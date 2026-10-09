# -*- coding: utf-8 -*-
"""Smartys IPTV — Kategorie-Screen (Gruppe → Untergruppe).

Zeigt die Kategorien (z.B. Sport, Filme, Kinder) als erste Ebene, damit man
nicht durch tausende Einträge scrollen muss. Bei OK öffnet sich die
entsprechende Liste mit category_id gefiltert.
"""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from .api import Credentials, XtreamApi
from . import theme


class CategoryListScreen(Screen):
    """Generischer Kategorie-Screen.

    Erwartet: category_action (api-methodenname), list_screen (Screen-Klasse),
    list_header (Titel der Folgeliste), plus "Alle" als erster Eintrag.
    """

    screen_name = "SmartysCategories"

    def __init__(self, session, cfg, category_action, list_screen,
                 list_header, list_subtitle):
        self.skin = theme.build_skin(self.screen_name)
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.category_action = category_action
        self.list_screen = list_screen
        self.list_header = list_header
        self.list_subtitle = list_subtitle

        self.api = self._build_api()
        self.categories = []

        self["header"] = Label(_("Kategorien"))
        self["subtitle"] = Label(_(list_header))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.open_category, "cancel": self.close},
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
            cats = getattr(self.api, self.category_action)()
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        # "Alle" als erster Eintrag (category_id=None zeigt alles)
        entries = [(_("Alle"), None)]
        for c in cats:
            entries.append((c.get("category_name", "?"), c.get("category_id")))
        self["list"].setList(entries)
        self["status"].setText(_("%d Kategorien") % len(cats))

    def open_category(self):
        sel = self["list"].getCurrent()
        if not sel:
            return
        category_id = sel[1]
        self.session.open(
            self.list_screen, self.cfg, category_id,
            self.list_header, self.list_subtitle)
