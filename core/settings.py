import json
import os
from pathlib import Path


def data_dir():
    path = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local' / 'share')) / 'Portal'
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError) as exc:
        raise RuntimeError(f'Не удалось прочитать {path}: {exc}') from exc


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    with temp.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)


class Settings:
    def __init__(self, root=None):
        self.path = (root or data_dir()) / 'settings.json'
        self.data = read_json(self.path, {'portals': [], 'size': 140})
        if not isinstance(self.data, dict) or not isinstance(self.data.get('portals'), list):
            raise RuntimeError('Неверный формат settings.json. Сохраните резервную копию и исправьте файл.')

    def save(self):
        write_json(self.path, self.data)
