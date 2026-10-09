# -*- coding: utf-8 -*-
"""Smartys IPTV — gemeinsame Basisklasse für Listen-Screens.

Jeder Listen-Screen: Vollbild, Logo, Header, Untertitel, Liste, Status.
Der Skin wird zur Laufzeit auf die aktuelle OSD-Auflösung skaliert.
"""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from .api import Credentials, XtreamApi
from . import theme


class BaseListScreen(Screen):
    """Basis für Live-TV / VOD / Serien-Listen."""

    screen_name = "SmartysList"
    header_text = ""
    subtitle_text = ""

    def __init__(self, session, cfg):
        self.skin = theme.build_skin(self.screen_name)
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg

        self.api = self._build_api()

        self["header"] = Label(_(self.header_text))
        self["subtitle"] = Label(_(self.subtitle_text))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.on_select, "cancel": self.close},
        )
        self.onLayoutFinish.append(self._load)

    def _build_api(self):
        providers = self.cfg.providers()
        if not providers:
            return None
        p = providers[0]
        return XtreamApi(Credentials(p["server_url"], p["username"], p["password"]))

    # --- von Unterklassen zu implementieren ---

    def _fetch(self):
        """Lädt die Einträge; liefert (liste_von_dicts, status_text) oder wirft ApiError."""
        raise NotImplementedError

    def _on_select(self, item):
        """Wird bei OK auf einen Eintrag gerufen."""
        raise NotImplementedError

    # --- gemeinsam ---

    def _load(self):
        if not self.api:
            self["list"].setList([(_("Nicht verbunden"), None)])
            return
        try:
            items, status = self._fetch()
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self["list"].setList(items)
        self["status"].setText(status)

    def on_select(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        self._on_select(sel[1])
