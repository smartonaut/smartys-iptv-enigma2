# -*- coding: utf-8 -*-
"""
Smartys IPTV — Xtream-Codes-API-Client (Python 3, für Enigma2).

Portiert aus der Desktop/Android-Version (XtreamApi.kt). Nutzt ausschließlich
die Standardbibliothek (urllib) + json, damit das Plugin auf Enigma2-Boxen
ohne zusätzliche Python-Pakete läuft.
"""

import json
import urllib.parse
import urllib.request
import ssl

# Ignoriere selbst-signierte/abgelaufene Zertifikate — IPTV-Panels nutzen
# häufig eigene Zertifikate. (Wie die Desktop-Version, die auch über
# HttpsURLConnection mit Standard-Zertifikatsvalidierung läuft.)
_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

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
            self.url, self.user, self.password, stream_id, ext)

    def movie_url(self, stream_id, ext="mp4"):
        return "%s/movie/%s/%s/%s.%s" % (
            self.url, self.user, self.password, stream_id, ext)

    def series_url(self, episode_id, ext="mp4"):
        return "%s/series/%s/%s/%s.%s" % (
            self.url, self.user, self.password, episode_id, ext)


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
      2. GET  /api/v1/providers mit Authorization: Bearer <token>      -> providers
    Liefert eine Liste von Credentials (server_url/username/password).
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
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
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
        with urllib.request.urlopen(req, timeout=10, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        raise ApiError("Provider-Laden fehlgeschlagen: %s" % e)

    providers = data.get("providers") or []
    creds = []
    for p in providers:
        creds.append(Credentials(
            p.get("server_url", ""),
            p.get("username", ""),
            p.get("password", "")))
    return creds
