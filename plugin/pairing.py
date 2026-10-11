# -*- coding: utf-8 -*-
"""Smartys IPTV — Pairing-Screen.

Zeigt die generierte Player-ID (MAC) + Pairing-Passwort AN (die trägt der
Nutzer im Panel ein) und holt per 'Verbinden' die Provider-Credentials.
"""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from .config import Config
from .api import pair_with_panel, ApiError
from . import theme


class PairingScreen(Screen):
    def __init__(self, session):
        self.skin = theme.build_skin(
            "SmartysPairing", list_h=330,
            extra_widgets=(
                '<widget name="details" position="%d,%d" size="%d,%d" '
                'font="Regular;%d" foregroundColor="%s" valign="top" '
                'transparent="1" zPosition="2" />'
                % (theme.scale(48), theme.scale_y(162), theme.scale(1184),
                   theme.scale_y(330), theme.font(19), theme.TEXT)
                +
                '<widget name="qr" position="%d,%d" size="%d,%d" '
                'zPosition="3" transparent="1" alphatest="on" />'
                % (theme.scale(48), theme.scale_y(510), theme.scale(230),
                   theme.scale_y(230))
            ),
        )
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        # Einmalig generieren (identisch zur Desktop/Android-App)
        self.pid = self.cfg.player_id()
        self.pw = self.cfg.pairing_pw()

        self["header"] = Label(_("Pairing"))
        self["subtitle"] = Label(_("Mit dem Panel verbinden"))
        self["details"] = Label(_(
            "Player-ID:  %s\n"
            "Passwort:   %s\n"
            "\n"
            "1. QR-Code mit dem Handy scannen\n"
            "   (oder panel.smartys.tech im Browser öffnen)\n"
            "2. Playlist zuweisen\n"
            "3. Hier ROT (Verbinden) drücken"
        ) % (self.pid, self.pw))
        self["qr"] = Pixmap()
        self["status"] = Label(
            _("Verbunden") if self.cfg.providers() else _("Nicht verbunden"))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.connect,
                "cancel": self.close,
                "red": self.connect,
                "green": self.close,
            },
        )
        self.onLayoutFinish.append(self._load_qr)

    def _load_qr(self):
        """Lädt das QR-PNG asynchron vom Panel und zeigt es an."""
        import threading
        import subprocess
        from urllib.parse import quote
        url = "https://panel.smartys.tech/qr?mac=%s&pw=%s" % (
            quote(self.pid), quote(self.pw))
        path = "/tmp/smartys_qr.png"
        # None = lädt noch, "" = Fehler, Pfad = fertig
        self._qr_path = None

        def fetch():
            try:
                subprocess.run(
                    ["wget", "-q", "-O", path, url], check=True, timeout=20)
                self._qr_path = path
            except Exception:
                self._qr_path = ""

        threading.Thread(target=fetch, daemon=True).start()

        self._qr_poll_timer = eTimer()
        try:
            self._qr_poll_timer.callback.append(self._poll_qr)
        except Exception:
            self._qr_poll_timer.timeout.connect(self._poll_qr)
        self._qr_poll_timer.start(400, True)

    def _poll_qr(self):
        if self._qr_path is None:
            try:
                self._qr_poll_timer.start(400, True)
            except Exception:
                pass
            return
        if self._qr_path:
            try:
                pix = LoadPixmap(self._qr_path)
                if pix:
                    self["qr"].instance.setPixmap(pix)
            except Exception:
                pass

    def connect(self):
        self["status"].setText(_("Verbinde mit panel.smartys.tech…"))
        try:
            creds = pair_with_panel(self.pid, self.pw)
        except ApiError as e:
            self["status"].setText(str(e))
            return

        if not creds:
            self["status"].setText(_("Keine Playlist zugewiesen"))
            return

        self.cfg.set_providers(creds)
        self["status"].setText(_("OK — %d Provider geladen") % len(creds))
