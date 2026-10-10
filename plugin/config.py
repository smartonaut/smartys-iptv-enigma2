# -*- coding: utf-8 -*-
"""
Smartys IPTV — Konfiguration & Persistenz für Enigma2.

Speichert Player-ID, Pairing-Passwort und Provider-Credentials in einer
JSON-Datei unter /etc/enigma2/smartysiptv.json (Standard-Enigma2-Konfig-Pfad,
der ein Reboot übersteht).
"""

import os
import json
import secrets

CONFIG_DIR = "/etc/enigma2"
CONFIG_FILE = os.path.join(CONFIG_DIR, "smartysiptv.json")

# Standardwerte für die einstellbaren Optionen (werden beim Laden ergänzt).
DEFAULTS = {
    "rec_dir": "/media/hdd/movie",
    "timeshift": True,
    "confirm_switch": True,
    "preview": True,
}

_PW_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"


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
        # Fehlende Optionen mit Standardwerten auffüllen.
        for k, v in DEFAULTS.items():
            self._data.setdefault(k, v)
        return self

    def save(self):
        try:
            if not os.path.isdir(CONFIG_DIR):
                os.makedirs(CONFIG_DIR)
            with open(CONFIG_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except IOError as exc:
            # Read-only rootfs etc. — nicht fatal, aber mindestens loggen,
            # damit Pairing-/Settings-Probleme nicht still verschluckt werden.
            try:
                print("[SmartysIPTV] config.save() fehlgeschlagen: %s" % exc)
            except Exception:
                pass

    # ---- Zugriff ----
    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    # ---- Player-ID + Pairing-Passwort (einmalig generiert) ----
    #
    # Identisch zur Desktop/Android-Version (CredStore.kt):
    #   Player-ID = 6 Bytes im MAC-Format, Byte 0 = lokal-admin-Bit (02:...)
    #   Pairing-PW = 12 Zeichen, kryptographisch sicher.

    def player_id(self):
        pid = self.get("player_id", "")
        if pid:
            return pid
        b = bytearray(secrets.token_bytes(6))
        b[0] = (b[0] & 0xFE) | 0x02
        pid = ":".join("%02X" % x for x in b)
        self.set("player_id", pid)
        return pid

    def pairing_pw(self):
        pw = self.get("pairing_pw", "")
        if pw:
            return pw
        pw = "".join(secrets.choice(_PW_CHARS) for _ in range(12))
        self.set("pairing_pw", pw)
        return pw

    def providers(self):
        return self.get("providers", [])  # Liste von {server_url, username, password}

    def set_providers(self, creds):
        self.set("providers", [
            {"server_url": c.url, "username": c.user, "password": c.password}
            for c in creds
        ])
