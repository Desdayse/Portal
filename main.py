import sys
import traceback
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QPen
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from core.settings import Settings, data_dir
from core.history import History
from core.portal_manager import PortalManager
from ui.main_window import MainWindow, STYLE


def app_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor('#10131B'))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor('#38BDF8'), 5))
    painter.drawEllipse(9, 9, 46, 46)
    painter.setPen(QPen(QColor('#8B5CF6'), 4))
    painter.drawLine(36, 18, 25, 34)
    painter.drawLine(25, 34, 39, 31)
    painter.drawLine(39, 31, 28, 47)
    painter.end()
    return QIcon(pixmap)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('Portal')
    app.setStyle('Fusion')
    app.setStyleSheet(STYLE)
    app.setQuitOnLastWindowClosed(False)
    lock = QLockFile(str(data_dir() / 'portal.lock'))
    if not lock.tryLock(100):
        if '--smoke-test' in sys.argv:
            raise RuntimeError('Не удалось захватить блокировку приложения')
        QMessageBox.information(None, 'Portal уже работает', 'Откройте Portal через значок в системном трее.')
        return 0
    try:
        manager = PortalManager(Settings())
        window = MainWindow(manager, History())
    except Exception as exc:
        if '--smoke-test' in sys.argv:
            raise
        QMessageBox.critical(None, 'Ошибка запуска', str(exc))
        return 1
    icon = app_icon()
    app.setWindowIcon(icon)
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip('Portal — телепортация файлов')
    menu = QMenu()

    def show():
        window.showNormal()
        window.raise_()
        window.activateWindow()

    def quit_app():
        if manager.workers:
            QMessageBox.information(window, 'Передача выполняется', 'Дождитесь завершения передач, затем выберите «Выход» снова.')
            return
        manager.save()
        window.setProperty('quitting', True)
        app.quit()

    menu.addAction('Открыть Portal', show)
    menu.addAction('Показать все порталы', lambda: manager.visibility(True))
    menu.addAction('Скрыть все порталы', lambda: manager.visibility(False))
    menu.addAction('Создать портал', window.create)
    menu.addAction('Настройки', window.preferences)
    menu.addSeparator()
    menu.addAction('Выход', quit_app)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show() if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
    tray.show()
    window.show()
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(500, app.quit)
    return app.exec()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:
        (data_dir() / 'crash.log').write_text(traceback.format_exc(), encoding='utf-8')
        raise
