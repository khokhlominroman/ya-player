# -*- coding: utf-8 -*-
"""
QTableView button delegate.
"""
from PyQt5.QtCore import QModelIndex, pyqtSignal
from PyQt5.QtWidgets import QItemDelegate, QPushButton, QStyle, QStyleOptionViewItem, QWidget


class ButtonDelegate(QItemDelegate):
    """
    QTableView button delegate for different roles.
    """
    ICONS = {1: QStyle.SP_TrashIcon,
             2: QStyle.SP_FileDialogListView,
             3: QStyle.SP_DialogApplyButton}
    pressed = pyqtSignal(int)

    def __init__(self, parent: QWidget, tooltip: str) -> None:
        super().__init__(parent)
        self.tooltip = tooltip
        self.pnt_view = parent

    def createEditor(self, parent: QWidget, _, index: QModelIndex) -> QPushButton: # pylint: disable=invalid-name
        """
        Create the QPushButton instance.
        :param parent:
        :param index:
        :return:
        """
        bt = QPushButton(parent)
        bt.setIcon(self.pnt_view.style().standardIcon(ButtonDelegate.ICONS[index.column()]))
        bt.setToolTip(self.tooltip)
        bt.clicked.connect(lambda checked, row=index.row(): self.pressed.emit(row))
        return bt

    def updateEditorGeometry(self, editor: QWidget, option: QStyleOptionViewItem, _: QModelIndex) -> None: # pylint: disable=invalid-name
        """
        Implementation for QPushButton redraw.
        :param editor:
        :param option:
        :return:
        """
        editor.setGeometry(option.rect)
