# -*- coding: utf-8 -*-
"""
Model for the list of playlists.
"""
from PyQt5.QtCore import QAbstractListModel, Qt, QModelIndex
from PyQt5.QtWidgets import QWidget
from yandex_music import Playlist


class PlaylistsModel(QAbstractListModel):
    """
    Model implementation for the list of playlists.
    """
    def __init__(self, parent: QWidget=None) -> None:
        super().__init__(parent)
        self.rows: list[tuple[str, str, int]] = []

    def data(self, index: QModelIndex, role: int=None):
        """
        Get the data for given index and role.
        :param index:
        :param role:
        :return:
        """
        if role == Qt.DisplayRole:
            return self.rows[index.row()][0]

        return None

    def rowCount(self, _: QModelIndex=None) -> int: # pylint: disable=invalid-name
        """
        Get the number of rows.
        :return:
        """
        return len(self.rows)

    def update_data(self, data: list[Playlist]) -> None:
        """
        Fully update the underlying data.
        :param data:
        :return:
        """
        self.rows.clear()
        self.beginResetModel()
        for _pl in data:
            self.rows.append((_pl.title, _pl.kind, _pl.revision))

        self.endResetModel()
