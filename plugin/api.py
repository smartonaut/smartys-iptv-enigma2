# -*- coding: utf-8 -*-
"""
Smartys IPTV — Xtream-Codes-API-Client (Python 3, für Enigma2).

Portiert aus der Desktop/Android-Version (XtreamApi.kt). Nutzt ausschließlich
die Standardbibliothek (urllib) + json, damit das Plugin auf Enigma2-Boxen
ohne zusätzliche Python-Pakete läuft.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
import ssl

# Ignoriere selbst-signierte/abgelaufene Zertifikate — IPTV-Panels nutzen
# häufig eigene Zertifikate. (Wie die Desktop-Version, die auch über
# HttpsURLConnection mit Standard-Zertifikatsvalidierung läuft.)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

# Für das eigene Panel (panel.smartys.tech) Zertifikatsvalidierung aktiv lassen —
# dort laufen die Pairing-Credentials, und das Panel hat ein gültiges
# Let's-Encrypt-Zertifikat (Traefik). Nur die IPTV-Provider-URLs bleiben lax.
_PANEL_SSL_CTX = ssl.create_default_context()

# Browser-User-Agent (wie beim Stream) — einige Xtream-Server blocken
# Requests ohne gültigen Browser-UA auch auf der player_api.php mit 407.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")


class ApiError(Exception):
    pass


class Credentials(object):
    """Ein Provider (Server + Zugangsdaten)."""

    def __init__(self, url, user, password):
        self.url = url.rstrip("/")
        self.user = user
        self.password = password

    def _base(self):
        return "%s/player_api.php?username=%s&password=%s" % (
            self.url,
            urllib.parse.quote(self.user),
            urllib.parse.quote(self.password),
        )

    def stream_url(self, stream_id, ext="ts"):
        return "%s/live/%s/%s/%s.%s" % (
            self.url, urllib.parse.quote(self.user),
            urllib.parse.quote(self.password), stream_id, ext)

    def _resolve_redirect(self, url):
        """Folgt einem 302-Redirect (Hoster) und liefert die finale URL.

        Viele VOD/Serien liegen nicht direkt auf dem Xtream-Server, sondern
        werden per 302 auf einen externen Hoster umgeleitet. Der Player folgt
        dem Redirect nicht — deshalb hier auflösen (nur 1 Byte via Range).
        """
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"})
            with urllib.request.urlopen(
                    req, timeout=10, context=_SSL_CTX) as r:
                final = r.geturl()
                if final and final != url:
                    return final
        except Exception:
            pass
        return url

    def movie_url(self, stream_id, ext="mp4"):
        url = "%s/movie/%s/%s/%s.%s" % (
            self.url, urllib.parse.quote(self.user),
            urllib.parse.quote(self.password), stream_id, ext)
        return self._resolve_redirect(url)

    def series_url(self, episode_id, ext="mp4"):
        url = "%s/series/%s/%s/%s.%s" % (
            self.url, urllib.parse.quote(self.user),
            urllib.parse.quote(self.password), episode_id, ext)
        return self._resolve_redirect(url)


class XtreamApi(object):
    """Synchroner Client für die Xtream player_api.php."""

    def __init__(self, creds):
        self.creds = creds

    # ---- Low-level ----
    def _get_json(self, path, params=None):
        p = params or {}
        p["username"] = self.creds.user
        p["password"] = self.creds.password
        url = "%s/player_api.php?%s" % (self.creds.url, urllib.parse.urlencode(p))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise ApiError("HTTP %s" % e.code)
        except Exception as e:
            raise ApiError(str(e))

    # ---- Auth ----
    def auth(self):
        return self._get_json("player_api.php")  # liefert user_info + server_info

    # ---- Live-TV ----
    def live_categories(self):
        return self._get_json("player_api.php", {"action": "get_live_categories"})

    def live_streams(self, category_id=None):
        p = {"action": "get_live_streams"}
        if category_id:
            p["category_id"] = category_id
        return self._get_json("player_api.php", p)

    def short_epg(self, stream_id, limit=2):
        return self._get_json("player_api.php", {
            "action": "get_short_epg", "stream_id": stream_id, "limit": str(limit)})

    # ---- VOD (Filme) ----
    def vod_categories(self):
        return self._get_json("player_api.php", {"action": "get_vod_categories"})

    def vod_streams(self, category_id=None):
        p = {"action": "get_vod_streams"}
        if category_id:
            p["category_id"] = category_id
        return self._get_json("player_api.php", p)

    def vod_info(self, vod_id):
        return self._get_json("player_api.php", {
            "action": "get_vod_info", "vod_id": vod_id})

    # ---- Serien ----
    def series_categories(self):
        return self._get_json("player_api.php", {"action": "get_series_categories"})

    def series_streams(self, category_id=None):
        p = {"action": "get_series"}
        if category_id:
            p["category_id"] = category_id
        return self._get_json("player_api.php", p)

    def series_info(self, series_id):
        return self._get_json("player_api.php", {
            "action": "get_series_info", "series_id": series_id})


def pair_with_panel(player_id, pairing_pw, panel="https://panel.smartys.tech"):
    """
    Pairing-Flow (identisch zur Desktop-Version DesktopViewModel.pairAndLoad):
      1. POST /api/v1/pair   mit mac=<player_id>&password=<pairing_pw>  -> token
      2. GET  /api/v1/providers mit Authorization: Bearer ***      -> payload
    Rückgabe: das Payload-Dict des Panels.

    Zwei Fälle:
      - {"encrypted": true, salt, iterations, providers: [{label, cipher_*}...]}
        => Panel-Spieler MIT Sicherheits-Passwort. Entschlüsselung passiert
        LOKAL mit dem Nutzer-Passwort (siehe config.store_panel_payload).
      - {"providers": [{server_url, username, password}...]}
        => Alt-Format (Panel-Spieler ohne Sicherheits-Passwort), Klartext.
    """
    # Schritt 1: Pair
    body = urllib.parse.urlencode({
        "mac": player_id,
        "password": pairing_pw,
    }).encode("utf-8")
    req = urllib.request.Request(
        panel + "/api/v1/pair", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_PANEL_SSL_CTX) as r:
            token = json.loads(r.read().decode("utf-8")).get("token")
    except Exception as e:
        raise ApiError("Pairing fehlgeschlagen: %s" % e)
    if not token:
        raise ApiError("Kein Token vom Panel erhalten")

    # Schritt 2: Provider laden
    req = urllib.request.Request(
        panel + "/api/v1/providers",
        headers={"Authorization": "Bearer " + token, "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_PANEL_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ApiError("Provider-Laden fehlgeschlagen: %s" % e)
    return data


def delete_player_remote(player_id, pairing_pw, panel="https://panel.smartys.tech"):
    """'Pairing loeschen': entfernt den Player komplett aus dem Panel.

    Auth ueber MAC + Pairing-Passwort. Wirft ApiError bei Fehlschlag.
    404 (Player im Panel schon weg) gilt als Erfolg — lokal wird trotzdem
    zurueckgesetzt."""
    body = urllib.parse.urlencode({
        "mac": player_id,
        "password": pairing_pw,
    }).encode("utf-8")
    req = urllib.request.Request(
        panel + "/api/v1/player/delete", data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded",
                 "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_PANEL_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {"ok": True, "already_gone": True}
        raise ApiError("Löschen fehlgeschlagen: HTTP %s" % e.code)
    except Exception as e:
        raise ApiError("Löschen fehlgeschlagen: %s" % e)
    if not data.get("ok"):
        raise ApiError("Löschen fehlgeschlagen")
    return data


def providers_to_credentials(provs):
    """Alt-Format-Provider (Klartext) in Credentials wandeln."""
    creds = []
    for p in provs:
        creds.append(Credentials(
            p.get("server_url", ""),
            p.get("username", ""),
            p.get("password", "")))
    return creds
