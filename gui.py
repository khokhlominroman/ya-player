"""
YaPlayer main GUI module.
"""
from json import dump, load
from os import getcwd, path, remove as os_rm
from PyQt5 import uic
from PyQt5.QtCore import QItemSelection, QModelIndex, QPoint, Qt, QUrl, QSize
from PyQt5.QtGui import QCloseEvent, QPixmap
from PyQt5.QtWidgets import QHeaderView, QMainWindow, QDialog, QLabel, QMessageBox as Qmb, QMenu, QAction, QToolButton
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from yandex_music.exceptions import NetworkError
from yandex_music.track_short import TrackShort

from dlg_button import ButtonDelegate
from models.playlists import PlaylistsModel
from models.tracks import TracksModel
from yaclient import YaClient, Track

_APP_TITLE = 'Yandex player'


class YaPlayerWindow(QMainWindow):  # pylint: disable=too-many-instance-attributes
    """
    YaPlayer main GUI class.
    """
    def __init__(self) -> None:
        super().__init__(flags=Qt.WindowType.Window)
        uic.loadUi(path.join(getcwd(), 'ui/main.ui'), self)
        with open('./ui/style.qss', 'r', encoding='utf-8') as fh:
            self.setStyleSheet('\n'.join(fh.readlines()))

        with open('settings.json', 'r', encoding='utf-8') as fh:
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
        self.bt_play.pressed.connect(self.player.play)
        self.bt_pause.pressed.connect(self.player.pause)
        self.bt_stop.pressed.connect(self.player.stop)
        self.sld_vol.valueChanged.connect(self.player.setVolume)
        self.qmpl_tracks = QMediaPlaylist()
        self.qmpl_likes = QMediaPlaylist()
        self.qmpl_similar = QMediaPlaylist()
        self.player.setPlaylist(self.qmpl_tracks)

        # Models
        self.model_playlists = PlaylistsModel()
        self.model_tracks = TracksModel(self.qmpl_tracks, 4)
        self.model_likes = TracksModel(self.qmpl_likes, 3)
        self.lv_playlists.setModel(self.model_playlists)
        self.tv_tracks.setModel(self.model_tracks)
        self.tv_likes.setModel(self.model_likes)

        self.connect_signals()
        self.setup_ui()
        self.act_logout.setText("Login")

    def connect_signals(self):
        """
        Connect widgets' signals with slots.
        :return:
        """
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.bt_like.pressed.connect(self._like_track)
        self.bt_prev.pressed.connect(self.qmpl_tracks.previous)
        self.bt_next.pressed.connect(self.qmpl_tracks.next)
        self.qmpl_tracks.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.qmpl_likes.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.qmpl_similar.currentIndexChanged.connect(self.on_track_similar_changed)
        self.lv_playlists.selectionModel().selectionChanged.connect(self.on_playlist_selected)
        self.tv_tracks.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.tv_likes.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.tv_tracks.doubleClicked.connect(self.on_track_double_clicked)
        self.tv_likes.doubleClicked.connect(self.on_track_double_clicked)
        self.sld_time.valueChanged.connect(self.player.setPosition)
        self.dlg_tracks_del = ButtonDelegate(self.tv_tracks, 'Удалить')
        self.dlg_tracks_similar = ButtonDelegate(self.tv_tracks, 'Волна по треку')
        self.dlg_tracks_like = ButtonDelegate(self.tv_tracks, 'Добавить в коллекцию')
        self.dlg_likes_del = ButtonDelegate(self.tv_likes, 'Удалить')
        self.dlg_likes_similar = ButtonDelegate(self.tv_likes, 'Волна по треку')
        self.dlg_tracks_del.pressed.connect(self._delete_track)
        self.dlg_tracks_similar.pressed.connect(self._similar)
        self.dlg_tracks_like.pressed.connect(self._like_track)
        self.dlg_likes_del.pressed.connect(self._delete_track)
        self.dlg_likes_similar.pressed.connect(self._similar)
        self.act_update_likes.triggered.connect(self.__update_likes)
        self.act_about.triggered.connect(self.on_about)
        self.act_logout.triggered.connect(self.__logout)

    def setup_ui(self) -> None:
        """
        Table views and labels initialisatrion.
        :return:
        """
        for tv in (self.tv_tracks, self.tv_likes):
            tv.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            tv.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            tv.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)

        self.tv_tracks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tv_tracks.setItemDelegateForColumn(1, self.dlg_tracks_del)
        self.tv_tracks.setItemDelegateForColumn(2, self.dlg_tracks_similar)
        self.tv_tracks.setItemDelegateForColumn(3, self.dlg_tracks_like)
        self.tv_likes.setItemDelegateForColumn(1, self.dlg_likes_del)
        self.tv_likes.setItemDelegateForColumn(2, self.dlg_likes_similar)

        mbar = self.menuBar()
        self.lb_user = QLabel(mbar)
        mbar.setCornerWidget(self.lb_user, Qt.TopRightCorner)
        self.lb_user.setAlignment(Qt.AlignRight)
        self.lb_user.setMinimumWidth(int(self.size().width()/2))
        self.lb_user.setContentsMargins(1, 2, 4, 1)

        self.lbst = QLabel(self.status)
        self.status.addWidget(self.lbst)

        _px = QPixmap('./ui/images/track.png')
        self.lb_track_cover.setPixmap(_px)
        self.lb_likes_cover.setPixmap(_px)

        self.setAcceptDrops(True)

    def closeEvent(self, event: QCloseEvent) -> None:   # pylint: disable=invalid-name
        """
        YaPlayer main window close handler.
        :param event:
        :return:
        """
        if self.__yac is not None and self.__yac.clt.token:
            sz = self.size()
            pos = self.pos()
            settings = {'TOKEN': self.__yac.clt.token, 'size': (sz.width(), sz.height()),
                        'pos': (pos.x(), pos.y())}
            with open('settings.json', 'w', encoding='utf-8') as fh:
                dump(settings, fh)

        event.accept()

    def login(self) -> None:
        """
        Creates the YaClient instance with given token.
        Updates playlists list and likes list.
        :return:
        """
        _token = None
        if path.exists('settings.json'):
            with open('settings.json', 'r', encoding='utf-8') as fh:
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

        self.act_logout.setText("Выйти из аккаунта")
        self.lb_user.setText(f'{self.__yac.clt.me.account.full_name} | {self.__yac.clt.me.default_email} ')

        self.__update_playlists()
        self.__update_likes()

    def __logout(self) -> None:
        """
        Removes the token, clears file cache and removes the YaClient instance.
        :return:
        """
        self.qmpl_likes.clear()
        if path.exists('settings.json'):
            os_rm('settings.json')
            im = QPixmap('./images/track.png')
            self.lb_likes_cover.setPixmap(im)
            self.lb_track_cover.setPixmap(im)
            self.actionLog_Out.setText('Залогиниться')
            self.acc_name.setText('')
            self.__yac.clear_cache()
            self.__yac = None
            self.is_logged = False
        else:
            Qmb.critical(self, _APP_TITLE, 'You are not logged in')

    def _like_track(self, row: int=None):
        if self.__yac is None:
            Qmb.critical(self, _APP_TITLE, 'You are not logged in')
            return

        if row is None:
            _pl = self.__yac.playlist if self.player.playlist() is self.qmpl_tracks else self.__yac.similar
            _tr = _pl[self.player.playlist().currentIndex()]
        else:
            _tr = self.__yac.playlist[row]

        try:
            if _tr.like():
                self.lbst.setText(f'Track `{_tr.title}` liked')
            else:
                Qmb.warning(self, _APP_TITLE, 'Не получается поставить лайк')
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
                self.qmpl_similar.clear()
                for _tr in self.__yac.similar:
                    self.qmpl_similar.addMedia(QMediaContent(
                        QUrl(f'file://{YaClient.TRACKS_DIR}/{", ".join(_tr.artists_name())} - '
                             f'{_tr.title}.{YaClient.CODEC}')))

                self.player.setPlaylist(self.qmpl_similar)
                self.bt_prev.pressed.disconnect()
                self.bt_next.pressed.disconnect()
                self.bt_prev.pressed.connect(self.qmpl_similar.previous)
                self.bt_next.pressed.connect(self.qmpl_similar.next)
                self.qmpl_similar.setCurrentIndex(0)
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
            sel = self.lv_playlists.selectionModel().selection()
            pl_row = sel.indexes()[0].row()
            _pl = self.model_playlists.rows[pl_row]
            _list = self.__yac.playlist
            track = self.__yac.playlist[row]
            try:
                _updated = self.__yac.clt.users_playlists_delete_track(_pl[1], row, row+1, _pl[2])
                if _updated is None:
                    return

                self.model_playlists.rows[pl_row] = (_pl[0], _pl[1], _updated.revision)
                if len(_updated.tracks) > 0:
                    _list.clear()
                    for _tr in _updated.tracks:
                        if isinstance(_tr, TrackShort):
                            _tr = _tr.track

                        _list.append(_tr)
                else:
                    self.on_playlist_selected(sel)
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

        add_menu = QMenu(self.bt_add_to_list)
        for _i, _pl in enumerate(self.model_playlists.rows):
            act = QAction(_pl[0], self)
            act.triggered.connect(lambda checked, pl_idx=_i: self.__add_to_list(pl_idx))
            add_menu.addAction(act)

        self.bt_add_to_list.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.bt_add_to_list.setMenu(add_menu)
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

        self.__update_media(self.model_likes, self.qmpl_likes, self.__yac.likes)
        self.lbst.setText('Likes updated')

    def __update_media(self, model: TracksModel, playlist: QMediaPlaylist, tracks: list[Track]) -> None:
        if not self.is_logged:
            return

        playlist.clear()
        for _tr in tracks:
            playlist.addMedia(QMediaContent(
                QUrl(f'file://{YaClient.TRACKS_DIR}/{", ".join(_tr.artists_name())} - {_tr.title}.{YaClient.CODEC}')))

        model.layoutChanged.emit()

    def __add_to_list(self, pl_idx: int) -> None:
        curr_pl = self.player.playlist()
        idx = curr_pl.currentIndex()
        if idx == -1:
            return

        plist = self.model_playlists.rows[pl_idx]
        if curr_pl is self.qmpl_tracks:
            track_list = self.__yac.playlist
            curr_pl_name = self.model_playlists.data(self.lv_playlists.currentIndex(), 0)
            if curr_pl_name == plist[0]:
                return
        elif curr_pl is self.qmpl_similar:
            track_list = self.__yac.similar
        elif curr_pl is self.qmpl_likes:
            track_list = self.__yac.likes
        else:
            return

        track = track_list[idx]
        try:
            new_pl = self.__yac.clt.users_playlists_insert_track(plist[1], track.id, track.albums[0].id,
                                                                 revision=plist[2])
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        if new_pl is not None:
            self.model_playlists.rows[pl_idx] = (plist[0], plist[1], new_pl.revision)

        self.lbst.setText(f'`{track.title}` added to `{plist[0]}`')

    def update_duration(self, duration: int) -> None:
        """
        Update slider maximum and total time label.
        :param duration:
        :return:
        """
        self.sld_time.setMaximum(duration)
        if duration >= 0:
            self.lb_time_total.setText(f'{duration//60000}:{duration%60000//1000:02d}')

    def update_position(self, position: int) -> None:
        """
        Update time slider position.
        :param position:
        :return:
        """
        if position >= 0:
            self.lb_time_current.setText(f'{position//60000}:{position%60000//1000:02d}')

        # Disable the events to prevent update triggering a setPosition event (can cause stuttering).
        self.sld_time.blockSignals(True)
        self.sld_time.setValue(position)
        self.sld_time.blockSignals(False)

    def on_playlist_selected(self, sel: QItemSelection, _=None) -> None:
        """
        Update track list and tracks data of selected playlist.
        :param sel:
        :param _:
        :return:
        """
        _pl = self.model_playlists.rows[sel.indexes()[0].row()]
        try:
            self.__yac.load_list(_pl[0], _pl[1])
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.__update_media(self.model_tracks, self.qmpl_tracks, self.__yac.playlist)
        self.lbst.setText(f'{_pl[0]} updated')

    def on_track_selected(self, curr: QItemSelection, prev: QItemSelection) -> None:
        """
        Update labels and buttons when track is selected.
        :param curr:
        :param prev:
        :return:
        """
        if curr.isEmpty():
            return

        self.lbst.setText('')

        row = curr.indexes()[0].row()
        if self.currtab_idx == 0:
            view = self.tv_tracks
            model = self.model_tracks
            cover = self.lb_track_cover
            title = self.lb_track_title
            track = self.__yac.playlist[row]
        elif self.currtab_idx == 1:
            view = self.tv_likes
            model = self.model_likes
            cover = self.lb_likes_cover
            title = self.lb_likes_title
            track = self.__yac.likes[row]
        else:
            return

        artists = ", ".join(track.artists_name())
        cover_name = f'{artists} - {track.title}'.replace('/', '\\')
        cover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{cover_name}.png'))
        album = f'{track.albums[0].title} [{track.albums[0].year}]' if len(track.albums) > 0 else ''
        duration = f'{track.duration_ms//60000}:{track.duration_ms%60000//1000:02d}'
        title.setText(f'<b>{artists}</b><br><br>{track.title} [<b>{duration}</b>]<br><br><b>Альбом</b><br>{album}')
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
        """
        Start to play the track when one has been double clicked.
        :param idx:
        :return:
        """
        if not idx.isValid():
            return

        if self.currtab_idx == 0:
            qmpl = self.qmpl_tracks
            view = self.tv_tracks
        elif self.currtab_idx == 1:
            qmpl = self.qmpl_likes
            view = self.tv_likes
        else:
            return

        qmpl.setCurrentIndex(idx.row())
        self.player.play()
        view.setCurrentIndex(idx)

    def on_track_selected_qmpl(self, idx: int) -> None:
        """
        Update labels when track changed at QMediaPlaylist.
        :param idx:
        :return:
        """
        if idx < 0:
            return

        if self.currtab_idx == 0:
            track = self.__yac.playlist[idx]
            view = self.tv_tracks
            model = self.model_tracks
        elif self.currtab_idx == 1:
            track = self.__yac.likes[idx]
            view = self.tv_likes
            model = self.model_likes
        else:
            return

        try:
            self.__yac.download_track(track)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        track_name = f'{", ".join(track.artists_name())} - {track.title}'.replace('/', '\\')
        self.lb_curr_cover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{track_name}.png'))
        self.lb_curr_title.setText(track_name)
        view.setCurrentIndex(model.index(idx, 2))

    def on_track_similar_changed(self, idx: int) -> None:
        """
        Update labels when track changed at QMediaPlaylist.
        :param idx:
        :return:
        """
        track = self.__yac.similar[idx]
        try:
            self.__yac.download_track(track)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        track_name = f'{", ".join(track.artists_name())} - {track.title}'.replace('/', '\\')
        self.lb_curr_cover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{track_name}.png'))
        self.lb_curr_title.setText(track_name)

    def on_tab_changed(self, ix: int) -> None:
        """
        Change the playlist when other tab has been selected.
        :param ix:
        :return:
        """
        self.currtab_idx = ix
        if ix == 0:
            qmplist = self.qmpl_tracks
            self.__update_playlists()
        elif ix == 1:
            qmplist = self.qmpl_likes
            self.__update_likes()
        else:
            return

        self.player.setPlaylist(qmplist)
        self.bt_prev.pressed.disconnect()
        self.bt_next.pressed.disconnect()
        self.bt_prev.pressed.connect(qmplist.previous)
        self.bt_next.pressed.connect(qmplist.next)

    def on_about(self, _) -> None:
        """
        About dialog exec.
        :param _:
        :return:
        """
        dlg = QDialog(self, Qt.WindowType.Dialog)
        uic.loadUi(path.join(getcwd(), 'ui/about.ui'), dlg)
        dlg.exec_()
