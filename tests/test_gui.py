import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import QPoint, Qt, QElapsedTimer
from PySide6.QtTest import QTest
from core.settings import Settings
from core.history import History
from core.portal_manager import PortalManager
from ui.main_window import MainWindow
from ui.create_portal_dialog import CreatePortalDialog


class GuiSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_create_restore_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dialog = CreatePortalDialog()
            dialog.name.setText('Тест')
            dialog.folder.setText(tmp)
            model = dialog.portal()
            manager = PortalManager(Settings(root))
            window = MainWindow(manager, History(root))
            manager.add(model)
            self.app.processEvents()
            self.assertEqual(window.portals.rowCount(), 1)
            self.assertEqual(Settings(root).data['portals'][0]['name'], 'Тест')
            restored = PortalManager(Settings(root))
            self.assertEqual(restored.windows[model['id']].model['folder'], tmp)
            for portal in restored.windows.values(): portal.close()
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                manager.remove(model['id'])
            self.assertEqual(len(manager.windows), 0)
            self.assertEqual(Settings(root).data['portals'], [])
            window.setProperty('quitting', True)
            window.close()

    def test_mode_after_reposition_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dest = root / 'destination'
            dest.mkdir()
            dialog = CreatePortalDialog()
            dialog.name.setText('Перенос')
            dialog.folder.setText(str(dest))
            model = dialog.portal()
            manager = PortalManager(Settings(root))
            manager.add(model)
            portal = manager.windows[model['id']]
            # A screen to the left of the primary monitor has negative coordinates.
            portal.move(-1200, 80)
            portal.drag_start = QPoint(20, 20)
            QTest.mouseRelease(portal, Qt.LeftButton)
            self.assertEqual(model['mode'], 'copy')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.No):
                manager.set_mode(model['id'], 'move')
            self.assertEqual(model['mode'], 'copy')
            with patch.object(QMessageBox, 'question', return_value=QMessageBox.Yes):
                manager.set_mode(model['id'], 'move')
            self.assertEqual(Settings(root).data['portals'][0]['mode'], 'move')
            restored = PortalManager(Settings(root))
            self.assertEqual(restored.windows[model['id']].model['mode'], 'move')
            source = root / 'sample.txt'
            source.write_text('test move')
            results = []
            restored.operation.connect(results.append)
            restored.start(model['id'], [str(source)])
            timer = QElapsedTimer()
            timer.start()
            while restored.workers and timer.elapsed() < 5000:
                QTest.qWait(10)
            self.assertFalse(restored.workers)
            self.assertFalse(source.exists())
            self.assertEqual((dest / 'sample.txt').read_text(), 'test move')
            self.assertEqual(results[0]['mode'], 'move')
            for owner in (manager, restored):
                for window in owner.windows.values(): window.close()
