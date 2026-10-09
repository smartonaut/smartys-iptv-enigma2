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
    """Basis für Live-TV / VOD / Serien-Listen.

    Konstruktor akzeptiert optional category_id (Filter) und Header/Untertitel,
    damit die Kategorie-Navigation die Folgeliste steuern kann.
    """

    screen_name = "SmartysList"
    header_text = ""
    subtitle_text = ""
    # Unterklassen setzen True, um ein Pig-Vorschaufenster einzublenden.
    preview = False
    # Tasten-Hinweise unten im Screen.
    footer = ""
    # Unterklassen setzen True, um ein EPG-Label (jetzt/danach) zu zeigen.
    epg = False

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        self.skin = theme.build_skin(self.screen_name, preview=self.preview,
                                     footer=self.footer, epg=self.epg)
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.category_id = category_id
        if header_text is not None:
            self.header_text = header_text
        if subtitle_text is not None:
            self.subtitle_text = subtitle_text

        self.api = self._build_api()

        self["header"] = Label(_(self.header_text))
        self["subtitle"] = Label(_(self.subtitle_text))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "InfoActions"],
            {
                "ok": self.on_select,
                "cancel": self.close,
                "red": self.on_red,
                "info": self.on_info,
            },
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

    # --- optional: ROT-Taste (Aufnahme) — Standard: ignorieren ---

    def on_red(self):
        pass

    # --- optional: EPG/INFO-Taste — Standard: ignorieren ---

    def on_info(self):
        pass

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
