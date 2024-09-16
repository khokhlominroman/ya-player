# -*- coding: utf-8 -*-
from PyQt5.QtCore import QAbstractListModel, Qt
from yandex_music import Playlist


class PlaylistsModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[tuple[str, str, int]] = []

    def data(self, index, role=None):
        if role == Qt.DisplayRole:
            return self._rows[index.row()][0]

    def rowCount(self, index=None, *args, **kwargs) -> int:
        return len(self._rows)

    def update_data(self, data: list[Playlist]) -> None:
        self._rows.clear()
        self.beginResetModel()
        for _pl in data:
            self._rows.append((_pl.title, _pl.kind, _pl.revision))

        self.endResetModel()
