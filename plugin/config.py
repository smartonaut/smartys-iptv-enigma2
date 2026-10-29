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
import hashlib

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

# Namespace der abgeleiteten Player-ID. Ändert sich dieser String, ändern
# sich ALLE neu vergebenen IDs — also nie ohne Migration anfassen.
_PID_NAMESPACE = b"smartys-iptv-player-id-v1|"

# Reihenfolge der Netzwerkschnittstellen für den Hardware-Fingerprint:
# zuerst die fest verbaute Leitung, dann WLAN. Sortiert wird nach dieser
# Priorität und danach alphabetisch — damit die Ableitung auf derselben
# Hardware immer identisch ist, egal in welcher Reihenfolge der Kernel
# die Interfaces auflistet.
_NIC_PRIORITY = ("eth0", "eth1", "lan0", "wlan0")
_NIC_IGNORE = ("lo",)

# Spiegel der Identität AUSSERHALB der Plugin-JSON. Zweck: ein Reflash oder
# ein versehentliches Löschen von /etc/enigma2 darf laufende Player nicht von
# ihrer Line abschneiden (die AAD hängt an der ID). /media/hdd überlebt einen
# Image-Flash, /etc/enigma2 nicht — deshalb steht das HDD zuerst.
# Reihenfolge = Abfrage-Reihenfolge. Kein Geheimnis, nur Komfort: wer die
# Datei lesen kann, konnte vorher auch die JSON lesen.
_IDENTITY_MIRRORS = (
    "/media/hdd/.smartysiptv-identity.json",
    "/etc/enigma2/.smartysiptv-identity.json",
)


