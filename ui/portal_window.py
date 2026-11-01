from PySide6.QtCore import Qt, Signal, Property, QPropertyAnimation, QEasingCurve, QTimer, QRectF
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget, QMenu


class PortalWindow(QWidget):
    dropped = Signal(str, list)
    changed = Signal()
    remove = Signal(str)
    open_folder = Signal(str)
    mode_requested = Signal(str, str)

    def __init__(self, model):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.model = model
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.resize(model.get('size', 140), model.get('size', 140))
        self._glow = 0.2
        self.status = ''
        self.drag_start = None
        self.busy = False
        self.animation = QPropertyAnimation(self, b'glow', self)
        self.animation.setDuration(260)
        self.animation.setEasingCurve(QEasingCurve.InOutSine)
        self.reset_timer = QTimer(self)
        self.reset_timer.setSingleShot(True)
        self.reset_timer.timeout.connect(self.reset_status)
        self.refresh_mode()

    def refresh_mode(self):
        mode = self.model['mode']
        description = ('Копирование — исходник остаётся' if mode == 'copy'
                       else 'Перемещение — исходник удаляется после проверки копии')
        self.setToolTip(f"{self.model['folder']}\n{description}")
        self.update()

    def get_glow(self):
        return self._glow

    def set_glow(self, value):
        self._glow = value
        self.update()

    glow = Property(float, get_glow, set_glow)

    def animate(self, value, pulse=False):
        self.animation.stop()
        self.animation.setStartValue(self._glow)
        self.animation.setEndValue(value)
        self.animation.setLoopCount(-1 if pulse else 1)
        self.animation.start()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        color = QColor('#F87171' if self.status == '!' else self.model['color'])
        rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
        for i in range(9, 0, -1):
            glow = QColor(color)
            glow.setAlpha(int((10 - i) * (1 + self._glow)))
            p.setPen(QPen(glow, i * 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect, 24, 24)
        p.setBrush(QColor('#1A2030'))
        p.setPen(QPen(color, 1.5 + self._glow))
        p.drawRoundedRect(rect, 24, 24)
        center = rect.center()
        p.setPen(QPen(color, 3))
        p.drawEllipse(QRectF(center.x()-23, 29, 46, 46))
        p.setFont(QFont('Segoe UI', 20))
        p.drawText(QRectF(center.x()-26, 27, 52, 48), Qt.AlignCenter, self.status or '↯')
        p.setPen(QColor('#F8FAFC'))
        p.setFont(QFont('Segoe UI', 9))
        text = p.fontMetrics().elidedText(self.model['name'], Qt.ElideRight, self.width()-34)
        p.drawText(QRectF(16, self.height()-59, self.width()-32, 24), Qt.AlignCenter, text)
        p.setFont(QFont('Segoe UI', 8))
        p.setPen(color)
        p.drawText(QRectF(16, self.height()-36, self.width()-32, 16), Qt.AlignCenter,
                   'Передача…' if self.busy else ('КОПИЯ' if self.model['mode']=='copy' else 'ПЕРЕНОС'))

    def enterEvent(self, event):
        if not self.busy: self.animate(1)

    def leaveEvent(self, event):
        if not self.busy: self.animate(.2)

    def dragEnterEvent(self, event):
        if not self.busy and event.mimeData().hasUrls() and all(u.isLocalFile() for u in event.mimeData().urls()):
            event.acceptProposedAction()
            self.animate(1, True)

    def dragLeaveEvent(self, event):
        self.animate(.2)

    def dropEvent(self, event):
        if self.busy: return
        event.setDropAction(Qt.CopyAction)  # Explorer must never delete the source itself.
        event.accept()
        self.dropped.emit(self.model['id'], [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()])

    def feedback(self, busy=False, success=True):
        self.busy = busy
        self.status = '…' if busy else ('✓' if success else '!')
        self.animate(1, busy)
        if not busy: self.reset_timer.start(2500)

    def reset_status(self):
        self.status = ''
        self.animate(.2)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if self.drag_start is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_start)

    def mouseReleaseEvent(self, event):
        if self.drag_start is not None:
            self.drag_start = None
            self.model.update(x=self.x(), y=self.y())
            self.changed.emit()

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction('Открыть папку', lambda: self.open_folder.emit(self.model['folder']))
        menu.addAction('Скрыть', self.hide_portal)
        modes = menu.addMenu('Режим передачи')
        modes.setEnabled(not self.busy)
        for label, mode in [('Копирование — оставить исходник', 'copy'),
                            ('Перемещение — удалить исходник', 'move')]:
            action = modes.addAction(label)
            action.setCheckable(True)
            action.setChecked(self.model['mode'] == mode)
            action.triggered.connect(lambda checked=False, value=mode:
                                     self.mode_requested.emit(self.model['id'], value))
        action = menu.addAction('Удалить портал', lambda: self.remove.emit(self.model['id']))
        action.setEnabled(not self.busy)
        menu.exec(event.globalPos())

    def hide_portal(self):
        self.model['visible'] = False
        self.hide()
        self.changed.emit()
