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
        self.skin = theme.build_skin(
            "SmartysMainMenu",
            footer="OK = Auswahl   ·   EXIT = Beenden")
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
            (_("▶ Im Demo-Modus starten"), self.open_demo),
            (_("Live-TV"), self.open_live),
            (_("Filme (VOD)"), self.open_vod),
            (_("Serien"), self.open_series),
            (_("Timer-Aufnahmen"), self.open_timers),
            (_("Einstellungen"), self.open_prefs),
            (_("Pairing"), self.open_settings),
        ]
        self["list"].setList([(label, fnc) for label, fnc in entries])
        self["status"].setText(
            _("Verbunden") if paired
            else _("Demo-Modus — öffentliche Sender (ohne Line)"))

    def ok(self):
        sel = self["list"].getCurrent()
        if sel:
            sel[1]()

    def open_demo(self):
        # Direkter Einstieg in den Demo-Modus (legale öffentliche Sender).
        from .demo import DemoListScreen
        self.session.open(DemoListScreen, self.cfg)

    def open_live(self):
        if not self.cfg.providers():
            # Demo-Modus: legale öffentliche Sender, damit man ohne Line testet.
            from .demo import DemoListScreen
            self.session.open(DemoListScreen, self.cfg)
            return
        from .categories import CategoryListScreen
        from .channellist import LiveListScreen
        self.session.open(
            CategoryListScreen, self.cfg, "live_categories",
            LiveListScreen, "Live-TV", "Sender wählen")

    def open_vod(self):
        from .categories import CategoryListScreen
        from .vodlist import VodListScreen
        self.session.open(
            CategoryListScreen, self.cfg, "vod_categories",
            VodListScreen, "Filme", "Video-on-Demand")

    def open_series(self):
        from .categories import CategoryListScreen
        from .serieslist import SeriesListScreen
        self.session.open(
            CategoryListScreen, self.cfg, "series_categories",
            SeriesListScreen, "Serien", "Staffeln & Episoden")

    def open_timers(self):
        from .timerlist import TimerListScreen
        self.session.open(TimerListScreen)

    def open_settings(self):
        from .pairing import PairingScreen
        self.session.open(PairingScreen)

    def open_prefs(self):
        from .settings import SettingsScreen
        self.session.open(SettingsScreen)
