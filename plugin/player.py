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


def open_player(session, url, servicetype=SERVICE_GSTREAMER, name="",
                stream_id=None, api=None, stream_icon=None):
    """Öffnet den Vollbild-StreamPlayer-Screen (mit EPG-Infobar)."""
    from .streamplayer import StreamPlayerScreen
    session.open(StreamPlayerScreen, url, servicetype, name, stream_id,
                 api, stream_icon)


def download_trailer(url):
    """Lädt einen Trailer (YouTube-ID oder URL) als lokale MP4-Datei.

    exteplayer3 kann YouTube nicht direkt abspielen; deshalb lädt yt-dlp
    den Trailer als gemergte MP4 (Video+Audio) herunter, die dann lokal
    abgespielt wird. Rückgabe: lokaler Pfad oder None.
    """
    import hashlib
    import os
    import subprocess
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://www.youtube.com/watch?v=%s" % url
    key = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    path = "/tmp/trailer_%s.mp4" % key
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return path
    try:
        cmd = ["yt-dlp", "-f", "bestvideo[height<=480]+bestaudio/best",
               "--merge-output-format", "mp4", "--no-playlist",
               "-o", path, url]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        proc.wait(timeout=180)
        if os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None
