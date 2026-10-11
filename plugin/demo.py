# -*- coding: utf-8 -*-
"""Smartys IPTV — Demo-Modus.

Zeigt ausschließlich legale, öffentlich-rechtliche Sender (SD, nicht HD),
damit Interessenten den Player ohne eigene Line testen können.

Wichtig: Hier dürfen NUR frei zugängliche, legale Sender-Streams stehen —
keine privaten Lines, keine Xtream-Credentials, keine HD-Premium-Varianten.
"""

from .screens_base import BaseListScreen
from . import player as vlc_player

# Legale öffentlich-rechtliche Livestreams (SD — "med"-Varianten, nicht HD).
DEMO_CHANNELS = [
    {"name": "Das Erste", "url": "https://daserste-live.ard-mcdn.de/daserste/live/hls/de/master.m3u8"},
    {"name": "ZDF", "url": "https://zdf-hls-15.akamaized.net/hls/live/2016498/de/med/master.m3u8"},
    {"name": "3sat", "url": "https://zdf-hls-18.akamaized.net/hls/live/2016501/dach/med/master.m3u8"},
    {"name": "ARTE", "url": "https://artesimulcast.akamaized.net/hls/live/2030993/artelive_de/master.m3u8"},
    {"name": "phoenix", "url": "https://zdf-hls-19.akamaized.net/hls/live/2016502/de/med/master.m3u8"},
    {"name": "tagesschau24", "url": "https://tagesschau.akamaized.net/hls/live/2020115/tagesschau/tagesschau_1/master.m3u8"},
    {"name": "KiKA", "url": "https://kikageohls.akamaized.net/hls/live/2022693/livetvkika_de/master.m3u8"},
    {"name": "one", "url": "https://mcdn-one.ard.de/ardone/hls/master.m3u8"},
    {"name": "ZDFneo", "url": "https://zdf-hls-16.akamaized.net/hls/live/2016499/de/med/master.m3u8"},
    {"name": "ZDFinfo", "url": "https://zdf-hls-17.akamaized.net/hls/live/2016500/de/med/master.m3u8"},
]


class DemoListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Demo-Modus"
    subtitle_text = "Öffentlich-rechtliche Sender (legal)"
    footer = "OK = Abspielen   ·   EXIT = Zurück"

    def _build_api(self):
        # Demo braucht kein Xtream-API — Sender kommen direkt aus DEMO_CHANNELS.
        return None

    def _load(self):
        items = [(ch["name"], ch) for ch in DEMO_CHANNELS]
        self["list"].setList(items)
        self["status"].setText(
            _("%d Sender — ohne Line testen") % len(DEMO_CHANNELS))

    def _on_select(self, item):
        vlc_player.open_player(self.session, item["url"], name=item["name"])
