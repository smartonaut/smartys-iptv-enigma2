# -*- coding: utf-8 -*-
"""Smartys IPTV — Hauptmenü-Screen (Vollbild, alle Auflösungen)."""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from .config import Config
from . import theme


class MainMenuScreen(Screen):
    def __init__(self, session):
        self.skin = theme.build_skin("SmartysMainMenu")
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        self["header"] = Label(_("Menü"))
        self["subtitle"] = Label(_("Live-TV · Filme · Serien"))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.ok,
                "cancel": self.close,
            },
        )
        self.onLayoutFinish.append(self._refresh)

    def _refresh(self):
        paired = bool(self.cfg.providers())
        entries = [
            (_("Live-TV"), self.open_live),
            (_("Filme (VOD)"), self.open_vod),
            (_("Serien"), self.open_series),
            (_("Einstellungen / Pairing"), self.open_settings),
        ]
        self["list"].setList([(label, fnc) for label, fnc in entries])
        self["status"].setText(
            _("Verbunden") if paired else _("Nicht verbunden — bitte pairen"))

    def ok(self):
        sel = self["list"].getCurrent()
        if sel:
            sel[1]()

    def open_live(self):
        from .channellist import LiveListScreen
        self.session.open(LiveListScreen, self.cfg)

    def open_vod(self):
        from .vodlist import VodListScreen
        self.session.open(VodListScreen, self.cfg)

    def open_series(self):
        from .serieslist import SeriesListScreen
        self.session.open(SeriesListScreen, self.cfg)

    def open_settings(self):
        from .pairing import PairingScreen
        self.session.open(PairingScreen)
