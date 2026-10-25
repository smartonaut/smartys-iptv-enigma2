# -*- coding: utf-8 -*-
"""
Smartys IPTV — Konfiguration & Persistenz für Enigma2.

Speichert Player-ID, Pairing-Passwort und Provider-Credentials in einer
JSON-Datei unter /etc/enigma2/smartysiptv.json (Standard-Enigma2-Konfig-Pfad,
der ein Reboot übersteht).

VERSCHLÜSSELTE SPEICHERUNG (Sicherheits-Passwort-Feature):
  - Lokale Eingabe: Line wird mit dem vom Nutzer gewählten Sicherheits-
    Passwort AES-256-GCM-verschlüsselt (PBKDF2-HMAC-SHA256) gespeichert.
  - Panel-Pairing: das Panel liefert die Line bereits verschlüsselt
    (Nutzer-Schlüssel); der Ciphertext wird 1:1 lokal abgelegt.
  - In BEIDEN Fällen liegt in smartysiptv.json nur Ciphertext. Der
    Klartext existiert ausschließlich im RAM, nachdem der Nutzer das
    Sicherheits-Passwort eingegeben hat (unlock()).
  - Die Line wird dabei NIE an panel.smartys.tech übertragen (lokaler Modus).
"""
import os
import json
import secrets

from . import crypto as sec

CONFIG_DIR = "/etc/enigma2"
CONFIG_FILE = os.path.join(CONFIG_DIR, "smartysiptv.json")

# Standardwerte für die einstellbaren Optionen (werden beim Laden ergänzt).
DEFAULTS = {
    "rec_dir": "/media/hdd/movie",
    "timeshift": True,
    "confirm_switch": True,
    "preview": True,
    "show_in_main_menu": False,
    # Favoriten: Liste von stream_ids (als String). Die App arbeitet mit
    # genau einer Line (providers[0]); bei mehreren Lines koennen sich die
    # IDs ueberschneiden.
    "favorites": [],
}

_PW_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789"

SEC_VERIFY_PLAINTEXT = "smartys-sec-password-ok"