def _mirror_read():
    """Erste vorhandene Identitäts-Spiegeldatei lesen. -> dict (evtl. leer)."""
    for path in _IDENTITY_MIRRORS:
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except (IOError, OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("player_id"):
            return data
    return {}


def _mirror_write(pid, pw=None, source=None):
    """Identität in alle beschreibbaren Spiegel schreiben (best effort)."""
    payload = {"player_id": pid}
    if pw:
        payload["pairing_pw"] = pw
    if source:
        payload["player_id_source"] = source
    for path in _IDENTITY_MIRRORS:
        try:
            folder = os.path.dirname(path)
            if not os.path.isdir(folder):
                continue
            tmp = path + ".tmp"
            with open(tmp, "w") as f:
                json.dump(payload, f, indent=2)
            os.rename(tmp, path)
        except (IOError, OSError):
            continue


def _read_text(path):
    try:
        with open(path, "rb") as f:
            return f.read().strip().decode("utf-8", "ignore")
    except (IOError, OSError):
        return ""


def hw_fingerprint_parts():
    """Stabile Hardware-Merkmale der Box, in fester Reihenfolge.

    Bewusst KEINE Zufallswerte und nichts, was der Nutzer ändern oder das
    Image überschreiben kann (hostname, machine-id fallen weg). `sn` ist die
    Geräteseriennummer aus dem Bootloader — der stärkste Anker.
    """
    parts = []
    for key in ("boxtype", "sn", "chipset", "board_revision"):
        value = _read_text("/proc/stb/info/" + key)
        if value:
            parts.append("%s=%s" % (key, value))
    # Netzwerk-MAC: nur zur Unterscheidung baugleicher Boxen ohne `sn`.
    try:
        names = [n for n in os.listdir("/sys/class/net") if n not in _NIC_IGNORE]
    except OSError:
        names = []
    names.sort(key=lambda n: (
        _NIC_PRIORITY.index(n) if n in _NIC_PRIORITY else len(_NIC_PRIORITY), n))
    for name in names:
        mac = _read_text("/sys/class/net/%s/address" % name)
        if mac and mac != "00:00:00:00:00:00":
            parts.append("nic=%s" % mac)
            break
    return parts


def hw_player_id():
    """Leitet die Player-ID DETERMINISTISCH aus der Hardware ab.

    Rückgabe: (player_id, quelle)

    Dieselbe Box ergibt nach Neuinstallation, GELB-Reset oder Reflash immer
    wieder dieselbe ID — ohne die echte MAC zu verwenden: die MAC geht nur
    als Hash-Eingabe ein, ist aus der ID nicht zurückrechenbar, und die ID
    trägt das lokal-administrierte Bit (02:..), ist also sichtbar keine
    Hardware-MAC.

    Kann keine Hardware gelesen werden (z. B. fremdes Image ohne
    /proc/stb/info), wird wie früher zufällig gewürfelt — dann ist die ID
    NICHT stabil, was die Quelle im Feld `player_id_source` offenlegt.
    """
    parts = hw_fingerprint_parts()
    if not parts:
        b = bytearray(secrets.token_bytes(6))
        b[0] = (b[0] & 0xFC) | 0x02
        return ":".join("%02X" % x for x in b), "random"
    digest = hashlib.sha256(_PID_NAMESPACE + "|".join(parts).encode("utf-8")).digest()
    b = bytearray(digest[:6])
    # lokal administriert (0x02) + unicast (Multicast-Bit 0x01 löschen)
    b[0] = (b[0] & 0xFC) | 0x02
    return ":".join("%02X" % x for x in b), "hw-v1"

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
        # Identität früh sichern: so entsteht der Spiegel schon beim ersten
        # Config-Load (irgendein Screen), nicht erst wenn der Pairing-Screen
        # geöffnet wird. Überlebt der Spiegel einen Reflash, ist die ID auch
        # dann noch da, wenn der Nutzer den Pairing-Screen nie wieder öffnet.
        pid = self._data.get("player_id", "")
        if pid:
            try:
                self._mirror_sync(pid)
            except Exception:
                pass
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

    # ---- Player-ID + Pairing-Passwort ----
    #
    # GRUNDREGEL: EINE BEREITS GESPEICHERTE Player-ID WIRD NIE ANGEFASST.
    # Viele Player laufen bei fremden Leuten im Feld; wer seine ID verliert,
    # verliert seine Line (die AAD bindet den Ciphertext an genau diese ID)
    # und kann sich nicht selbst helfen. Deshalb: kein Umbenennen, keine
    # Migration alter IDs, kein Neu-Würfeln — unter keinen Umständen.
    #
    # NEUE Player (keine ID in der JSON) bekommen eine ABGELEITETE Identität:
    #   ID = SHA-256(NAMESPACE | boxtype | sn | chipset | board_revision | eth-MAC)
    #        -> 6 Bytes, MAC-Format, Byte 0 = lokal-admin + unicast (02:..)
    # Damit ist dieselbe Hardware nach Neuinstallation / GELB / Reflash
    # IMMER wieder dieselbe ID, ohne dass die echte Hardware-MAC verwendet
    # oder veröffentlicht wird (Hash ist nicht umkehrbar).
    #
    # Reihenfolge der Suche (jede Stufe ist gültig, keine überschreibt die
    # vorherige):
    #   1. player_id in der Plugin-JSON        (Bestand — unantastbar)
    #   2. Identitäts-Spiegel (HDD / etc)      (überlebt Reflash & Löschen der JSON)
    #   3. aus der Hardware abgeleitet         (neue Installation)
    #
    # Siehe player_id(), pairing_pw() und reset().

    def player_id(self):
        pid = self.get("player_id", "")
        if pid:
            # Bestehende Identität: unantastbar (siehe Grundregel oben).
            self._mirror_sync(pid)
            return pid
        mirror = _mirror_read()
        if mirror.get("player_id"):
            # Aus dem Spiegel wiedergefunden (z. B. nach Reflash) — übernehmen.
            pid = mirror["player_id"]
            src = mirror.get("player_id_source", "mirror")
            if mirror.get("pairing_pw") and not self.get("pairing_pw"):
                self._data["pairing_pw"] = mirror["pairing_pw"]
            self.set("player_id", pid)
            self.set("player_id_source", src)
            return pid
        pid, source = hw_player_id()
        self.set("player_id", pid)
        self.set("player_id_source", source)
        self._mirror_sync(pid, source=source)
        return pid

    def _mirror_sync(self, pid, source=None):
        """Spiegel anlegen/auffüllen, ohne je eine andere ID zu überschreiben.

        Wichtig: existiert im HDD-Spiegel bereits eine ANDERE ID (Altgerät),
        wird sie NICHT ersetzt — der Spiegel ist ein Gedächtnis, kein Cache.
        """
        existing = _mirror_read()
        if existing.get("player_id") and existing["player_id"] != pid:
            return
        if existing.get("player_id") == pid and existing.get("pairing_pw"):
            return
        _mirror_write(
            pid,
            pw=self.get("pairing_pw", "") or None,
            source=source or self.get("player_id_source", "") or None,
        )

    def pairing_pw(self):
        pw = self.get("pairing_pw", "")
        if pw:
            return pw
        pw = "".join(secrets.choice(_PW_CHARS) for _ in range(12))
        self.set("pairing_pw", pw)
        # Passwort mit in den Spiegel, damit nach einem Reflash ID UND
        # Passwort wieder da sind (das Panel prüft beides gegen Argon2).
        self._mirror_sync(self.get("player_id", ""), source=None)
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
        """Pairing + Line löschen, IDENTITÄT BLEIBT.

        Player-ID und Pairing-Passwort werden bewusst BEHALTEN: der Nutzer
        will den Player löschen und auf derselben Hardware neu aufsetzen —
        und dabei dieselbe ID behalten (die Line hängt per AAD an ihr).
        Ein Neu-Würfeln hier würde im Feld laufende Player von ihren Lines
        abschneiden. Nur Lines/Session/EPG-Cache werden entfernt.
        """
        pid = self.get("player_id", "")
        src = self.get("player_id_source", "")
        ppw = self.get("pairing_pw", "")
        self._data = {}
        if pid:
            self._data["player_id"] = pid
            if src:
                self._data["player_id_source"] = src
        if ppw:
            self._data["pairing_pw"] = ppw
        self.save()
        _session["key"] = None
        _session["providers"] = []
        # EPG-Cache der alten Sender ebenfalls entfernen (epgbackup.CACHE_FILE).
        try:
            os.remove("/etc/enigma2/smartysiptv_epg.json")
        except OSError:
            pass
        return True
