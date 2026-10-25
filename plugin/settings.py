# -*- coding: utf-8 -*-
"""Smartys IPTV — Einstellungsmenü."""

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from . import theme
from .config import Config


# (config-key, Anzeigename) — Boolean-Optionen, die mit OK getoggelt werden.
OPTIONS = [
    ("timeshift", "Timeshift (Pause = automatische Aufnahme)"),
    ("confirm_switch", "Umschalt-Schutz (Abfrage bei laufender Aufnahme)"),
    ("preview", "Vorschau (PIP) in der Senderliste"),
    ("show_in_main_menu", "Im Hauptmenü anzeigen (wie XStreamity)"),
]


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
        entries = []
        for key, label in OPTIONS:
            val = bool(self.cfg.get(key, False))
            entries.append((self._fmt(label, val), key))
        # Aufnahme-Verzeichnis (nur Anzeige).
        rec_dir = self.cfg.get("rec_dir", "/media/hdd/movie")
        entries.append((self._dir_label(rec_dir), None))
        self["list"].setList(entries)

    def _fmt(self, label, val):
        state = "AN" if val else "AUS"
        return "%s   [%s]" % (label, state)

    def _dir_label(self, d):
        return "Aufnahme-Verzeichnis: %s   (nicht änderbar)" % d

    def _toggle(self):
        cur = self["list"].getCurrent()
        if not cur:
            return
        key = cur[1]
        if key is None:
            return  # Verzeichnis-Zeile ist nicht schaltbar
        val = bool(self.cfg.get(key, False))
        self.cfg.set(key, not val)
        self._rebuild()
        # Der Menüpunkt wird beim Laden der Plugins festgelegt — die
        # Umschaltung greift deshalb erst nach einem Neustart. Ohne diesen
        # Hinweis sucht man den Eintrag vergebens im Hauptmenü.
        if key == "show_in_main_menu":
            ziel = _("Hauptmenü") if not val else _("Erweiterungen (Plugins)")
            self.session.openWithCallback(
                self._neustart,
                MessageBox,
                _("Der Einstieg erscheint künftig unter: %s.\n\nDas wirkt erst nach einem Neuladen der Oberfläche. Jetzt neu laden?") % ziel,
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
