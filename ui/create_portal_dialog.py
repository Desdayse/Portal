from pathlib import Path
from uuid import uuid4
from PySide6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QPushButton,
                              QFileDialog, QComboBox, QDialogButtonBox, QMessageBox)


class CreatePortalDialog(QDialog):
    def __init__(self, parent=None, size=140):
        super().__init__(parent)
        self.setWindowTitle('Создать портал')
        self.setMinimumWidth(420)
        self.size = size
        form = QFormLayout(self)
        self.name = QLineEdit()
        self.folder = QLineEdit()
        browse = QPushButton('Выбрать папку…')
        browse.clicked.connect(self.browse)
        self.color = QComboBox()
        for label, value in [('Голубой', '#38BDF8'), ('Фиолетовый', '#8B5CF6'), ('Зелёный', '#34D399'), ('Розовый', '#F472B6')]:
            self.color.addItem(label, value)
        self.mode = QComboBox()
        self.mode.addItem('Копирование', 'copy')
        self.mode.addItem('Перемещение', 'move')
        form.addRow('Название', self.name)
        form.addRow('Папка', self.folder)
        form.addRow('', browse)
        form.addRow('Цвет', self.color)
        form.addRow('Режим', self.mode)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Save).setText('Создать')
        buttons.button(QDialogButtonBox.Cancel).setText('Отмена')
        buttons.accepted.connect(self.validate)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def browse(self):
        folder = QFileDialog.getExistingDirectory(self, 'Папка назначения')
        if folder:
            self.folder.setText(folder)
            if not self.name.text():
                self.name.setText(Path(folder).name)

    def validate(self):
        if not self.name.text().strip() or not Path(self.folder.text()).is_dir() or not self.folder.text().strip():
            QMessageBox.warning(self, 'Проверьте данные', 'Введите название и выберите существующую папку.')
            return
        self.accept()

    def portal(self):
        return dict(id=uuid4().hex, name=self.name.text().strip(), folder=str(Path(self.folder.text()).absolute()),
                    color=self.color.currentData(), mode=self.mode.currentData(), x=100, y=100,
                    size=self.size, visible=True)
