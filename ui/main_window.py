from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QMessageBox, QInputDialog)
from ui.create_portal_dialog import CreatePortalDialog


STYLE = '''
QWidget { background: #10131B; color: #F8FAFC; font-family: 'Segoe UI'; font-size: 10pt; }
QLabel#title { font-size: 32pt; font-weight: 700; color: #38BDF8; }
QPushButton { background: #1A2030; border: 1px solid #34405A; border-radius: 8px; padding: 10px 16px; }
QPushButton:hover { border-color: #38BDF8; background: #24314A; }
QPushButton#primary { background: #22658A; border-color: #38BDF8; }
QTableWidget { background: #1A2030; border: 0; border-radius: 8px; gridline-color: #293249; }
QHeaderView::section { background: #202A3E; color: #94A3B8; padding: 9px; border: 0; }
QLineEdit, QComboBox, QSpinBox { background: #1A2030; padding: 8px; border: 1px solid #34405A; border-radius: 5px; }
QMenu { background: #1A2030; padding: 5px; }
QMenu::item { padding: 8px 20px; } QMenu::item:selected { background: #22658A; }
'''


class MainWindow(QMainWindow):
    def __init__(self, manager, history):
        super().__init__()
        self.manager, self.history = manager, history
        self.setWindowTitle('Portal — телепортация файлов')
        self.resize(960, 740)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 24, 28, 24)
        title = QLabel('PORTAL')
        title.setObjectName('title')
        layout.addWidget(title)
        layout.addWidget(QLabel('Ваши папки — на расстоянии одного движения.'))
        bar = QHBoxLayout()
        for label, callback in [('＋ Создать портал', self.create), ('Показать все', lambda: manager.visibility(True)),
                                ('Скрыть все', lambda: manager.visibility(False)), ('Настройки', self.preferences)]:
            button = QPushButton(label)
            if label.startswith('＋'): button.setObjectName('primary')
            button.clicked.connect(callback)
            bar.addWidget(button)
        layout.addLayout(bar)
        layout.addWidget(QLabel('ПОРТАЛЫ · выберите строку для действий'))
        self.portals = self.table(['Название', 'Папка назначения', 'Режим', 'Видимость'])
        layout.addWidget(self.portals, 2)
        actions = QHBoxLayout()
        for label, callback in [('Открыть папку', self.open_folder), ('Режим передачи', self.change_mode),
                                ('Показать / скрыть', self.toggle), ('Удалить портал', self.remove)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)
        self.status = QLabel('Готов к передаче')
        layout.addWidget(self.status)
        layout.addWidget(QLabel('ИСТОРИЯ · последние 500 операций'))
        self.log = self.table(['Время', 'Имя', 'Источник', 'Назначение', 'Режим', 'Результат', 'Ошибка'])
        layout.addWidget(self.log, 3)
        manager.updated.connect(self.refresh)
        manager.operation.connect(self.record)
        self.refresh()
        self.refresh_history()

    def table(self, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.verticalHeader().hide()
        return table

    def create(self):
        dialog = CreatePortalDialog(self, self.manager.settings.data.get('size', 140))
        if dialog.exec(): self.manager.add(dialog.portal())

    def preferences(self):
        size, ok = QInputDialog.getInt(self, 'Настройки', 'Размер новых порталов (пиксели):',
                                     self.manager.settings.data.get('size', 140), 140, 240, 10)
        if ok:
            self.manager.settings.data['size'] = size
            self.manager.save()

    def selected(self):
        row = self.portals.currentRow()
        models = self.manager.settings.data['portals']
        return models[row] if 0 <= row < len(models) else None

    def open_folder(self):
        model = self.selected()
        if model: QDesktopServices.openUrl(QUrl.fromLocalFile(model['folder']))

    def toggle(self):
        model = self.selected()
        if model: self.manager.visibility(not model.get('visible', True), model['id'])

    def change_mode(self):
        model = self.selected()
        if not model:
            QMessageBox.information(self, 'Выберите портал', 'Сначала выберите портал в таблице.')
            return
        labels = ['Копирование — исходник остаётся', 'Перемещение — исходник удаляется после проверки']
        label, ok = QInputDialog.getItem(self, 'Режим передачи', model['name'], labels,
                                        0 if model['mode'] == 'copy' else 1, False)
        if ok:
            self.manager.set_mode(model['id'], 'copy' if label == labels[0] else 'move')

    def remove(self):
        model = self.selected()
        if model: self.manager.remove(model['id'])

    def refresh(self):
        models = self.manager.settings.data['portals']
        self.portals.setRowCount(len(models))
        for row, model in enumerate(models):
            values = [model['name'], model['folder'], 'Копирование' if model['mode']=='copy' else 'Перемещение',
                      'Виден' if model.get('visible', True) else 'Скрыт']
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.portals.setItem(row, col, item)
        self.status.setText(f'Активных передач: {len(self.manager.workers)} · Порталов: {len(models)}')

    def record(self, entry):
        try:
            self.history.add(entry)
        except OSError as exc:
            QMessageBox.warning(self, 'История не сохранена', str(exc))
        self.refresh_history()

    def refresh_history(self):
        self.log.setRowCount(len(self.history.entries))
        for row, entry in enumerate(self.history.entries):
            values = [entry.get('time',''), Path(entry['source']).name, entry['source'], entry['destination'],
                      'Копирование' if entry['mode']=='copy' else 'Перемещение', entry['status'], entry['error']]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.log.setItem(row, col, item)

    def closeEvent(self, event):
        if self.property('quitting'):
            event.accept()
        else:
            event.ignore()
            self.hide()
