import os
from json import dump
from glob import glob
from yandex_music.client import Client, Track
from yandex_music.track_short import TrackShort


class YaClient:
    __slots__ = ('_clt', 'likes', 'playlists')

    CODEC = 'mp3' # mp3, aac
    CACHE_DIR = f'{os.getcwd()}/.cache'
    TRACKS_DIR = f'{os.getcwd()}/.cache/tracks'
    COVERS_DIR = f'{os.getcwd()}/.cache/covers'

    def __init__(self, token):
        self._clt = Client(token).init()
        self.likes: list[Track] = []
        self.playlists: list[Track] = []

        os.makedirs(YaClient.TRACKS_DIR, exist_ok=True)

    def __get_codec(self, track: Track) -> tuple[str, int]:
        if track.download_info is None:
            track.get_download_info()

        return max(((di.codec, di.bitrate_in_kbps) for di in track.download_info if di.codec == YaClient.CODEC),
                   key=lambda x: x[1], default=('mp3', 192))

    def download_track(self, track: Track) -> None:
        _name = f'{", ".join(track.artists_name())} - {track.title}'
        _fname = f'{YaClient.TRACKS_DIR}/{_name}.{YaClient.CODEC}'
        if os.path.isfile(_fname):
            return

        print('Downloading track:', _name)
        track.download(_fname, *self.__get_codec(track))

        _fname = f'{YaClient.COVERS_DIR}/{_name}.png'
        if os.path.isfile(_fname):
            return

        track.download_og_image(_fname)

    def load_list(self, list_name: str, yalist: list[Track], kind: int|str=None):
        yalist.clear()
        _tracks = self._clt.users_likes_tracks().fetch_tracks() if list_name == 'likes' else \
            self._clt.users_playlists(kind).tracks
        for _tr in _tracks:
            if isinstance(_tr, TrackShort):
                _tr = _tr.track

            yalist.append(_tr)

        with open(f'{YaClient.CACHE_DIR}/tracks_{list_name.replace(" ", "_")}.json', 'w') as fh:
            dump([f'{_t.artists_name()} - {_t.title}' for _t in yalist], fh)

    def clear_cache(self):
        print(os.listdir(YaClient.TRACKS_DIR))
        for fn in glob(YaClient.TRACKS_DIR):
            os.remove(fn)

        for fn in glob(YaClient.COVERS_DIR):
            os.remove(fn)

        for fn in glob(YaClient.CACHE_DIR):
            os.remove(fn)
