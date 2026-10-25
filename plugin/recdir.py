# -*- coding: utf-8 -*-
"""Smartys IPTV — Verzeichnis-Auswahl fuer das Aufnahmeverzeichnis.

Eigener Screen, weil Enigma2 keinen fertigen Ordner-Browser fuer diesen
Zweck mitbringt. Bedienung nur mit der Fernbedienung: hoch/runter waehlt,
OK oeffnet einen Ordner oder bestaetigt, BLAU legt einen neuen Ordner an,
EXIT bricht ab.
"""

import os

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from . import theme


# Orte, an denen auf einer Enigma2-Box ueblicherweise geschrieben werden darf.
# Die Reihenfolge ist die Voreinstellung: erst die echten Datentraeger.
START_ORTE = [
    "/media/hdd/movie",
    "/media/hdd",
    "/media/usb",
    "/media/usb/movie",
    "/media/hdd2",
    "/home/root",
    "/tmp",
]


def _schreibbar(pfad):
    """Prueft, ob in den Ordner wirklich geschrieben werden kann.

    os.access allein genuegt nicht: auf Boxen mit read-only gemountetem
    /media/net oder einem vollen Datentraeger waere der Ordner trotzdem
    unbrauchbar. Deshalb eine echte Testdatei.
    """
    if not os.path.isdir(pfad):
        return False
    test = os.path.join(pfad, ".smartys_write_test")
    try:
        with open(test, "w") as f:
            f.write("x")
        os.remove(test)
        return True
    except Exception:
        return False


def freier_platz(pfad):
    """Freier Platz in GB (oder None, wenn nicht ermittelbar)."""
    try:
        st = os.statvfs(pfad)
        return st.f_bavail * st.f_frsize / (1024.0 ** 3)
    except Exception:
        return None


class RecDirScreen(Screen):
    """Ordner-Browser fuer das Aufnahmeverzeichnis."""

    screen_name = "SmartysRecDir"
    tasten = [
        (theme.TASTE_OK, "OK", "Öffnen / Wählen"),
        (theme.TASTE_BLAU, "BLAU", "Neuer Ordner"),
        (None, "EXIT", "Zurück"),
    ]

    def __init__(self, session, start=None, callback=None):
        self.skin = theme.build_skin(
            self.screen_name, tasten=getattr(self, "tasten", None))
        Screen.__init__(self, session)
        self.session = session
        self.callback = callback
        self.pfad = start if start and os.path.isdir(start) else "/media/hdd"

        self["header"] = Label(_("Aufnahmeverzeichnis"))
        self["subtitle"] = Label(self.pfad)
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self._ok,
                "cancel": self._abbrechen,
                "blue": self._neuer_ordner,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _eintraege(self):
        """Ordnerliste: Übergeordnet, Unterordner, dann 'Diesen Ordner wählen'."""
        eintraege = []
        eltern = os.path.dirname(self.pfad.rstrip("/"))
        if eltern and eltern != self.pfad:
            eintraege.append((_(".. (übergeordnet)"), ("nav", eltern, None)))

        try:
            namen = sorted(os.listdir(self.pfad))
        except Exception:
            namen = []
        for name in namen:
            if name.startswith("."):
                continue
            voll = os.path.join(self.pfad, name)
            if not os.path.isdir(voll):
                continue
            try:
                frei = freier_platz(voll)
            except Exception:
                frei = None
            zusatz = ""
            if frei is not None:
                zusatz = "   (%.1f GB frei)" % frei
            eintraege.append((name + zusatz, ("nav", voll, None)))

        # Der aktuelle Ordner als Auswahl — steht unten, damit man beim
        # Durchblaettern nicht versehentlich bestaetigt.
        frei = freier_platz(self.pfad)
        text = _("Diesen Ordner verwenden")
        if frei is not None:
            text += "   (%.1f GB frei)" % frei
        eintraege.append((text, ("waehlen", self.pfad, None)))
        return eintraege

    def _load(self):
        self["subtitle"].setText(self.pfad)
        eintraege = self._eintraege()
        self["list"].setList(eintraege)
        if _schreibbar(self.pfad):
            self["status"].setText(_("Schreibbar"))
        else:
            self["status"].setText(
                _("Nicht beschreibbar — bitte einen anderen Ordner wählen"))

    def _ok(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        art, pfad, _unused = sel[1]
        if art == "nav":
            self.pfad = pfad
            self._load()
            return
        # Auswahl bestaetigen
        if not _schreibbar(pfad):
            self.session.open(
                MessageBox,
                _("In diesen Ordner kann nicht geschrieben werden:\n%s\n\n"
                  "Bitte einen anderen wählen.") % pfad,
                MessageBox.TYPE_ERROR)
            return
        if self.callback:
            self.callback(pfad)
        self.close()

    def _abbrechen(self):
        if self.callback:
            self.callback(None)
        self.close()

    def _neuer_ordner(self):
        """BLAU: neuen Unterordner anlegen (Name per Bildschirmtastatur)."""
        from Screens.VirtualKeyBoard import VirtualKeyBoard

        def _fertig(name):
            if not name:
                return
            # Schraegstriche und Punkte am Anfang abweisen — sonst landet
            # die Aufnahme ausserhalb des gewaehlten Ordners.
            name = name.replace("/", "_").strip().lstrip(".")
            if not name:
                return
            ziel = os.path.join(self.pfad, name)
            try:
                if not os.path.isdir(ziel):
                    os.makedirs(ziel)
            except Exception as e:
                self.session.open(
                    MessageBox,
                    _("Ordner konnte nicht angelegt werden:\n%s") % str(e),
                    MessageBox.TYPE_ERROR)
                return
            self.pfad = ziel
            self._load()

        self.session.openWithCallback(_fertig, VirtualKeyBoard,
                                      title=_("Name des neuen Ordners"),
                                      text="")
