import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from core.file_transfer import transfer, TransferCancelled
from core.settings import Settings
from core.history import History


class Transfers(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.dest = self.root / 'Целевая папка'
        self.dest.mkdir()
        self.source = self.root / 'Пример файла.txt'
        self.source.write_text('Привет! ' * 100, encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_copy_unicode(self):
        target, _ = transfer(self.source, self.dest)
        self.assertEqual(target.read_bytes(), self.source.read_bytes())

    def test_move(self):
        target, _ = transfer(self.source, self.dest, 'move')
        self.assertFalse(self.source.exists())
        self.assertTrue(target.is_file())

    def test_folder(self):
        folder = self.root / 'Папка'
        (folder / 'пустая').mkdir(parents=True)
        (folder / 'данные.txt').write_text('data')
        target, _ = transfer(folder, self.dest)
        self.assertTrue((target / 'пустая').is_dir())
        self.assertEqual((target / 'данные.txt').read_text(), 'data')

    def test_conflicts(self):
        target, _ = transfer(self.source, self.dest)
        renamed, _ = transfer(self.source, self.dest)
        self.assertNotEqual(target, renamed)
        _, status = transfer(self.source, self.dest, conflict=lambda *_: 'skip')
        self.assertEqual(status, 'Пропущено')
        with self.assertRaises(TransferCancelled):
            transfer(self.source, self.dest, conflict=lambda *_: 'cancel')
        self.source.write_text('new')
        transfer(self.source, self.dest, conflict=lambda *_: 'replace')
        self.assertEqual(target.read_text(), 'new')

    def test_self_and_descendant(self):
        with self.assertRaises(ValueError): transfer(self.source, self.root)
        with self.assertRaises(ValueError): transfer(self.root, self.dest)

    def test_missing_destination(self):
        with self.assertRaises(FileNotFoundError): transfer(self.source, self.root / 'missing')
        self.assertTrue(self.source.exists())

    def test_failed_copy_preserves_both(self):
        target = self.dest / self.source.name
        target.write_text('old')
        with patch('core.file_transfer.shutil.copy2', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                transfer(self.source, self.dest, 'move', lambda *_: 'replace')
        self.assertTrue(self.source.exists())
        self.assertEqual(target.read_text(), 'old')

    def test_failed_commit_restores_backup(self):
        target = self.dest / self.source.name
        target.write_text('old')
        original = Path.rename
        def rename(path, other):
            if path.name == 'payload': raise PermissionError('blocked')
            return original(path, other)
        with patch.object(Path, 'rename', rename):
            with self.assertRaises(PermissionError):
                transfer(self.source, self.dest, 'move', lambda *_: 'replace')
        self.assertTrue(self.source.exists())
        self.assertEqual(target.read_text(), 'old')

    def test_source_changes(self):
        import shutil
        copy = shutil.copy2
        def modified(src, dst):
            copy(src, dst)
            src.write_text('changed')
        with patch('core.file_transfer.shutil.copy2', modified):
            with self.assertRaises(IOError): transfer(self.source, self.dest, 'move')
        self.assertTrue(self.source.exists())
        self.assertFalse((self.dest / self.source.name).exists())

    def test_failed_source_delete_keeps_copy(self):
        with patch.object(Path, 'unlink', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError): transfer(self.source, self.dest, 'move')
        self.assertEqual(self.source.read_bytes(), (self.dest / self.source.name).read_bytes())

    def test_folder_move(self):
        folder = self.root / 'folder'
        folder.mkdir()
        (folder / 'file').write_text('content')
        target, _ = transfer(folder, self.dest, 'move')
        self.assertFalse(folder.exists())
        self.assertEqual((target / 'file').read_text(), 'content')

    def test_settings_history(self):
        settings = Settings(self.root)
        settings.data['portals'].append({'name': 'Портал'})
        settings.save()
        self.assertEqual(Settings(self.root).data['portals'][0]['name'], 'Портал')
        history = History(self.root)
        history.add({'source': 'file'})
        self.assertEqual(History(self.root).entries[0]['source'], 'file')


if __name__ == '__main__': unittest.main()
