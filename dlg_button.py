# -*- coding: utf-8 -*-
from PyQt5.QtCore import QModelIndex, pyqtSignal
from PyQt5.QtWidgets import QItemDelegate, QPushButton, QStyle


class ButtonDelegate(QItemDelegate):
    ICONS = {1: QStyle.SP_TrashIcon,
             2: QStyle.SP_DialogApplyButton}
    pressed = pyqtSignal(int)

    def __init__(self, parent, operation):
        super().__init__(parent)
        self.operation = operation
        self.pnt_view = parent

    def createEditor(self, parent, option, index: QModelIndex) -> QPushButton:
        bt = QPushButton(parent)
        bt.setIcon(self.pnt_view.style().standardIcon(ButtonDelegate.ICONS[index.column()]))
        bt.setToolTip(self.operation)
        bt.clicked.connect(lambda checked, row=index.row(): self.pressed.emit(row))
        return bt

    def updateEditorGeometry(self, editor, option, index, **kwargs):
        editor.setGeometry(option.rect)
