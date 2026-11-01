"""Staged, verified transfers. Existing targets require an explicit replace policy.

Incomplete staging directories are deliberately retained after process termination.
They never have the final user filename; recovery instructions are in README.
"""
import hashlib
import os
import shutil
import tempfile
from pathlib import Path


class TransferCancelled(Exception):
    pass


def exists(path):
    return os.path.lexists(path)


def manifest(path):
    if path.is_symlink():
        raise ValueError('Символические ссылки не поддерживаются для безопасной передачи.')
    if path.is_dir():
        result = {}
        for child in sorted(path.iterdir()):
            # Junctions can point outside the selected tree or back into it.
            if child.is_symlink() or (hasattr(child, 'is_junction') and child.is_junction()):
                raise ValueError(f'Ссылка или junction в папке: {child}')
            result[child.name] = manifest(child)
        return result
    if not path.is_file():
        raise ValueError(f'Необычный тип файла: {path}')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return (path.stat().st_size, digest.hexdigest())


def transfer(source, destination, mode='copy', conflict=None):
    """conflict(source, target) -> rename/skip/replace/cancel, called by worker."""
    source = Path(source).absolute()
    destination = Path(destination).resolve(strict=True)
    if not destination.is_dir():
        raise ValueError('Папка назначения недоступна.')
    if source.is_symlink() or (hasattr(source, 'is_junction') and source.is_junction()):
        raise ValueError('Передача ссылок и junction не поддерживается.')
    source = source.resolve(strict=True)
    if mode not in ('copy', 'move'):
        raise ValueError('Неизвестный режим передачи.')
    target = destination / source.name
    if target.resolve() == source or (source.is_dir() and destination.is_relative_to(source)):
        raise ValueError('Нельзя передавать объект в самого себя или внутрь себя.')
    replace = False
    if exists(target):
        action = conflict(source, target) if conflict else 'rename'
        if action == 'cancel':
            raise TransferCancelled('Операция отменена.')
        if action == 'skip':
            return target, 'Пропущено'
        if action == 'replace':
            replace = True
        elif action == 'rename':
            n = 1
            while exists(target):
                target = destination / f'{source.stem} ({n}){source.suffix}'
                n += 1
        else:
            raise ValueError('Неизвестное решение конфликта.')
    stage = Path(tempfile.mkdtemp(prefix='.portal-transfer-', dir=destination))
    payload = stage / 'payload'
    backup = stage / 'previous'
    published = False
    try:
        before = manifest(source)
        if source.is_dir():
            shutil.copytree(source, payload, symlinks=True)
        else:
            shutil.copy2(source, payload)
        if manifest(payload) != before or manifest(source) != before:
            raise IOError('Проверка копии не пройдена: источник изменился или копия повреждена.')
        if replace and exists(target):
            target.rename(backup)
        try:
            # On Windows rename refuses to overwrite a concurrently created target.
            if exists(target):
                raise FileExistsError(f'Назначение появилось во время передачи: {target}')
            payload.rename(target)
            published = True
        except Exception:
            if exists(backup) and not exists(target):
                backup.rename(target)
            raise
        if mode == 'move':
            # A second check protects against most concurrent edits during copying.
            if manifest(source) != before:
                raise IOError('Источник изменился. Копия сохранена, источник не удалён.')
            if source.is_dir():
                shutil.rmtree(source)
            else:
                source.unlink()
        return target, 'Готово'
    finally:
        # Never discard a replacement backup on an unsuccessful publication.
        if not exists(backup) or published:
            shutil.rmtree(stage, ignore_errors=True)
