# -*- coding: utf-8 -*-
"""Smartys IPTV — VOD (Filme) Liste."""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList

from .api import Credentials, XtreamApi, ApiError
from . import player as vlc_player


class VodListScreen(Screen):
    skin = """
        <screen position="center,center" size="720,480" title="Smartys IPTV — Filme">
            <widget name="list" position="20,20" size="680,440" />
        </screen>
    """

    def __init__(self, session, cfg):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.api = self._build_api()
        self.movies = []

        self["list"] = MenuList([])
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.play_movie, "cancel": self.close},
        )
        self.onLayoutFinish.append(self._load)

    def _build_api(self):
        providers = self.cfg.providers()
        if not providers:
            return None
        p = providers[0]
        return XtreamApi(Credentials(p["server_url"], p["username"], p["password"]))

    def _load(self):
        if not self.api:
            self["list"].setList([(_("Nicht verbunden"), None)])
            return
        try:
            movies = self.api.vod_streams()
        except ApiError as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self.movies = movies
        self["list"].setList([
            (m.get("name", "?"), m) for m in movies
        ])

    def play_movie(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        m = sel[1]
        stream_id = m.get("stream_id")
        ext = m.get("container_extension") or "mp4"
        url = self.api.creds.movie_url(stream_id, ext)
        vlc_player.play(self.session, url)
