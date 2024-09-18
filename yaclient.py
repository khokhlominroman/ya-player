import os
from json import dump
from glob import glob
from yandex_music.client import Client, Track
from yandex_music.track_short import TrackShort


class YaClient:
    __slots__ = ('clt', 'likes', 'playlist', 'similar')

    CODEC = 'mp3' # mp3, aac
    CACHE_DIR = f'{os.getcwd()}/.cache'
    TRACKS_DIR = f'{os.getcwd()}/.cache/tracks'
    COVERS_DIR = f'{os.getcwd()}/.cache/covers'

    def __init__(self, token):
        self.clt = Client(token).init()
        self.likes: list[Track] = []
        self.playlist: list[Track] = []
        self.similar: list[Track] = []

        os.makedirs(YaClient.TRACKS_DIR, exist_ok=True)

    @staticmethod
    def __get_codec(track: Track) -> tuple[str, int]:
        if track.download_info is None:
            track.get_download_info()

        return max(((di.codec, di.bitrate_in_kbps) for di in track.download_info if di.codec == YaClient.CODEC),
                   key=lambda x: x[1], default=('mp3', 192))

    def download_track(self, track: Track) -> None:
        _name = f'{", ".join(track.artists_name())} - {track.title}'
        _fname = f'{YaClient.COVERS_DIR}/{_name}.png'
        if not os.path.isfile(_fname):
            track.download_og_image(_fname)

        _fname = f'{YaClient.TRACKS_DIR}/{_name}.{YaClient.CODEC}'
        if not os.path.isfile(_fname):
            print('Downloading track:', _name)
            track.download(_fname, *self.__get_codec(track))

    def load_list(self, list_name: str, kind: int | str=None) -> None:
        if list_name == 'likes':
            _list = self.likes
            _tracks = self.clt.users_likes_tracks().fetch_tracks()
        else:
            _list = self.playlist
            _tracks = self.clt.users_playlists(kind).tracks

        self.update_playlist(list_name, _list, _tracks)

    def load_similar(self, track_id: int | str) -> bool:
        self.similar.clear()
        res = self.clt.tracks_similar(track_id)
        if len(res.similar_tracks) > 0:
            self.similar = res.similar_tracks

        return len(self.similar) != 0

    def update_playlist(self, list_name: str, plist: list[Track], tracks: list[Track | TrackShort]):
        plist.clear()
        for _tr in tracks:
            if isinstance(_tr, TrackShort):
                _tr = _tr.track

            plist.append(_tr)

        with open(f'{YaClient.CACHE_DIR}/tracks_{list_name.replace(" ", "_")}.json', 'w') as fh:
            dump([f'{_t.artists_name()} - {_t.title}' for _t in plist], fh)


    @staticmethod
    def clear_cache() -> None:
        print(os.listdir(YaClient.TRACKS_DIR))
        for fn in glob(YaClient.TRACKS_DIR):
            os.remove(fn)

        for fn in glob(YaClient.COVERS_DIR):
            os.remove(fn)

        for fn in glob(YaClient.CACHE_DIR):
            os.remove(fn)
