# -*- coding: utf-8 -*-
from functools import lru_cache
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtMultimedia import QMediaPlaylist


class TracksModel(QAbstractTableModel):
    commonFlags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    buttonFlags = commonFlags | Qt.ItemFlag.ItemIsEditable

    def __init__(self, playlist: QMediaPlaylist, column_count: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist
        self.col_cnt = column_count

    def rowCount(self, index=None, *args, **kwargs) -> int:
        return self.playlist.mediaCount()

    @lru_cache(10)
    def columnCount(self, *args, **kwargs) -> int:
        return self.col_cnt

    def data(self, index: QModelIndex, role=None):
        if not index.isValid():
            return None

        if role == 0 and index.column() == self.col_cnt-1:
            return self.playlist.media(index.row()).canonicalUrl().fileName().rsplit('.', 1)[0]

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return TracksModel.commonFlags if index.column() == self.col_cnt-1 else TracksModel.buttonFlags
