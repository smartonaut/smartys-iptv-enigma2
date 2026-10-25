# -*- coding: utf-8 -*-
"""Smartys IPTV — Einstellungsmenü."""

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from . import theme
from .config import Config
from .recdir import RecDirScreen, freier_platz


# (config-key, Anzeigename) — Boolean-Optionen, die mit OK getoggelt werden.
OPTIONS = [
    ("timeshift", "Timeshift (Pause = automatische Aufnahme)"),
    ("confirm_switch", "Umschalt-Schutz (Abfrage bei laufender Aufnahme)"),
    ("preview", "Vorschau (PIP) in der Senderliste"),
    ("show_in_main_menu", "Im Hauptmenü anzeigen (wie XStreamity)"),
]

# Sortiermodi — muessen zu channellist.LiveListScreen.SORT_MODES passen.
SORT_REIHENFOLGE = ("original", "az", "za", "fav_first")
SORT_NAMEN = {
    "original": "Reihenfolge des Anbieters",
    "az": "Alphabetisch A-Z",
    "za": "Alphabetisch Z-A",
    "fav_first": "Favoriten zuerst",
}


class SettingsScreen(Screen):
    def __init__(self, session):
        # WICHTIG: Skin muss VOR Screen.__init__ gesetzt werden, sonst baut
        # Enigma2 den Screen mit dem Default-Skin (siehe alle anderen Screens).
        self.skin = theme.build_skin(
            "SmartysSettings", logo=True,
            tasten=[(theme.TASTE_OK, "OK", "Ändern"), (None, "EXIT", "Zurück")])
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        self["header"] = Label(_("Einstellungen"))
        self["subtitle"] = Label(_("Optionen"))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {
                "ok": self._toggle,
                "cancel": self.close,
            },
        )

        self._rebuild()

    def _rebuild(self):
        """Baut die Liste neu auf.

        Jede Zeile traegt einen Aktionstyp als zweites Element:
        ("bool", key)     — AN/AUS
        ("rec", None)     — Aufnahmeverzeichnis waehlen
        ("sort", None)    — Sortierung durchschalten
        ("hidden", None)  — ausgeblendete Gruppen zuruecksetzen
        """
        entries = []
        for key, label in OPTIONS:
            val = bool(self.cfg.get(key, False))
            entries.append((self._fmt(label, val), ("bool", key)))

        # Aufnahmeverzeichnis — jetzt aenderbar, mit freiem Platz daneben.
        rec_dir = self.cfg.get("rec_dir", "/media/hdd/movie")
        frei = freier_platz(rec_dir)
        zusatz = "  (%.1f GB frei)" % frei if frei is not None else ""
        entries.append((
            "Aufnahme-Verzeichnis:  %s%s" % (rec_dir, zusatz),
            ("rec", None)))

        # Sortierung
        modus = self.cfg.get("sort_mode", "original")
        entries.append((
            "Sortierung Senderliste:  %s"
            % SORT_NAMEN.get(modus, SORT_NAMEN["original"]),
            ("sort", None)))

        # Ausgeblendete Gruppen
        versteckt = self.cfg.get("hidden_categories", [])
        if isinstance(versteckt, dict):
            anzahl = len([k for k, v in versteckt.items() if v])
        elif isinstance(versteckt, (list, tuple)):
            anzahl = len(versteckt)
        else:
            anzahl = 0
        if anzahl:
            entries.append((
                "Ausgeblendete Gruppen:  %d  (OK = alle wieder zeigen)" % anzahl,
                ("hidden", None)))
        else:
            entries.append((
                "Ausgeblendete Gruppen:  keine", ("hidden", None)))

        self["list"].setList(entries)

    def _fmt(self, label, val):
        return "%s   [%s]" % (label, "AN" if val else "AUS")

    def _toggle(self):
        cur = self["list"].getCurrent()
        if not cur or not cur[1]:
            return
        art, key = cur[1]

        if art == "rec":
            self._waehle_verzeichnis()
            return
        if art == "sort":
            self._naechste_sortierung()
            return
        if art == "hidden":
            self._zeige_versteckte()
            return

        val = bool(self.cfg.get(key, False))
        self.cfg.set(key, not val)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._rebuild()
        # Der Menüpunkt wird beim Laden der Plugins festgelegt — die
        # Umschaltung greift deshalb erst nach einem Neuladen. Ohne diesen
        # Hinweis sucht man den Eintrag vergebens im Hauptmenü.
        if key == "show_in_main_menu":
            ziel = _("Hauptmenü") if not val else _("Erweiterungen (Plugins)")
            self.session.openWithCallback(
                self._neustart,
                MessageBox,
                _("Der Einstieg erscheint künftig unter: %s.\n\n"
                  "Das wirkt erst nach einem Neuladen der Oberfläche. "
                  "Jetzt neu laden?") % ziel,
                MessageBox.TYPE_YESNO,
            )

    def _waehle_verzeichnis(self):
        """Oeffnet den Ordner-Browser und uebernimmt die Auswahl."""
        aktuell = self.cfg.get("rec_dir", "/media/hdd/movie")

        def _fertig(pfad):
            if not pfad:
                return
            self.cfg.set("rec_dir", pfad)
            try:
                self.cfg.save()
            except Exception:
                pass
            self._rebuild()
            self["status"].setText(_("Aufnahmen jetzt nach: %s") % pfad)

        self.session.open(RecDirScreen, start=aktuell, callback=_fertig)

    def _naechste_sortierung(self):
        modus = self.cfg.get("sort_mode", "original")
        try:
            idx = SORT_REIHENFOLGE.index(modus)
        except ValueError:
            idx = 0
        neu = SORT_REIHENFOLGE[(idx + 1) % len(SORT_REIHENFOLGE)]
        self.cfg.set("sort_mode", neu)
        try:
            self.cfg.save()
        except Exception:
            pass
        self._rebuild()
        self["status"].setText(_("Sortierung: %s") % SORT_NAMEN.get(neu, neu))

    def _zeige_versteckte(self):
        """Zeigt die ausgeblendeten Gruppen und bietet das Zuruecksetzen an."""
        versteckt = self.cfg.get("hidden_categories", [])
        if isinstance(versteckt, dict):
            namen = sorted([k for k, v in versteckt.items() if v])
        elif isinstance(versteckt, (list, tuple)):
            namen = [str(x) for x in versteckt]
        else:
            namen = []
        if not namen:
            self["status"].setText(
                _("Keine Gruppen ausgeblendet (in der Kategorienliste mit GELB)"))
            return

        def _antwort(ja):
            if not ja:
                return
            self.cfg.set("hidden_categories", [])
            try:
                self.cfg.save()
            except Exception:
                pass
            self._rebuild()
            self["status"].setText(_("Alle Gruppen wieder sichtbar"))

        self.session.openWithCallback(
            _antwort,
            MessageBox,
            _("Diese Gruppen sind ausgeblendet:\n\n%s\n\nAlle wieder einblenden?")
            % ("\n".join("• " + n for n in namen)),
            MessageBox.TYPE_YESNO,
        )

    def _neustart(self, ja):
        """Oberfläche neu laden — kein Box-Neustart, nur der Enigma-Autoreload."""
        if not ja:
            return
        try:
            from enigma import quitMainloop
            quitMainloop(3)
        except Exception:
            try:
                import os
                os.system("init 4; sleep 2; init 3 &")
            except Exception:
                pass