# Sitzungs-Zustand (nur RAM): entsperrte Provider + Key. Bewusst NICHT
# persistiert — nach Neustart muss das Sicherheits-Passwort neu eingegeben
# werden (genau das ist der Sinn der Verschlüsselung).
_session = {"key": None, "providers": []}


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

    # ============================ FAVORITEN ============================

    def favorites(self):
        return [str(x) for x in (self.get("favorites") or [])]

    def is_favorite(self, stream_id):
        return str(stream_id) in self.favorites()

    def toggle_favorite(self, stream_id):
        """Favorit an/aus. Rueckgabe: True, wenn jetzt Favorit."""
        sid = str(stream_id)
        favs = self.favorites()
        if sid in favs:
            favs.remove(sid)
            neu = False
        else:
            favs.append(sid)
            neu = True
        self.set("favorites", favs)
        return neu

    # ====================== VERSCHLÜSSELTE PROVIDER ======================

    def has_encrypted(self):
        """Liegt verschlüsselter Bestand vor (Panel-Payload oder lokal)?"""
        return bool(self.get("providers_enc"))

    def has_legacy_plaintext(self):
        """Altformat (Klartext) vorhanden? (Migration nötig, selten.)"""
        return bool(self.get("providers"))

    def is_locked(self):
        """Verschlüsselt vorhanden UND noch nicht entsperrt (kein Klartext abgelegt)?"""
        return (self.has_encrypted() and not _session["providers"]
                and not self.get("providers"))

    def providers(self):
        """Provider-Liste (Klartext).

        Reihenfolge: RAM-Session (gerade entsperrt) → lokal abgelegter
        Klartext (einmaliges Entsperren, danach kein Passwort nötig) →
        [] wenn verschlüsselt + gesperrt."""
        if _session["providers"]:
            return list(_session["providers"])
        legacy = self.get("providers", []) or []
        if legacy:
            return [{"server_url": p.get("server_url", ""),
                     "username": p.get("username", ""),
                     "password": p.get("password", ""),
                     "label": p.get("label", "")} for p in legacy]
        return []

    def unlock(self, password):
        """Entsperrt mit dem Sicherheits-Passwort. Füllt die RAM-Session.

        Rückgabe: True bei Erfolg, False bei falschem Passwort."""
        if not self.has_encrypted():
            return True  # nichts zu entsperren
        if not sec.crypto_available():
            return False
        salt = self.get("sec_salt", "")
        key = sec.derive_key(password, salt)
        # Verify-Token prüfen (falsches Passwort => GCM-Auth-Fehler => "")
        verify = self.get("sec_verify", "")
        if sec.decrypt_text(key, verify, self.player_id()) != SEC_VERIFY_PLAINTEXT:
            return False
        provs = []
        for enc in (self.get("providers_enc") or []):
            d = sec.decrypt_provider(key, enc.get("cipher", ""), self.player_id())
            if d:
                d.setdefault("label", enc.get("label", ""))
                provs.append(d)
        if not provs:
            return False
        _session["key"] = key
        _session["providers"] = provs
        # Klartext lokal ablegen (einmaliges Entsperren, danach kein Passwort
        # mehr — gleiche Entscheidung wie beim Desktop-Player).
        self.set("providers", provs)
        return True

    def _encrypt_and_store(self, provs, user_password, salt=None):
        """Verschlüsselt Provider-Liste mit Nutzer-Passwort und speichert."""
        salt = salt or sec.new_salt()
        key = sec.derive_key(user_password, salt)
        pid = self.player_id()
        enc_list = []
        for p in provs:
            payload = {"server_url": p.get("server_url", ""),
                       "username": p.get("username", ""),
                       "password": p.get("password", ""),
                       "epg_url": p.get("epg_url", "")}
            enc_list.append({
                "label": p.get("label", "") or "Meine Line",
                "cipher": sec.encrypt_provider(key, payload, pid),
            })
        self.set("sec_salt", salt)
        self.set("sec_verify", sec.encrypt_text(key, SEC_VERIFY_PLAINTEXT, pid))
        self.set("providers_enc", enc_list)
        # Altformat-Klartext NICHT behalten (nur Ciphertext auf der Platte).
        if "providers" in self._data:
            self._data.pop("providers", None)
            self.save()
        _session["key"] = key
        _session["providers"] = [
            {"server_url": p["server_url"], "username": p["username"],
             "password": p["password"], "epg_url": p.get("epg_url", ""),
             "label": p.get("label", "") or "Meine Line"}
            for p in provs
        ]

    def store_local_line(self, server_url, username, password, user_password,
                         epg_url="", label="Lokale Line"):
        """LOKALE Eingabe: Line verschlüsselt auf der Box speichern.
        Es wird NICHTS an das Panel gesendet."""
        provs = [{"server_url": server_url.strip(),
                  "username": username.strip(),
                  "password": password,
                  "epg_url": epg_url.strip(),
                  "label": label}]
        self._encrypt_and_store(provs, user_password)

    def store_panel_payload(self, payload, user_password):
        """Panel-Pairing (verschlüsseltes Payload): Ciphertext 1:1 ablegen,
        Salt vom Panel übernehmen, lokal entsperren."""
        salt = payload.get("salt", "")
        if not salt:
            return False
        provs = payload.get("providers", []) or []
        if not provs:
            return False
        key = sec.derive_key(user_password, salt)
        pid = self.player_id()
        enc_list = []
        plain_list = []
        for p in provs:
            d = {
                "server_url": sec.decrypt_text(key, p.get("cipher_server_url", ""), pid),
                "username": sec.decrypt_text(key, p.get("cipher_username", ""), pid),
                "password": sec.decrypt_text(key, p.get("cipher_password", ""), pid),
                "epg_url": sec.decrypt_text(key, p.get("cipher_epg_url", ""), pid),
            }
            if not (d["server_url"] and d["username"]):
                return False  # falsches Passwort
            payload_json = {"server_url": d["server_url"], "username": d["username"],
                            "password": d["password"], "epg_url": d["epg_url"]}
            enc_list.append({"label": p.get("label", "") or "Meine Line",
                             "cipher": sec.encrypt_text(key, json.dumps(payload_json), pid)})
            plain_list.append(dict(d, label=p.get("label", "") or "Meine Line"))
        self.set("sec_salt", salt)
        self.set("sec_verify", sec.encrypt_text(key, SEC_VERIFY_PLAINTEXT, pid))
        self.set("providers_enc", enc_list)
        if "providers" in self._data:
            self._data.pop("providers", None)
            self.save()
        _session["key"] = key
        _session["providers"] = plain_list
        return True

    def set_providers_legacy(self, creds):
        """Alt-Pfad (Panel OHNE Sicherheits-Passwort): Klartext wie bisher."""
        self.set("providers", [
            {"server_url": c.url, "username": c.user, "password": c.password,
             "label": ""}
            for c in creds
        ])
        _session["providers"] = [
            {"server_url": c.url, "username": c.user, "password": c.password,
             "label": ""}
            for c in creds
        ]

    def reset(self):
        """Kompletter Neuinstall: Player-ID, Pairing-PW, Lines + Session weg.
        Beim naechsten Zugriff werden frische Werte generiert."""
        self._data = {}
        self.save()
        _session["key"] = None
        _session["providers"] = []
        # EPG-Cache der alten Sender ebenfalls entfernen (epgbackup.CACHE_FILE).
        try:
            os.remove("/etc/enigma2/smartysiptv_epg.json")
        except OSError:
            pass
        return True
