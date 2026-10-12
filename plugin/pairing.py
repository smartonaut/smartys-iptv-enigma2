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
from .api import (pair_with_panel, providers_to_credentials, ApiError,
                  delete_player_remote)
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
                'scale="1" zPosition="3" transparent="1" alphatest="blend" />'
                % (theme.scale(48), theme.scale_y(488), theme.scale(200),
                   theme.scale_y(200))
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
            "3. Hier ROT (Verbinden) drücken\n"
            "\n"
            "GELB = Pairing löschen    GRÜN = Schließen"
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
                "yellow": self.delete_pairing,
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
            payload = pair_with_panel(self.pid, self.pw)
        except ApiError as e:
            self["status"].setText(str(e))
            return

        if payload.get("encrypted"):
            # Panel-Spieler MIT Sicherheits-Passwort: Line kommt verschlüsselt.
            # Entschlüsselung passiert LOKAL — Nutzer-Passwort abfragen.
            if not payload.get("providers"):
                self["status"].setText(_("Keine Playlist zugewiesen"))
                return
            self["status"].setText(_(
                "Line verschlüsselt empfangen — Sicherheits-Passwort eingeben"))
            from .lineentry import UnlockScreen
            self.session.open(UnlockScreen, payload=payload)
            return

        # Alt-Format: Panel ohne Sicherheits-Passwort (Klartext, wie bisher).
        creds = providers_to_credentials(payload.get("providers") or [])
        if not creds:
            self["status"].setText(_("Keine Playlist zugewiesen"))
            return

        self.cfg.set_providers_legacy(creds)
        self["status"].setText(_("OK — %d Provider geladen") % len(creds))

    def delete_pairing(self):
        """GELB: Pairing + Line komplett löschen (mit Warnung)."""
        from Screens.MessageBox import MessageBox

        def _do_delete(answer):
            if answer is not True:
                return
            self["status"].setText(_("Lösche Pairing…"))
            try:
                delete_player_remote(self.pid, self.pw)
            except ApiError as e:
                self["status"].setText(str(e))
                return
            self.cfg.reset()
            self.pid = self.cfg.player_id()
            self.pw = self.cfg.pairing_pw()

            def _restart(answer):
                from enigma import quitMainloop
                quitMainloop(3)

            self.session.openWithCallback(
                _restart,
                MessageBox,
                _("Pairing gelöscht.\n\n"
                  "Line + Pairing sind entfernt.\n"
                  "Enigma2 wird jetzt neu gestartet."),
                MessageBox.TYPE_INFO,
            )

        self.session.openWithCallback(
            _do_delete,
            MessageBox,
            _("Pairing wirklich löschen?\n\n"
              "Das löscht deine Line und das Pairing mit dem Webpanel.\n"
              "Du musst dich danach neu registrieren."),
            MessageBox.TYPE_YESNO,
        )
