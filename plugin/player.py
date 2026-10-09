# -*- coding: utf-8 -*-
"""
Smartys IPTV — Wiedergabe-Anbindung für Enigma2.

Probiert die Player-Engines automatisch durch (wie IPTV-BOX/e2iplayer):
  1. exteplayer3  (ffmpeg-basiert, robust für Xtream-Redirects/403)
  2. GStreamer    (Standard)
  3. serviceapp   (exteplayer3/gstplayer als Dienst)

Der User-Agent ist entscheidend: viele Xtream-Server blocken Requests ohne
plausiblen User-Agent mit 403/Redirect-Schleifen.
"""

USER_AGENT = "SmartysIPTV-E2/1.0 (Enigma2)"


def _play_exteplayer3(url, user_agent):
    """exteplayer3 direkt aufrufen (eigenständiges Binary, ffmpeg)."""
    try:
        from subprocess import Popen
        # exteplayer3 liegt je nach Image unter /usr/bin/exteplayer3
        Popen(["exteplayer3", url], env=_with_ua(user_agent))
        return True
    except Exception:
        return False


def _play_gstreamer(url, user_agent):
    """GStreamer-basierte Wiedergabe über die Enigma2-ServiceAPI."""
    try:
        from enigma import eServiceReference, eServiceCenter
        ref = eServiceReference(eServiceReference.idGST, 0, url)
        ref.setName(url)
        eServiceCenter.getInstance().playService(ref)
        return True
    except Exception:
        return False


def _play_serviceapp(url, user_agent):
    """serviceapp (exteplayer3/gstplayer als Service) nutzen."""
    try:
        from enigma import eServiceReference, eServiceCenter
        # 4097 = serviceapp-Player (abhängig vom Image), hier als Fallback
        ref = eServiceReference(4097, 0, url)
        ref.setName(url)
        eServiceCenter.getInstance().playService(ref)
        return True
    except Exception:
        return False


def _with_ua(user_agent):
    import os
    env = os.environ.copy()
    env["HTTP_USER_AGENT"] = user_agent
    return env


def play(url):
    """Versucht die Engines der Reihe nach. Liefert True bei Erfolg."""
    for engine in (_play_exteplayer3, _play_gstreamer, _play_serviceapp):
        try:
            if engine(url, USER_AGENT):
                return True
        except Exception:
            continue
    return False
