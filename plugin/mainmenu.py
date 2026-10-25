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
            tasten=[(theme.TASTE_OK, "OK", "Auswahl"), (None, "EXIT", "Beenden")])
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
        locked = self.cfg.is_locked()
        entries = []
        # Der Demo-Einstieg ist nur für Nutzer OHNE Line sinnvoll. Mit
        # hinterlegter Line wäre er ein irreführender Umweg.
        if not paired:
            entries.append((_("▶ Im Demo-Modus starten"), self.open_demo))
        entries += [
            (_("Live-TV"), self.open_live),
            (_("Filme (VOD)"), self.open_vod),
            (_("Serien"), self.open_series),
            (_("Suche"), self.open_search),
            (_("Timer-Aufnahmen"), self.open_timers),
            (_("Einstellungen"), self.open_prefs),
            (_("Line lokal eingeben"), self.open_line_entry),
            (_("Pairing"), self.open_settings),
        ]
        self["list"].setList([(label, fnc) for label, fnc in entries])
        if locked:
            self["status"].setText(_("Gesperrt — Sicherheits-Passwort eingeben"))
        elif paired:
            self["status"].setText(_("Verbunden · Line verschlüsselt gespeichert"))
        else:
            self["status"].setText(
                _("Demo-Modus — öffentliche Sender (ohne Line)"))

    def ok(self):
        sel = self["list"].getCurrent()
        if sel:
            sel[1]()

    def _unlock_or(self, target):
        """Öffnet den Entsperren-Screen, wenn die Line verschlüsselt+gesperrt ist."""
        if self.cfg.is_locked():
            from .lineentry import UnlockScreen
            self.session.open(UnlockScreen, target=target)
            return True
        return False

    def open_demo(self):
        # Direkter Einstieg in den Demo-Modus (legale öffentliche Sender).
        from .demo import DemoListScreen
        self.session.open(DemoListScreen, self.cfg)

    def open_live(self):
        if self._unlock_or("live"):
            return
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
        if self._unlock_or("vod"):
            return
        from .categories import CategoryListScreen
        from .vodlist import VodListScreen
        self.session.open(
            CategoryListScreen, self.cfg, "vod_categories",
            VodListScreen, "Filme", "Video-on-Demand")

    def open_series(self):
        if self._unlock_or("series"):
            return
        from .categories import CategoryListScreen
        from .serieslist import SeriesListScreen
        self.session.open(
            CategoryListScreen, self.cfg, "series_categories",
            SeriesListScreen, "Serien", "Staffeln & Episoden")

    def open_search(self):
        if self._unlock_or("search"):
            return
        from .search import SearchScreen
        self.session.open(SearchScreen, self.cfg)

    def open_timers(self):
        from .timerlist import TimerListScreen
        self.session.open(TimerListScreen)

    def open_settings(self):
        from .pairing import PairingScreen
        self.session.open(PairingScreen)

    def open_line_entry(self):
        from .lineentry import LineEntryScreen
        self.session.open(LineEntryScreen)

    def open_prefs(self):
        from .settings import SettingsScreen
        self.session.open(SettingsScreen)
