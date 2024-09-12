from json import load
from os import getcwd, path, remove as os_rm
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, QItemSelection, QModelIndex, Qt, QSize, QUrl
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QHeaderView, QMainWindow, QFileDialog, QLabel, QMessageBox as Qmb
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist
from PyQt5.QtMultimediaWidgets import QVideoWidget
from yandex_music.exceptions import NetworkError

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

        #
        # Yandex client
        #
        self.is_logged = False
        self.__yac: YaClient = None

        #
        # GUI
        #
        # self.tvTrackList = QTableView()
        self.tvTrackList.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.tvTrackList.horizontalHeader().setStretchLastSection(True)
        self.tvTrackList.setColumnWidth(0, 25)
        self.tvTrackList.setColumnWidth(1, 25)
        self.delegate_del = ButtonDelegate(self.tvTrackList, 'del')
        self.delegate_like = ButtonDelegate(self.tvTrackList, 'like')
        self.tvTrackList.setItemDelegateForColumn(0, self.delegate_del)
        self.tvTrackList.setItemDelegateForColumn(1, self.delegate_like)

        self.currtab_idx = 0
        mbar = self.menuBar()
        self.lbUser = QLabel(mbar)
        mbar.setCornerWidget(self.lbUser, Qt.TopRightCorner)
        self.lbUser.setAlignment(Qt.AlignRight)
        self.lbUser.setMinimumWidth(int(self.size().width()/3))
        self.lbUser.setContentsMargins(1, 2, 4, 1)

        self.lbst = QLabel(self.statusBar)
        self.statusBar.addWidget(self.lbst)

        #
        # Player
        #
        self.player = QMediaPlayer(self)
        self.player.error.connect(lambda err: Qmb.critical(self, 'Error', str(err)))
        self.player.durationChanged.connect(self.update_duration)
        self.player.positionChanged.connect(self.update_position)
        self.playButton.pressed.connect(self.player.play)
        self.pauseButton.pressed.connect(self.player.pause)
        self.stopButton.pressed.connect(self.player.stop)
        self.volumeSlider.valueChanged.connect(self.player.setVolume)
        self.qmplTracks = QMediaPlaylist()
        self.qmplLikes = QMediaPlaylist()
        self.player.setPlaylist(self.qmplTracks)

        #
        # Models
        #
        self.model_playlists = PlaylistsModel()
        self.model_tracks = TracksModel(self.qmplTracks)
        self.model_likes = TracksModel(self.qmplLikes)
        self.lvPlaylists.setModel(self.model_playlists)
        self.tvTrackList.setModel(self.model_tracks)
        self.lvLikedList.setModel(self.model_likes)

        #
        # Signals
        #
        self.tabWidget.currentChanged.connect(self.on_tab_changed)
        self.previousButton.pressed.connect(self.qmplTracks.previous)
        self.nextButton.pressed.connect(self.qmplTracks.next)
        self.qmplTracks.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.qmplLikes.currentIndexChanged.connect(self.on_track_selected_qmpl)
        self.lvPlaylists.selectionModel().selectionChanged.connect(self.on_playlist_selected)
        self.tvTrackList.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.lvLikedList.selectionModel().selectionChanged.connect(self.on_track_selected)
        self.tvTrackList.doubleClicked.connect(self.on_track_double_clicked)
        self.lvLikedList.doubleClicked.connect(self.on_track_double_clicked)
        self.timeSlider.valueChanged.connect(self.player.setPosition)

        self.viewButton.toggled.connect(self.toggle_viewer)
        self.actUpdateLikes.triggered.connect(self.__update_liked)
        self.actLogout.triggered.connect(self.__logout)

        self.setAcceptDrops(True)

        _px = QPixmap(f'./ui/images/image.png')
        self.lbTrackCover.setPixmap(_px)
        self.lbLikedCover.setPixmap(_px)
        self.actLogout.setText("Login")

        self.show()
        self.__login()

    def dragEnterEvent(self, e) -> None:
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e) -> None:
        for url in e.mimeData().urls():
            self.qmplLikes.addMedia(QMediaContent(url))

        self.model.layoutChanged.emit()

        # If not playing, seeking to first of newly added + play.
        if self.player.state() != QMediaPlayer.PlayingState:
            i = self.qmplLikes.mediaCount() - len(e.mimeData().urls())
            self.qmplLikes.setCurrentIndex(i)
            self.player.play()

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open file", "", "mp3 Audio (*.mp3);mp4 Video (*.mp4);Movie files (*.mov);All files (*.*)")

        if path:
            self.qmplLikes.addMedia(QMediaContent(QUrl.fromLocalFile(path)))

        self.model.layoutChanged.emit()

    def __login(self) -> None:
        _token= None
        if path.exists('settings.json'):
            with open('settings.json', 'r') as fp:
                _token = load(fp).get('TOKEN')

        if not _token:
            Qmb.critical(self, _APP_TITLE, 'You should get a token.\n'
                                           'See https://yandex-music.readthedocs.io/en/main/token.html')
            return

        try:
            self.__yac = YaClient(_token)
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.is_logged = self.__yac._clt.me is not None
        self.actLogout.setText("Выйти из аккаунта")
        self.lbUser.setText(f'{self.__yac._clt.me.account.full_name} | {self.__yac._clt.me.default_email} ')

        self.__update_playlists()
        self.__update_liked()

    def __logout(self) -> None:
        self.qmplLikes.clear()
        if path.exists("settings.json"):
            os_rm("settings.json")
            im = QPixmap(f"./images/image.png")
            self.lbLikedCover.setPixmap(im)
            self.lbTrackCover.setPixmap(im)
            self.actionLog_Out.setText("Войти в аккаунт")
            self.acc_name.setText("")
            self.__yac.clear_cache()
            self.__yac = None
            self.is_logged = False
        else:
            # QMessageBox.critical(
            #     self, "Update Error", "You are not logged in", defaultButton=QMessageBox.Ok)
            self.__login()

    def __update_playlists(self) -> None:
        if self.__yac is None:
            Qmb.critical(self, "Update Error", "You are not logged in", defaultButton=Qmb.Ok)
            return

        try:
            self.model_playlists.update_data(self.__yac._clt.users_playlists_list())
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.lbst.setText('Playlists updated')

    def __update_liked(self) -> None:
        if not self.is_logged:
            Qmb.critical(self, "Update Error", "You are not logged in", defaultButton=Qmb.Ok)
            return

        try:
            self.__yac.load_list('likes', self.__yac.likes)
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

    def update_duration(self, duration) -> None:
        self.timeSlider.setMaximum(duration)
        if duration >= 0:
            self.totalTimeLabel.setText(f'{duration//60000}:{duration%60000//1000:02d}')

    def update_position(self, position) -> None:
        if position >= 0:
            self.currentTimeLabel.setText(f'{position//60000}:{position%60000//1000:02d}')

        # Disable the events to prevent update triggering a setPosition event (can cause stuttering).
        self.timeSlider.blockSignals(True)
        self.timeSlider.setValue(position)
        self.timeSlider.blockSignals(False)

    def on_playlist_selected(self, idx: QModelIndex, _) -> None:
        _pl = self.model_playlists._rows[idx.indexes()[0].row()]
        try:
            self.__yac.load_list(_pl[0], self.__yac.playlists, _pl[1])
        except NetworkError as e:
            Qmb.critical(self, _APP_TITLE, f'Error:\n{e}')
            return

        self.__update_media(self.model_tracks, self.qmplTracks, self.__yac.playlists)
        self.lbst.setText(f'{_pl[0]} updated')

    def on_track_selected(self, curr: QItemSelection, prev: QItemSelection) -> None:
        if curr.isEmpty():
            return

        row = curr.indexes()[0].row()
        if self.currtab_idx == 0:
            cover = self.lbTrackCover
            title = self.lbTrackTitle
            track = self.__yac.playlists[row]
        elif self.currtab_idx == 1:
            cover = self.lbLikedCover
            title = self.lbLikedTitle
            track = self.__yac.likes[row]
        else:
            return

        artists = ", ".join(track.artists_name())
        cover_name = f'{artists} - {track.title}'.replace('/', '\\')
        cover.setPixmap(QPixmap(f'{YaClient.COVERS_DIR}/{cover_name}.png'))
        album = f'{track.albums[0].title} [{track.albums[0].year}]' if len(track.albums) > 0 else ''
        duration = f'{track.duration_ms//60000}:{track.duration_ms%60000//1000:02d}'
        title.setText(f'<b>{artists}</b><br><br>{track.title} [<b>{duration}</b>]<br><br><b>Альлбом</b><br>{album}')
        self.tvTrackList.openPersistentEditor(self.model_tracks.index(row, 0))
        self.tvTrackList.openPersistentEditor(self.model_tracks.index(row, 1))

        if not prev.isEmpty():
            row = prev.indexes()[0].row()
            self.tvTrackList.closePersistentEditor(self.model_tracks.index(row, 0))
            self.tvTrackList.closePersistentEditor(self.model_tracks.index(row, 1))

    def on_track_double_clicked(self, idx: QModelIndex) -> None:
        if not idx.isValid():
            return

        if self.currtab_idx == 0:
            qmpl = self.qmplTracks
            view = self.tvTrackList
        elif self.currtab_idx == 1:
            qmpl = self.qmplLikes
            view = self.lvLikedList
        else:
            return

        qmpl.setCurrentIndex(idx.row())
        self.player.play()
        view.setCurrentIndex(idx)

    def on_track_selected_qmpl(self, idx: int) -> None:
        if idx < 0:
            return

        if self.currtab_idx == 0:
            track = self.__yac.playlists[idx]
            view = self.tvTrackList
            model = self.model_tracks
        elif self.currtab_idx == 1:
            track = self.__yac.likes[idx]
            view = self.lvLikedList
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

    def on_tab_changed(self, ix: int) -> None:
        self.currtab_idx = ix
        if ix == 0:
            qmplist = self.qmplTracks
        elif ix == 1:
            qmplist = self.qmplLikes
        else:
            return

        self.player.setPlaylist(qmplist)
        self.previousButton.pressed.disconnect()
        self.nextButton.pressed.disconnect()
        self.previousButton.pressed.connect(qmplist.previous)
        self.nextButton.pressed.connect(qmplist.next)

    def toggle_viewer(self, state):
        if state:
            self.viewer.show()
        else:
            self.viewer.hide()
