# -*- coding: utf-8 -*-
"""
Track list model.
"""
from functools import lru_cache
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtMultimedia import QMediaPlaylist


class TracksModel(QAbstractTableModel):
    """
    Track list model implementation.
    """
    commonFlags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    buttonFlags = commonFlags | Qt.ItemFlag.ItemIsEditable

    def __init__(self, playlist: QMediaPlaylist, column_count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist
        self.col_cnt = column_count

    def rowCount(self, _: QModelIndex=None) -> int: # pylint: disable=invalid-name
        """
        Get the number of rows.
        :return:
        """
        return self.playlist.mediaCount()

    @lru_cache(10)
    def columnCount(self, _: QModelIndex=None) -> int: # pylint: disable=invalid-name
        """
        Get the number of columns.
        :param _:
        :return:
        """
        return self.col_cnt

    def data(self, index: QModelIndex, role: int=None):
        """
        Get the data for given index and role.
        :param index:
        :param role:
        :return:
        """
        if not index.isValid() or role != 0 or index.column() != 0:
            return None

        return self.playlist.media(index.row()).canonicalUrl().fileName().rsplit('.', 1)[0]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        Get item flags for given index, separately for buttons.
        :param index:
        :return:
        """
        return TracksModel.commonFlags if index.column() == 0 else TracksModel.buttonFlags
