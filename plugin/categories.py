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

    # ROT/GRUEN verschieben die markierte Gruppe, GELB blendet aus,
    # BLAU holt alle zurueck. Ausgeblendete Gruppen landen als Liste von
    # Namen in der Config, nicht als IDs: manche Panels vergeben die IDs
    # bei jedem Abruf neu.
    tasten = [
        (theme.TASTE_OK, "OK", "Öffnen"),
        (theme.TASTE_ROT, "ROT", "Nach oben"),
        (theme.TASTE_GRUEN, "GRÜN", "Nach unten"),
        (theme.TASTE_GELB, "GELB", "Ausblenden"),
        (theme.TASTE_BLAU, "BLAU", "Alle aus/an"),
    ]

    def __init__(self, session, cfg, category_action, list_screen,
                 list_header, list_subtitle):
        self.skin = theme.build_skin(
            self.screen_name,
            tasten=getattr(self, "tasten", None),
            tasten_dynamisch=("GELB",))
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
        # Beschriftung der GELB-Taste wechselt je nach Zustand des
        # markierten Eintrags: ausgeblendet -> "Einblenden".
        self["taste_gelb"] = Label(_("Ausblenden"))

        try:
            self["list"].onSelectionChanged.append(lambda: self._gelb_label())
        except Exception:
            pass

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.open_category,
                "cancel": self.close,
                "red": lambda: self._move_current(-1),
                "green": lambda: self._move_current(+1),
                "yellow": self._hide_current,
                "blue": self._alle_aus_oder_an,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _gelb_label(self):
        """GELB-Beschriftung an den markierten Eintrag anpassen."""
        try:
            sel = self["list"].getCurrent()
        except Exception:
            sel = None
        if not sel or sel[1] in (None, "__fav__"):
            text = _("Ausblenden")
        else:
            name = sel[0]
            if name.startswith("- "):
                name = name[2:]
            text = _("Einblenden") if name in self._hidden() else _("Ausblenden")
        try:
            self["taste_gelb"].setText(text)
        except Exception:
            pass

    def _order_key(self):
        """Config-Schluessel fuer die eigene Gruppen-Reihenfolge."""
        bereich = (self.category_action or "").replace("_categories", "")
        return "category_order_%s" % (bereich or "live")

    def _order(self):
        """Gespeicherte Reihenfolge der Gruppennamen (kann unvollstaendig sein)."""
        wert = self.cfg.get(self._order_key(), [])
        if isinstance(wert, (list, tuple)):
            return [str(x) for x in wert]
        return []

    def _set_order(self, namen):
        self.cfg.set(self._order_key(), list(namen))
        try:
            self.cfg.save()
        except Exception:
            pass

    def _sortiere_gruppen(self, cats):
        """Eigene Reihenfolge zuerst, neue Gruppen hinten alphabetisch.

        Die Anbieter-Reihenfolge ist bei Testlines oft willkuerlich (hunderte
        Gruppen), deshalb darf der Nutzer sie selbst festlegen. Gruppen, die
        erst spaeter dazukommen, werden hinten einsortiert statt zu
        verschwinden.
        """
        pos = {n: i for i, n in enumerate(self._order())}
        def key(c):
            name = c.get("category_name", "?")
            if name in pos:
                return (0, pos[name], "")
            return (1, 0, name.casefold())
        return sorted(cats, key=key)

    def _move_current(self, delta):
        """Gruppe um eine POSITION IN DER ANZEIGE verschieben.

        Frueher wurde in self._alle getauscht, also in der Liste aller
        Gruppen. Weil ausgeblendete Gruppen in einer eigenen Sektion unten
        stehen, war der Nachbar dort fast immer eine unsichtbare Gruppe —
        der Tausch blieb also ohne sichtbare Wirkung ("gruene Taste geht
        nicht"). Jetzt wird innerhalb der Sektion getauscht, in der die
        markierte Gruppe auch steht.
        """
        sel = self["list"].getCurrent()
        if not sel or sel[1] in (None, "__fav__"):
            self["status"].setText(_("Diese Zeile lässt sich nicht verschieben"))
            return
        text = sel[0]
        ist_versteckt = text.startswith("- ")
        name = text[2:] if ist_versteckt else text

        try:
            eintraege = [e[0] for e in (self["list"].getList() or [])]
            pos = self["list"].getCurrentIndex()
        except Exception:
            self["status"].setText(_("Verschieben nicht möglich"))
            return
        if not eintraege or pos >= len(eintraege):
            return

        # Nachbarn derselben Sektion suchen (ausgeblendet bleibt bei
        # ausgeblendet, sichtbar bei sichtbar) — Kopfzeilen ueberspringen.
        zielname = None
        j = pos + delta
        while 0 <= j < len(eintraege):
            kandidat = eintraege[j]
            if kandidat in (_("Alle"),) or kandidat.startswith(_("Favoriten (")):
                j += delta
                continue
            if kandidat.startswith("- ") == ist_versteckt:
                zielname = kandidat[2:] if ist_versteckt else kandidat
                break
            j += delta

        if zielname is None:
            self["status"].setText(_("\u201e%s\u201c ist schon am Rand") % name)
            return

        reihe = [c.get("category_name", "?") for c in self._alle]
        if name not in reihe or zielname not in reihe:
            self["status"].setText(_("Verschieben nicht möglich"))
            return
        i = reihe.index(name)
        k = reihe.index(zielname)
        reihe[i], reihe[k] = reihe[k], reihe[i]
        self._set_order(reihe)
        self._load()
        self._springe_zu(name)
        richtung = _("nach unten") if delta > 0 else _("nach oben")
        self["status"].setText(
            _("\u201e%s\u201c %s verschoben") % (name, richtung))

    def _springe_zu(self, name):
        """Cursor auf eine Gruppe setzen (nach dem Verschieben/Einblenden).

        Ohne das springt die Liste bei jedem GELB nach oben und man muss sich
        durch 50 Gruppen zurueckscrollen.
        """
        try:
            eintraege = self["list"].getList()
        except Exception:
            try:
                eintraege = self["list"].list
            except Exception:
                eintraege = None
        if not eintraege:
            return
        ziel = None
        for i, eintrag in enumerate(eintraege):
            try:
                text = eintrag[0]
            except Exception:
                continue
            if isinstance(text, str) and text.startswith("- "):
                text = text[2:]
            if text == name:
                ziel = i
                break
        if ziel is None:
            return
        # Erst den Cursor setzen, dann dafuer sorgen, dass die Zeile auch
        # sichtbar ist: moveToIndex scrollt bei Enigma2 nicht immer mit.
        for aufruf in (
            lambda: self["list"].moveToIndex(ziel),
            lambda: self["list"].instance.moveToIndex(ziel),
            lambda: self["list"].setCurrentIndex(ziel),
        ):
            try:
                aufruf()
                break
            except Exception:
                continue
        try:
            self["list"].setTopIndex(max(0, ziel - 5))
        except Exception:
            try:
                self["list"].instance.setTopIndex(max(0, ziel - 5))
            except Exception:
                pass

    def _cfg_key(self):
        """Config-Schluessel fuer diesen Bereich.

        Live-TV, Filme und Serien fuehren getrennte Listen: die Kategorienamen
        ueberschneiden sich (Sport, Kinder, DE), ein gemeinsamer Schluessel
        wuerde beim Ausblenden in einer Ebene die anderen mit ausblenden.
        """
        bereich = (self.category_action or "").replace("_categories", "")
        return "hidden_categories_%s" % (bereich or "live")

    def _hidden(self):
        """Namen der ausgeblendeten Gruppen (Liste, stabil sortiert)."""
        wert = self.cfg.get(self._cfg_key(), [])
        # Altbestand: vor der Bereichstrennung lag alles in einem globalen
        # Schluessel. Diese Namen gehoeren zu Live-TV, dort weiterverwenden,
        # damit eine bestehende Auswahl nicht verloren geht.
        if not wert and self._cfg_key() == "hidden_categories_live":
            wert = self.cfg.get("hidden_categories", [])
        if isinstance(wert, dict):
            # Altbestand: frueher als {name: true} gespeichert
            return sorted([k for k, v in wert.items() if v])
        if isinstance(wert, (list, tuple)):
            return [str(x) for x in wert]
        return []

    def _set_hidden(self, namen):
        self.cfg.set(self._cfg_key(), sorted(set(namen)))
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
        # POSITION merken, nicht den Namen: die eingeblendete Gruppe wandert
        # nach oben in die sichtbare Liste, die ausgeblendete nach unten in
        # die "- "-Sektion. Wuerde der Cursor dem Namen folgen, springt er
        # bei jedem GELB an den Anfang und man muss sich zurueckscrollen.
        # Auf demselben Index bleibt dagegen der naechste Kandidat stehen.
        try:
            pos = self["list"].getCurrentIndex()
        except Exception:
            pos = 0
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
        self._nach_index(pos)

    def _nach_index(self, pos):
        """Cursor auf eine Listenposition setzen (nicht auf einen Namen)."""
        try:
            anzahl = len(self["list"].getList() or [])
        except Exception:
            return
        if anzahl <= 0:
            return
        ziel = min(max(0, pos), anzahl - 1)
        for aufruf in (
            lambda: self["list"].moveToIndex(ziel),
            lambda: self["list"].setCurrentIndex(ziel),
            lambda: self["list"].instance.moveToIndex(ziel),
        ):
            try:
                aufruf()
                break
            except Exception:
                continue
        try:
            self["list"].setTopIndex(max(0, ziel - 5))
        except Exception:
            try:
                self["list"].instance.setTopIndex(max(0, ziel - 5))
            except Exception:
                pass

    def _hide_all(self):
        """BLAU bei sichtbaren Gruppen: ALLE ausblenden.

        Danach ist die Liste leer bis auf die ausgeblendeten Eintraege — man
        geht sie durch und holt mit GELB nur die zurueck, die man behalten
        will. Das ist der schnelle Weg bei Testlines mit hunderten Gruppen.
        """
        namen = [c.get("category_name", "?") for c in self._alle]
        if not namen:
            return
        try:
            pos = self["list"].getCurrentIndex()
        except Exception:
            pos = 0
        self._set_hidden(namen)
        self._load()
        self._nach_index(pos)
        self["status"].setText(
            _("%d Gruppen ausgeblendet — GELB holt einzelne zurück") % len(namen))

    def _show_all(self):
        """BLAU bei ausgeblendeten Gruppen: alle wieder anzeigen."""
        anzahl = len(self._hidden())
        if not anzahl:
            self["status"].setText(_("Nichts ausgeblendet"))
            return
        self._set_hidden([])
        self["status"].setText(_("%d Gruppen wieder eingeblendet") % anzahl)
        self._load()

    def _alle_aus_oder_an(self):
        """BLAU: alle aus, wenn noch welche sichtbar sind — sonst alle an."""
        namen = [c.get("category_name", "?") for c in self._alle]
        if not namen:
            return
        if len(self._hidden()) >= len(namen):
            self._show_all()
        else:
            self._hide_all()

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
        self._alle = self._sortiere_gruppen(cats)
        versteckt = set(self._hidden())

        entries = [(_("Alle"), None)]
        try:
            favs = self.cfg.favorites()
        except Exception:
            favs = []
        if favs and self.category_action == "live_categories":
            entries.append((_("Favoriten (%d)") % len(favs), "__fav__"))

        sichtbar = 0
        for c in self._alle:
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
            for c in self._alle:
                name = c.get("category_name", "?")
                if name in versteckt:
                    entries.append(("- " + name, c.get("category_id")))

        self["list"].setList(entries)
        self._gelb_label()
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
