# -*- coding: utf-8 -*-
"""Smartys IPTV — Serienliste (Serien → Staffeln → Episoden)."""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList

from .api import Credentials, XtreamApi, ApiError
from . import player as vlc_player


class SeriesListScreen(Screen):
    skin = """
        <screen position="center,center" size="720,480" title="Smartys IPTV — Serien">
            <widget name="list" position="20,20" size="680,440" />
        </screen>
    """

    def __init__(self, session, cfg):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.api = self._build_api()
        self.series = []

        self["list"] = MenuList([])
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.open_series, "cancel": self.close},
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
            series = self.api.series_streams()
        except ApiError as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self.series = series
        self["list"].setList([
            (s.get("name", "?"), s) for s in series
        ])

    def open_series(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        s = sel[1]
        series_id = s.get("series_id")
        self.session.open(EpisodeListScreen, self.api, series_id)


class EpisodeListScreen(Screen):
    skin = """
        <screen position="center,center" size="720,480" title="Episoden">
            <widget name="list" position="20,20" size="680,440" />
        </screen>
    """

    def __init__(self, session, api, series_id):
        Screen.__init__(self, session)
        self.session = session
        self.api = api
        self.series_id = series_id
        self.episodes = []

        self["list"] = MenuList([])
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.play_episode, "cancel": self.close},
        )
        self.onLayoutFinish.append(self._load)

    def _load(self):
        try:
            info = self.api.series_info(self.series_id)
        except ApiError as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        # info: {"seasons": [...], "episodes": {season: [...]}, ...}
        eps = info.get("episodes") or {}
        # Flache Liste aller Episoden über alle Staffeln
        flat = []
        for season, ep_list in eps.items():
            for ep in ep_list:
                ep = dict(ep)
                ep["_season"] = season
                flat.append(ep)
        self.episodes = flat
        self["list"].setList([
            ("S%sE%s — %s" % (
                e.get("_season", "?"),
                e.get("episode_num", "?"),
                e.get("title") or ""), e)
            for e in flat
        ])

    def play_episode(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        ep = sel[1]
        ep_id = ep.get("id")
        ext = ep.get("container_extension") or "mp4"
        url = self.api.creds.series_url(ep_id, ext)
        vlc_player.play(self.session, url)
