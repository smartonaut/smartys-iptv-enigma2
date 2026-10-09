# -*- coding: utf-8 -*-
"""
Smartys IPTV — Wiedergabe-Anbindung für Enigma2.

Wiedergabe über exteplayer3 (ffmpeg-basiert, robust für Xtream-Streams).
Der User-Agent ist ENTSCHEIDEND: viele Xtream-Server (line.smartytv.xyz)
blocken Requests ohne gültigen Browser-User-Agent mit HTTP 407.

Bewiesen auf VU+ Duo4K (openATV 7.6): exteplayer3 + Browser-UA spielt
den Stream sauber (PLAYBACK_PLAY sts:0, 1280x720 H.264, AC3 deutsch).

Engine-Priorität:
  1. exteplayer3 direkt (bewiesen funktionsfähig) — mit -u User-Agent
  2. exteplayer3 als Enigma2-Service (5002, via serviceapp, falls konfiguriert)
  3. GStreamer (4097) — letzter Fallback
"""

import os
import subprocess

# Browser-User-Agent (wie XStreamity Default) — sonst 407 vom Stream-Server.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")

SERVICE_EXTPLAYER3 = 5002
SERVICE_GSTREAMER = 4097


def _has(binary):
    return os.path.exists("/usr/bin/" + binary)


def _play_exteplayer3_direct(url):
    """exteplayer3 direkt aufrufen — der bewiesene, robuste Weg."""
    try:
        subprocess.Popen(["exteplayer3", url, "-u", USER_AGENT])
        return True
    except Exception:
        return False


def _play_via_service(session, url, servicetype):
    """Spielt die URL über Enigma2's Service-System (korrektes OSD/Fullscreen)."""
    try:
        from enigma import eServiceReference
        ref = eServiceReference(servicetype, 0, url)
        ref.setName(url)
        session.nav.playService(ref)
        return True
    except Exception:
        return False


def play(session, url):
    """Wählt die beste verfügbare Engine. Liefert True bei Erfolg."""
    # 1. exteplayer3 direkt (primär, bewiesen)
    if _has("exteplayer3"):
        if _play_exteplayer3_direct(url):
            return True
    # 2. exteplayer3 als Service (5002, via serviceapp)
    if _has("exteplayer3"):
        if _play_via_service(session, url, SERVICE_EXTPLAYER3):
            return True
    # 3. GStreamer (eingebauter Enigma2-Pfad)
    if _play_via_service(session, url, SERVICE_GSTREAMER):
        return True
    return False
