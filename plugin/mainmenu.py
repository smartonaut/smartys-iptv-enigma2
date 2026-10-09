# -*- coding: utf-8 -*-
"""Smartys IPTV — Hauptmenü-Screen."""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from .config import Config
from .pairing import PairingScreen


class MainMenuScreen(Screen):
    skin = """
        <screen position="center,center" size="560,420" title="Smartys IPTV">
            <widget name="menu" position="20,20" size="520,340" />
            <widget name="status" position="20,370" size="520,30" font="Regular;18" halign="center" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        self["menu"] = MenuList([])
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
        self["menu"].setList([(label, fnc) for label, fnc in entries])
        self["status"].setText(
            _("Verbunden") if paired else _("Nicht verbunden — bitte pairen"))

    def ok(self):
        sel = self["menu"].getCurrent()
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
        self.session.open(PairingScreen)
