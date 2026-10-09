# -*- coding: utf-8 -*-
"""Smartys IPTV — Pairing-Screen (Player-ID + Passwort gegen panel.smartys.tech)."""

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Button import Button
from Components.ConfigList import ConfigListScreen
from Components.config import config, ConfigText, ConfigSelection, getConfigListEntry

from .config import Config
from .api import pair_with_panel, ApiError


class PairingScreen(Screen):
    skin = """
        <screen position="center,center" size="640,360" title="Smartys IPTV — Pairing">
            <widget name="info" position="20,10" size="600,60" font="Regular;20" halign="center" valign="center" />
            <widget name="config" position="20,90" size="600,160" />
            <widget name="status" position="20,260" size="600,40" font="Regular;18" halign="center" />
            <widget name="key_red" position="20,310" size="200,30" font="Regular;20" halign="center" />
            <widget name="key_green" position="240,310" size="200,30" font="Regular;20" halign="center" />
        </screen>
    """

    def __init__(self, session):
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        self.player_id = ConfigText(default=self.cfg.player_id(), fixed_size=False)
        self.pairing_pw = ConfigText(default=self.cfg.pairing_pw(), fixed_size=False)

        self["info"] = Label(_(
            "1. Auf panel.smartys.tech mit Player-ID + Passwort anmelden\n"
            "2. Dort Playlist hinterlegen\n"
            "3. Hier 'Verbinden' drücken"))
        self["config"] = self._configlist()
        self["status"] = Label(_(""))
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
        self.onLayoutFinish.append(self._set_keys)

    def _configlist(self):
        from Components.config import getConfigListEntry
        self.list = [
            getConfigListEntry(_("Player-ID"), self.player_id),
            getConfigListEntry(_("Passwort"), self.pairing_pw),
        ]
        from Components.ConfigList import ConfigList
        cl = ConfigList(self.list)
        self["config"] = cl
        return cl

    def _set_keys(self):
        self["key_red"].setText(_("Verbinden"))
        self["key_green"].setText(_("Zurück"))

    def connect(self):
        pid = self.player_id.value.strip()
        pw = self.pairing_pw.value.strip()
        if not pid or not pw:
            self["status"].setText(_("Bitte Player-ID und Passwort eingeben"))
            return

        self["status"].setText(_("Verbinde mit panel.smartys.tech…"))
        try:
            creds = pair_with_panel(pid, pw)
        except ApiError as e:
            self["status"].setText(str(e))
            return

        if not creds:
            self["status"].setText(_("Keine Playlist zugewiesen"))
            return

        self.cfg.set("player_id", pid)
        self.cfg.set("pairing_pw", pw)
        self.cfg.set_providers(creds)
        self["status"].setText(_("OK — %d Provider geladen") % len(creds))
