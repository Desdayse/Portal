import threading
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox
from core.file_transfer import transfer, TransferCancelled
from ui.portal_window import PortalWindow


class TransferWorker(QThread):
    conflict_requested = Signal(object)
    result = Signal(dict)

    def __init__(self, model, sources):
        super().__init__()
        self.model = dict(model)
        self.sources = sources
        self.condition = threading.Condition()
        self.choice = None
        self.failed = False

    def decide(self, source, target):
        with self.condition:
            self.choice = None
            self.conflict_requested.emit((self, str(source), str(target)))
            self.condition.wait_for(lambda: self.choice is not None)
            return self.choice

    def answer(self, choice):
        with self.condition:
            self.choice = choice
            self.condition.notify_all()

    def run(self):
        for source in self.sources:
            entry = dict(source=source, destination=str(Path(self.model['folder']) / Path(source).name),
                         mode=self.model['mode'], error='')
            try:
                target, status = transfer(source, self.model['folder'], self.model['mode'], self.decide)
                entry.update(destination=str(target), status=status)
            except TransferCancelled as exc:
                entry.update(status='Отменено', error=str(exc))
                self.result.emit(entry)
                break
            except Exception as exc:
                self.failed = True
                entry.update(status='Ошибка', error=str(exc))
            self.result.emit(entry)


class PortalManager(QObject):
    updated = Signal()
    operation = Signal(dict)

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.windows = {}
        self.workers = {}
        for model in settings.data['portals']:
            self.add(model, persist=False)
        QApplication.instance().screenRemoved.connect(lambda _: self.recover_positions())

    def save(self):
        try:
            self.settings.save()
        except OSError as exc:
            QMessageBox.critical(None, 'Настройки не сохранены', str(exc))
        self.updated.emit()

    def recover_positions(self):
        for window in self.windows.values():
            self.place(window)
        self.save()

    def place(self, window):
        from PySide6.QtCore import QRect
        screens = QApplication.screens()
        wanted = QRect(window.model.get('x', 100), window.model.get('y', 100), window.width(), window.height())
        screen = next((s for s in screens if s.availableGeometry().contains(wanted)), screens[0])
        area = screen.availableGeometry()
        x = max(area.left(), min(wanted.x(), area.right()-window.width()+1))
        y = max(area.top(), min(wanted.y(), area.bottom()-window.height()+1))
        window.move(x, y)
        window.model.update(x=x, y=y)

    def add(self, model, persist=True):
        window = PortalWindow(model)
        window.changed.connect(self.save)
        window.remove.connect(self.remove)
        window.open_folder.connect(lambda path: QDesktopServices.openUrl(QUrl.fromLocalFile(path)))
        window.dropped.connect(self.start)
        window.mode_requested.connect(self.set_mode)
        self.windows[model['id']] = window
        self.place(window)
        if model.get('visible', True): window.show()
        if persist:
            self.settings.data['portals'].append(model)
            self.save()

    def set_mode(self, portal_id, mode):
        if mode not in ('copy', 'move') or portal_id not in self.windows:
            return
        if portal_id in self.workers:
            QMessageBox.information(None, 'Передача выполняется', 'Дождитесь завершения передачи перед сменой режима.')
            return
        window = self.windows[portal_id]
        if window.model['mode'] == mode:
            return
        if mode == 'move' and QMessageBox.question(
                None, 'Включить перемещение?',
                'При следующих передачах исходные файлы будут удаляться после успешного копирования и проверки.\n'
                'Уже скопированные файлы останутся на месте. Включить перемещение?',
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        window.model['mode'] = mode
        window.refresh_mode()
        self.save()

    def remove(self, portal_id):
        if portal_id in self.workers: return
        if QMessageBox.question(None, 'Удалить портал?', 'Будет удалён только портал. Файлы и папка останутся.') != QMessageBox.Yes:
            return
        self.windows.pop(portal_id).close()
        self.settings.data['portals'] = [p for p in self.settings.data['portals'] if p['id'] != portal_id]
        self.save()

    def visibility(self, visible, portal_id=None):
        for key, window in self.windows.items():
            if portal_id is None or key == portal_id:
                window.model['visible'] = visible
                window.setVisible(visible)
        self.save()

    def start(self, portal_id, sources):
        if portal_id in self.workers or not sources: return
        window = self.windows[portal_id]
        worker = TransferWorker(window.model, sources)
        self.workers[portal_id] = worker
        worker.conflict_requested.connect(self.resolve_conflict)
        worker.result.connect(self.operation)
        worker.finished.connect(lambda: self.completed(portal_id))
        window.feedback(busy=True)
        worker.start()
        self.updated.emit()

    def completed(self, portal_id):
        worker = self.workers.pop(portal_id)
        self.windows[portal_id].feedback(success=not worker.failed)
        worker.deleteLater()
        self.updated.emit()

    def resolve_conflict(self, request):
        worker, source, target = request
        box = QMessageBox()
        box.setWindowTitle('Совпадение имён')
        box.setText(f'В папке уже есть объект:\n{target}\n\nЧто сделать с новым объектом?')
        choices = {}
        for title, choice, role in [('Переименовать новый', 'rename', QMessageBox.AcceptRole),
                                    ('Пропустить', 'skip', QMessageBox.ActionRole),
                                    ('Заменить…', 'replace', QMessageBox.DestructiveRole),
                                    ('Отменить оставшиеся', 'cancel', QMessageBox.RejectRole)]:
            choices[box.addButton(title, role)] = choice
        box.exec()
        choice = choices.get(box.clickedButton(), 'cancel')
        if choice == 'replace':
            if QMessageBox.warning(None, 'Подтверждение замены',
                                   f'Заменить объект целиком?\n{target}\nСуществующее содержимое будет удалено после успешной передачи.',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
                choice = 'skip'
        worker.answer(choice)
