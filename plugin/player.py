# -*- coding: utf-8 -*-
"""Smartys IPTV — Wiedergabe über Enigma2's playService.

Der eigentliche Player ist exteplayer3 (ffmpeg/OpenSource, installiert).
Dieses Modul ist nur der Wrapper, der exteplayer3 über Enigma2's
session.nav.playService einbindet — exakt wie XStreamity.

Servicetype 4097 = GStreamer (eingebaut), 5002 = exteplayer3 (serviceapp).

Zwei Modi (beide über playService):
  - Vollbild: StreamPlayerScreen öffnen (InfoBarBase rendert das Video)
  - Vorschau: playService direkt, Listen-Screen bleibt offen, Pig zeigt Video
"""

from enigma import eServiceReference

SERVICE_GSTREAMER = 4097
SERVICE_EXTPLAYER3 = 5002


def play_service(session, url, servicetype=SERVICE_GSTREAMER):
    """Spielt die URL über playService. Liefert True bei Erfolg."""
    try:
        ref = eServiceReference(int(servicetype), 0, url)
        ref.setName(url)
        session.nav.playService(ref)
        return True
    except Exception:
        return False


def open_player(session, url, servicetype=SERVICE_GSTREAMER, name=""):
    """Öffnet den Vollbild-StreamPlayer-Screen."""
    from .streamplayer import StreamPlayerScreen
    session.open(StreamPlayerScreen, url, servicetype, name)
