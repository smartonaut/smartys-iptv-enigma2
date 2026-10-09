# -*- coding: utf-8 -*-
"""Smartys IPTV — Wiedergabe über Enigma2-Service (exteplayer3).

Der Stream wird über session.nav.playService mit Servicetype 5002
(exteplayer3 via serviceapp) abgespielt. So übernimmt Enigma2 das
Video-Handling korrekt (Menü schließen, Video-Layer einblenden, OSD).

Der User-Agent kommt aus /etc/enigma2/exteplayer3.cfg (JSON),
nicht als -u Parameter — serviceapp ruft exteplayer3 ohne eigene Args auf.
"""

import json
import os

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")

EXTPLAYER3_CFG = "/etc/enigma2/exteplayer3.cfg"

SERVICE_EXTPLAYER3 = 5002
SERVICE_GSTREAMER = 4097


def ensure_user_agent():
    """Schreibt den Browser-User-Agent in die exteplayer3-Config (JSON).

    Viele Xtream-Server (line.smartytv.xyz) blocken Requests ohne
    gültigen Browser-User-Agent mit HTTP 407. exteplayer3 liest den
    User-Agent aus dieser Config-Datei.
    """
    try:
        cfg = {}
        if os.path.exists(EXTPLAYER3_CFG):
            with open(EXTPLAYER3_CFG, "r") as f:
                cfg = json.load(f)
        if cfg.get("user-agent") != USER_AGENT:
            cfg["user-agent"] = USER_AGENT
            with open(EXTPLAYER3_CFG, "w") as f:
                json.dump(cfg, f)
    except Exception:
        pass


def play(session, url):
    """Spielt die URL ab. Bevorzugt exteplayer3 (5002), sonst GStreamer (4097)."""
    ensure_user_agent()
    try:
        from enigma import eServiceReference
    except Exception:
        return False

    # 1. exteplayer3 (5002) — bevorzugt, robust für Xtream-Streams
    try:
        ref = eServiceReference(SERVICE_EXTPLAYER3, 0, url)
        ref.setName(url)
        session.nav.playService(ref)
        return True
    except Exception:
        pass

    # 2. GStreamer (4097) — eingebauter Enigma2-Pfad
    try:
        ref = eServiceReference(SERVICE_GSTREAMER, 0, url)
        ref.setName(url)
        session.nav.playService(ref)
        return True
    except Exception:
        return False
