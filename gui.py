from json import dump, load
from os import getcwd, path, remove as os_rm
from PyQt5 import uic
from PyQt5.QtCore import QItemSelection, QModelIndex, QPoint, Qt, QUrl, QSize
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QHeaderView, QMainWindow, QDialog, QLabel, QMessageBox as Qmb
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from yandex_music.exceptions import NetworkError
from yandex_music.track_short import TrackShort

from dlg_button import ButtonDelegate
from models.playlists import PlaylistsModel
from models.tracks import TracksModel
from yaclient import YaClient, Track

_APP_TITLE = 'Yandex player'


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__(flags=Qt.WindowType.Window)
        uic.loadUi(path.join(getcwd(), 'ui/main.ui'), self)
        with open('./ui/style.qss', 'r') as fh:
            self.setStyleSheet('\n'.join(fh.readlines()))

        with open('settings.json', 'r') as fh:
            settings = load(fh)
            try:
                self.resize(QSize(*settings.get('size', (600, 700))))
                self.move(QPoint(*settings.get('pos', (0, 0))))
            except (KeyError, ValueError) as e:
                Qmb.critical(self, _APP_TITLE, f'Error: can\'t resize window\n{e}')
                return

        # Yandex client
        self.is_logged = False
        self.__yac: YaClient = None
        self.currtab_idx = 0

        # Player
        self.player = QMediaPlayer(self)
        self.player.error.connect(lambda err: Qmb.critical(self, 'Error', str(err)))
        self.player.durationChanged.connect(self.update_duration)
        self.player.positionChanged.connect(self.update_position)
        self.btPlay.pressed.connect(self.player.play)
        self.btPause.pressed.connect(self.player.pause)
        self.btStop.pressed.connect(self.player.stop)
        self.volumeSlider.valueChanged.connect(self.player.setVolume)
        self.qmplTracks = QMediaPlaylist()
        self.qmplLikes = QMediaPlaylist()
        self.qmplSimilar = QMediaPlaylist()
        self.player.setPlaylist(self.qmplTracks)

        # Models
        self.model_playlists = PlaylistsModel()
        self.model_tracks = TracksModel(self.qmplTracks, 4)
        self.model_likes = TracksModel(self.qmplLikes, 3)
        self.lvPlaylists.setModel(self.model_playlists)
        self.tvTracks.setModel(self.model_tracks)
        self.tvLikes.setModel(self.model_likes)

    #     # Signals
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.btLike.pressed.connect(self._like_track)
        self.btPrevious.pressed.connect(self.qmplTracks.previous)
        self.btNext.pressed.connect(self.qmplTracks.next)
        self.qmplTracks.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.qmplLikes.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.qmplSimilar.currentIndexChanged.connect(self.on_track_similar_changed)
        self.lvPlaylists.selectionModel().selectionChanged.connect(self.on_playlist_selected)
        self.tvTracks.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.tvLikes.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.tvTracks.doubleClicked.connect(self.on_track_double_clicked)
        self.tvLikes.doubleClicked.connect(self.on_track_double_clicked)
        self.timeSlider.valueChanged.connect(self.player.setPosition)
        self.dlg_tracks_del = ButtonDelegate(self.tvTracks, 'Удалить')
        self.dlg_tracks_similar = ButtonDelegate(self.tvTracks, 'Волна по треку')
        self.dlg_tracks_like = ButtonDelegate(self.tvTracks, 'Добавить в коллекцию')
        self.dlg_likes_del = ButtonDelegate(self.tvLikes, 'Удалить')
        self.dlg_likes_similar = ButtonDelegate(self.tvLikes, 'Волна по треку')
        self.dlg_tracks_del.pressed.connect(self._delete_track)
        self.dlg_tracks_similar.pressed.connect(self._similar)
        self.dlg_tracks_like.pressed.connect(self._like_track)
        self.dlg_likes_del.pressed.connect(self._delete_track)
        self.dlg_likes_similar.pressed.connect(self._similar)
        self.actUpdateLikes.triggered.connect(self.__update_likes)
        self.actAbout.triggered.connect(self.on_about)
        self.actLogout.triggered.connect(self.__logout)

        self.setup_ui()
        self.actLogout.setText("Login")

    def setup_ui(self) -> None:
        for tv in (self.tvTracks, self.tvLikes):
            tv.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tv.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            tv.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.tvTracks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tvTracks.setItemDelegateForColumn(1, self.dlg_tracks_del)
        self.tvTracks.setItemDelegateForColumn(2, self.dlg_tracks_similar)
        self.tvTracks.setItemDelegateForColumn(3, self.dlg_tracks_like)
        self.tvLikes.setItemDelegateForColumn(1, self.dlg_likes_del)
        self.tvLikes.setItemDelegateForColumn(2, self.dlg_likes_similar)

        mbar = self.menuBar()
        self.lbUser = QLabel(mbar)
        mbar.setCornerWidget(self.lbUser, Qt.TopRightCorner)
        self.lbUser.setAlignment(Qt.AlignRight)
        self.lbUser.setMinimumWidth(int(self.size().width()/2))
        self.lbUser.setContentsMargins(1, 2, 4, 1)

        self.lbst = QLabel(self.status)
        self.status.addWidget(self.lbst)

        _px = QPixmap(f'./ui/images/image.png')
        self.lbTrackCover.setPixmap(_px)
        self.lbLikesCover.setPixmap(_px)

        self.setAcceptDrops(True)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.__yac is not None and self.__yac.clt.token:
            sz = self.size()
            pos = self.pos()
            settings = {'TOKEN': self.__yac.clt.token, 'size': (sz.width(), sz.height()),
                        'pos': (pos.x(), pos.y())}
            with open('settings.json', 'w') as fh:
                dump(settings, fh)

        event.accept()

    def login(self) -> None:
        _token = None
        if path.exists('settings.json'):
            with open('settings.json', 'r') as fh:
                _token = load(fh).get('TOKEN')

        if not _token:
            Qmb.critical(self, _APP_TITLE, 'You should get a token.\n'
                                           'See https://yandex-music.readthedocs.io/en/main/token.html')
            return

        try:
            self.__yac = YaClient(_token)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.is_logged = self.__yac.clt.me is not None
        if not self.is_logged:
            return

        self.actLogout.setText("Выйти из аккаунта")
        self.lbUser.setText(f'{self.__yac.clt.me.account.full_name} | {self.__yac.clt.me.default_email} ')

        self.__update_playlists()
        self.__update_likes()

    def __logout(self) -> None:
        self.qmplLikes.clear()
        if path.exists("settings.json"):
            os_rm("settings.json")
            im = QPixmap(f"./images/image.png")
            self.lbLikesCover.setPixmap(im)
            self.lbTrackCover.setPixmap(im)
            self.actionLog_Out.setText("Войти в аккаунт")
            self.acc_name.setText("")
            self.__yac.clear_cache()
            self.__yac = None
            self.is_logged = False
        else:
            Qmb.critical(self, _APP_TITLE, 'You are not logged in')

    def _like_track(self, row: int=None):
        if self.__yac is None:
            Qmb.critical(self, "Update Error", "You are not logged in", defaultButton=Qmb.Ok)
            return

        if row is None:
            _pl = self.__yac.playlist if self.player.playlist() is self.qmplTracks else self.__yac.similar
            _tr = _pl[self.player.playlist().currentIndex()]
        else:
            _tr = self.__yac.playlist[row]

        try:
            if _tr.like():
                self.lbst.setText(f'Track `{_tr.title}` liked')
            else:
                Qmb.warning(self, _APP_TITLE, f'Не получается поставить лайк')
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')

        self.__update_likes()

    def _similar(self, row: int) -> None:
        if self.currtab_idx == 0:
            _tid = self.__yac.playlist[row].id
        elif self.currtab_idx == 1:
            _tid = self.__yac.likes[row].id
        else:
            return

        try:
            if self.__yac.load_similar(_tid):
                self.qmplSimilar.clear()
                for _tr in self.__yac.similar:
                    self.qmplSimilar.addMedia(QMediaContent(
                        QUrl(f'file://{YaClient.TRACKS_DIR}/{", ".join(_tr.artists_name())} - '
                             f'{_tr.title}.{YaClient.CODEC}')))

                self.player.setPlaylist(self.qmplSimilar)
                self.btPrevious.pressed.disconnect()
                self.btNext.pressed.disconnect()
                self.btPrevious.pressed.connect(self.qmplSimilar.previous)
                self.btNext.pressed.connect(self.qmplSimilar.next)
                self.qmplSimilar.setCurrentIndex(0)
                self.player.play()
            else:
                Qmb.information(self, _APP_TITLE, 'Похожие треки не найдены')
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')

    def _delete_track(self, row: int) -> None:
        if self.__yac is None:
            Qmb.critical(self, _APP_TITLE, 'Нужно залогиниться с помощью токена', defaultButton=Qmb.Ok)
            return
        if Qmb.StandardButton.Yes != Qmb.question(self, _APP_TITLE, 'Удалить трек из списка?'):
            return

        if self.currtab_idx == 0:
            _pl = self.model_playlists._rows[self.lvPlaylists.currentIndex().row()]
            _list = self.__yac.playlist
            track = self.__yac.playlist[row]
            try:
                _updated = self.__yac.clt.users_playlists_delete_track(_pl[1], row, row, _pl[2])
                _list.clear()
                for _tr in _updated.tracks:
                    if isinstance(_tr, TrackShort):
                        _tr = _tr.track

                    _list.append(_tr)
            except NetworkError as e:
                Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
                return
        elif self.currtab_idx == 1:
            track = self.__yac.likes[row]
            if self.__yac.clt.users_likes_tracks_remove(track.id):
                self.__update_likes()
        else:
            return

        self.lbst.setText(f'Track `{track.title}` removed')

    def __update_playlists(self) -> None:
        if self.__yac is None:
            Qmb.critical(self, "Update Error", "You are not logged in", defaultButton=Qmb.Ok)
            return

        try:
            self.model_playlists.update_data(self.__yac.clt.users_playlists_list())
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.lbst.setText('Playlists updated')

    def __update_likes(self) -> None:
        if not self.is_logged:
            Qmb.critical(self, "Update Error", "You are not logged in", defaultButton=Qmb.Ok)
            return

        try:
            self.__yac.load_list('likes')
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.__update_media(self.model_likes, self.qmplLikes, self.__yac.likes)
        self.lbst.setText('Likes updated')

    def __update_media(self, model: TracksModel, playlist: QMediaPlaylist, tracks: list[Track]) -> None:
        if not self.is_logged:
            return

        playlist.clear()
        for _tr in tracks:
            playlist.addMedia(QMediaContent(
                QUrl(f'file://{YaClient.TRACKS_DIR}/{", ".join(_tr.artists_name())} - {_tr.title}.{YaClient.CODEC}')))

        model.layoutChanged.emit()

    def update_duration(self, duration: int) -> None:
        self.timeSlider.setMaximum(duration)
        if duration >= 0:
            self.totalTimeLabel.setText(f'{duration//60000}:{duration%60000//1000:02d}')

    def update_position(self, position: int) -> None:
        if position >= 0:
            self.currentTimeLabel.setText(f'{position//60000}:{position%60000//1000:02d}')

        # Disable the events to prevent update triggering a setPosition event (can cause stuttering).
        self.timeSlider.blockSignals(True)
        self.timeSlider.setValue(position)
        self.timeSlider.blockSignals(False)

    def on_playlist_selected(self, idx: QModelIndex, _) -> None:
        _pl = self.model_playlists._rows[idx.indexes()[0].row()]
        try:
            self.__yac.load_list(_pl[0], _pl[1])
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.__update_media(self.model_tracks, self.qmplTracks, self.__yac.playlist)
        self.lbst.setText(f'{_pl[0]} updated')

    def on_track_selected(self, curr: QItemSelection, prev: QItemSelection) -> None:
        if curr.isEmpty():
            return

        self.lbst.setText('')

        row = curr.indexes()[0].row()
        if self.currtab_idx == 0:
            view = self.tvTracks
            model = self.model_tracks
            cover = self.lbTrackCover
            title = self.lbTrackTitle
            track = self.__yac.playlist[row]
        elif self.currtab_idx == 1:
            view = self.tvLikes
            model = self.model_likes
            cover = self.lbLikesCover
            title = self.lbLikesTitle
            track = self.__yac.likes[row]
        else:
            return

        artists = ", ".join(track.artists_name())
        cover_name = f'{artists} - {track.title}'.replace('/', '\\')
        cover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{cover_name}.png'))
        album = f'{track.albums[0].title} [{track.albums[0].year}]' if len(track.albums) > 0 else ''
        duration = f'{track.duration_ms//60000}:{track.duration_ms%60000//1000:02d}'
        title.setText(f'<b>{artists}</b><br><br>{track.title} [<b>{duration}</b>]<br><br><b>Альлбом</b><br>{album}')
        view.openPersistentEditor(model.index(row, 1))
        view.openPersistentEditor(model.index(row, 2))
        if model.col_cnt == 4:
            view.openPersistentEditor(model.index(row, 3))

        if not prev.isEmpty():
            row = prev.indexes()[0].row()
            view.closePersistentEditor(model.index(row, 1))
            view.closePersistentEditor(model.index(row, 2))
            if model.col_cnt == 4:
                view.closePersistentEditor(model.index(row, 3))

    def on_track_double_clicked(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return

        if self.currtab_idx == 0:
            qmpl = self.qmplTracks
            view = self.tvTracks
        elif self.currtab_idx == 1:
            qmpl = self.qmplLikes
            view = self.tvLikes
        else:
            return

        qmpl.setCurrentIndex(idx.row())
        self.player.play()
        view.setCurrentIndex(idx)

    def on_track_selected_qmpl(self, idx: int) -> None:
        if idx < 0:
            return

        if self.currtab_idx == 0:
            track = self.__yac.playlist[idx]
            view = self.tvTracks
            model = self.model_tracks
        elif self.currtab_idx == 1:
            track = self.__yac.likes[idx]
            view = self.tvLikes
            model = self.model_likes
        else:
            return

        try:
            self.__yac.download_track(track)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        track_name = f'{", ".join(track.artists_name())} - {track.title}'.replace('/', '\\')
        self.lbCurrCover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{track_name}.png'))
        self.lbCurrTitle.setText(track_name)
        view.setCurrentIndex(model.index(idx, 2))

    def on_track_similar_changed(self, idx: int) -> None:
        track = self.__yac.similar[idx]
        try:
            self.__yac.download_track(track)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        track_name = f'{", ".join(track.artists_name())} - {track.title}'.replace('/', '\\')
        self.lbCurrCover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{track_name}.png'))
        self.lbCurrTitle.setText(track_name)

    def on_tab_changed(self, ix: int) -> None:
        self.currtab_idx = ix
        if ix == 0:
            qmplist = self.qmplTracks
            self.__update_playlists()
        elif ix == 1:
            qmplist = self.qmplLikes
            self.__update_likes()
        else:
            return

        self.player.setPlaylist(qmplist)
        self.btPrevious.pressed.disconnect()
        self.btNext.pressed.disconnect()
        self.btPrevious.pressed.connect(qmplist.previous)
        self.btNext.pressed.connect(qmplist.next)

    def on_about(self, _) -> None:
        dlg = QDialog(self, Qt.WindowType.Dialog)
        uic.loadUi(path.join(getcwd(), 'ui/about.ui'), dlg)
        dlg.exec_()
