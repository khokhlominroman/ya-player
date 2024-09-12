# -*- coding: utf-8 -*-
from functools import lru_cache
from PyQt5.QtCore import QModelIndex
from PyQt5.QtCore import QAbstractTableModel, Qt
from PyQt5.QtMultimedia import QMediaPlaylist


class TracksModel(QAbstractTableModel):
    commonFlags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
    buttonFlags = commonFlags | Qt.ItemFlag.ItemIsEditable

    def __init__(self, playlist: QMediaPlaylist, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.playlist = playlist

    def rowCount(self, index=None, *args, **kwargs) -> int:
        return self.playlist.mediaCount()

    @lru_cache(100)
    def columnCount(self, *args, **kwargs) -> int:
        return 3

    def data(self, index: QModelIndex, role=None):
        if not index.isValid():
            return None

        if role == 0 and index.column() == 2:
            return self.playlist.media(index.row()).canonicalUrl().fileName().rsplit('.', 1)[0]

    @lru_cache(100)
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        return TracksModel.commonFlags if index.column() == 0 else TracksModel.buttonFlags
