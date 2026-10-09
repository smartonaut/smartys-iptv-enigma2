# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste."""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList

from .config import Config
from .api import Credentials, XtreamApi, ApiError
from . import player as vlc_player


class LiveListScreen(Screen):
    skin = """
        <screen position="center,center" size="720,480" title="Smartys IPTV — Live-TV">
            <widget name="list" position="20,20" size="680,440" />
        </screen>
    """

    def __init__(self, session, cfg):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg

        self.api = self._build_api()
        self.channels = []

        self["list"] = MenuList([])
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.play_channel, "cancel": self.close},
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
            streams = self.api.live_streams()
        except ApiError as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self.channels = streams
        self["list"].setList([
            (s.get("name", "?"), s) for s in streams
        ])

    def play_channel(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        ch = sel[1]
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")
        vlc_player.play(self.session, url)
