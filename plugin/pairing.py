# -*- coding: utf-8 -*-
"""Smartys IPTV — Pairing-Screen.

Zeigt die generierte Player-ID (MAC) + Pairing-Passwort AN (die trägt der
Nutzer im Panel ein) und holt per 'Verbinden' die Provider-Credentials.
"""

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button

from .config import Config
from .api import pair_with_panel, ApiError


class PairingScreen(Screen):
    skin = """
        <screen position="center,center" size="720,430" title="Smartys IPTV — Pairing">
            <widget name="info" position="20,10" size="680,130" font="Regular;20" valign="center" />
            <widget name="status" position="20,150" size="680,40" font="Regular;20" halign="center" />
            <widget name="key_red" position="20,390" size="200,30" font="Regular;20" halign="center" />
            <widget name="key_green" position="240,390" size="200,30" font="Regular;20" halign="center" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        # Einmalig generieren (identisch zur Desktop/Android-App)
        self.pid = self.cfg.player_id()
        self.pw = self.cfg.pairing_pw()

        self["info"] = Label(_(
            "Player-ID:  %s\n"
            "Passwort:   %s\n"
            "\n"
            "1. Im Browser panel.smartys.tech öffnen\n"
            "2. Mit diesen Daten anmelden + Playlist zuweisen\n"
            "3. Hier ROT (Verbinden) drücken"
        ) % (self.pid, self.pw))
        self["status"] = Label(_(
            "Verbunden") if self.cfg.providers() else _("Nicht verbunden"))

        self["key_red"] = Button(_("Verbinden"))
        self["key_green"] = Button(_("Zurück"))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.connect,
                "cancel": self.close,
                "red": self.connect,
                "green": self.close,
            },
        )

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
