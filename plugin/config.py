# -*- coding: utf-8 -*-
"""
Smartys IPTV — Konfiguration & Persistenz für Enigma2.

Speichert Player-ID, Pairing-Passwort und Provider-Credentials in einer
JSON-Datei unter /etc/enigma2/smartysiptv.json (Standard-Enigma2-Konfig-Pfad,
der ein Reboot übersteht).
"""

import os
import json

CONFIG_DIR = "/etc/enigma2"
CONFIG_FILE = os.path.join(CONFIG_DIR, "smartysiptv.json")


class Config(object):
    def __init__(self):
        self._data = {}

    # ---- Laden/Speichern ----
    def load(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                self._data = json.load(f)
        except (IOError, ValueError):
            self._data = {}
        return self

    def save(self):
        try:
            if not os.path.isdir(CONFIG_DIR):
                os.makedirs(CONFIG_DIR)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except IOError:
            pass  # Read-only rootfs etc. — nicht fatal

    # ---- Zugriff ----
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    # ---- Konkrete Felder ----
    def player_id(self):
        return self.get("player_id", "")

    def pairing_pw(self):
        return self.get("pairing_pw", "")

    def providers(self):
        return self.get("providers", [])  # Liste von {server_url, username, password}

    def set_providers(self, creds):
        self.set("providers", [
            {"server_url": c.url, "username": c.user, "password": c.password}
            for c in creds
        ])
