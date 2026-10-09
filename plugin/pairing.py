# -*- coding: utf-8 -*-
"""Smartys IPTV — Pairing-Screen.

Zeigt die generierte Player-ID (MAC) + Pairing-Passwort AN (die trägt der
Nutzer im Panel ein) und holt per 'Verbinden' die Provider-Credentials.
"""

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label

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
            "1. Im Browser panel.smartys.tech öffnen\n"
            "2. Mit diesen Daten anmelden + Playlist zuweisen\n"
            "3. Hier ROT (Verbinden) drücken"
        ) % (self.pid, self.pw))
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
