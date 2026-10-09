# -*- coding: utf-8 -*-
"""Smartys IPTV — Wiedergabe über Enigma2-Service (exteplayer3 via serviceapp).

Der Stream wird über session.nav.playService(eServiceReference(5002, 0, url))
abgespielt. Servicetype 5002 = exteplayer3 (via serviceapp) — Enigma2 übernimmt
den Video-Decoder korrekt und zeigt das Video.

exteplayer3 spielt den Stream auch ohne expliziten User-Agent (bewiesen:
PLAYBACK_OPEN sts:0). Der 407 betraf nur GStreamer/wget, nicht exteplayer3.

WICHTIG: Der Aufrufer entscheidet, ob der Screen geschlossen wird:
  - Vollbild: self.close() nach play() -> Enigma2 zeigt Video im Vollbild
  - Vorschau: Screen offen lassen -> Pig-Widget zeigt Video im kleinen Fenster
"""

import subprocess
import os

EXTPLAYER3 = "/usr/bin/exteplayer3"
SERVICE_EXTPLAYER3 = 5002


def play(session, url):
    """Spielt die URL über exteplayer3-Service (5002). Liefert True bei Erfolg."""
    try:
        from enigma import eServiceReference
        ref = eServiceReference(SERVICE_EXTPLAYER3, 0, url)
        ref.setName(url)
        session.nav.playService(ref)
        return True
    except Exception:
        return False


def play_exteplayer3_direct(url):
    """Fallback: exteplayer3 direkt (rendert auf Decoder, ohne Enigma2-Service)."""
    if not os.path.exists(EXTPLAYER3):
        return False
    try:
        subprocess.Popen([EXTPLAYER3, url],
                         stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False
