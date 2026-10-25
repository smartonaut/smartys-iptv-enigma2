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

    # GELB blendet die markierte Gruppe aus, BLAU holt alle zurueck.
    # Ausgeblendete Gruppen landen als Liste von Namen in der Config, nicht
    # als IDs: manche Panels vergeben die IDs bei jedem Abruf neu.
    tasten = [
        (theme.TASTE_OK, "OK", "Öffnen"),
        (theme.TASTE_GELB, "GELB", "Ausblenden"),
        (theme.TASTE_BLAU, "BLAU", "Alle zeigen"),
        (None, "EXIT", "Zurück"),
    ]

    def __init__(self, session, cfg, category_action, list_screen,
                 list_header, list_subtitle):
        self.skin = theme.build_skin(
            self.screen_name,
            tasten=getattr(self, "tasten", None))
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.category_action = category_action
        self.list_screen = list_screen
        self.list_header = list_header
        self.list_subtitle = list_subtitle

        self.api = self._build_api()
        self.categories = []
        self._alle = []

        self["header"] = Label(_("Kategorien"))
        self["subtitle"] = Label(_(list_header))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.open_category,
                "cancel": self.close,
                "yellow": self._hide_current,
                "blue": self._show_all,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _hidden(self):
        """Namen der ausgeblendeten Gruppen (Liste, stabil sortiert)."""
        wert = self.cfg.get("hidden_categories", [])
        if isinstance(wert, dict):
            # Altbestand: frueher als {name: true} gespeichert
            return sorted([k for k, v in wert.items() if v])
        if isinstance(wert, (list, tuple)):
            return [str(x) for x in wert]
        return []

    def _set_hidden(self, namen):
        self.cfg.set("hidden_categories", sorted(set(namen)))
        try:
            self.cfg.save()
        except Exception:
            pass

    def _hide_current(self):
        """GELB: markierte Gruppe ausblenden (oder wieder einblenden)."""
        sel = self["list"].getCurrent()
        if not sel or sel[1] in (None, "__fav__"):
            # "Alle" und "Favoriten" lassen sich nicht ausblenden — sonst
            # waere der Screen nicht mehr bedienbar.
            self["status"].setText(_("Diese Zeile lässt sich nicht ausblenden"))
            return
        name = sel[0]
        if name.startswith("- "):
            name = name[2:]   # Marker der ausgeblendeten Sektion
        versteckt = self._hidden()
        if name in versteckt:
            versteckt.remove(name)
            self._set_hidden(versteckt)
            self["status"].setText(_("\u201e%s\u201c wieder eingeblendet") % name)
        else:
            versteckt.append(name)
            self._set_hidden(versteckt)
            self["status"].setText(_("\u201e%s\u201c ausgeblendet") % name)
        self._load()

    def _show_all(self):
        """BLAU: alle ausgeblendeten Gruppen wieder anzeigen."""
        anzahl = len(self._hidden())
        if not anzahl:
            self["status"].setText(_("Nichts ausgeblendet"))
            return
        self._set_hidden([])
        self["status"].setText(_("%d Gruppen wieder eingeblendet") % anzahl)
        self._load()

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
        self._alle = cats
        versteckt = set(self._hidden())

        entries = [(_("Alle"), None)]
        try:
            favs = self.cfg.favorites()
        except Exception:
            favs = []
        if favs and self.category_action == "live_categories":
            entries.append((_("Favoriten (%d)") % len(favs), "__fav__"))

        sichtbar = 0
        for c in cats:
            name = c.get("category_name", "?")
            if name in versteckt:
                continue
            # Ausgeblendete Gruppen bleiben mit einem Punkt markiert sichtbar,
            # damit man sie mit GELB wieder einschalten kann. Ohne diesen
            # Anker findet man sie nicht mehr.
            entries.append((name, c.get("category_id")))
            sichtbar += 1

        # Die ausgeblendeten als eigene Sektion unten anhängen — gedimmt
        # markiert, damit klar ist, dass sie normalerweise nicht erscheinen.
        if versteckt:
            for c in cats:
                name = c.get("category_name", "?")
                if name in versteckt:
                    entries.append(("- " + name, c.get("category_id")))

        self["list"].setList(entries)
        if versteckt:
            self["status"].setText(
                _("%d Kategorien · %d ausgeblendet (GELB ein/aus)")
                % (sichtbar, len(versteckt)))
        else:
            self["status"].setText(_("%d Kategorien") % len(cats))

    def open_category(self):
        sel = self["list"].getCurrent()
        if not sel:
            return
        category_id = sel[1]
        if category_id == "__fav__":
            self.session.open(
                self.list_screen, self.cfg, "__fav__",
                _("Favoriten"), _("gemerkte Sender"))
            return
        self.session.open(
            self.list_screen, self.cfg, category_id,
            self.list_header, self.list_subtitle)
