# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Aufnahme (ffmpeg-basiert).

Die Aufnahme nutzt ffmpeg (auf der Box vorhanden) und schreibt den Stream
direkt als MPEG-TS nach /media/hdd/movie/ — identisch zum libVLC-Ansatz der
Desktop-Version (sout=#standard{access=file,mux=ts,dst=...}).

Der User-Agent ist entscheidend (sonst 407 vom Stream-Server).
"""

import os
import subprocess

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")

# Aufnahme-Verzeichnis (Enigma2-Standard)
REC_DIR = "/media/hdd/movie"


class Recorder(object):
    """Ein einzelner laufender ffmpeg-Aufnahmeprozess."""

    def __init__(self):
        self.proc = None
        self.output_path = None

    @property
    def recording(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, url, name):
        """Startet die Aufnahme. Liefert den Ausgabepfad oder wirft."""
        if self.recording:
            raise RuntimeError("Aufnahme läuft bereits")
        safe = "".join(c if c.isalnum() or c in " .-_" else "_" for c in name)
        if not safe.strip():
            safe = "recording"
        # Zeitstempel für eindeutigen Dateinamen
        import datetime
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(REC_DIR, "%s_%s.ts" % (safe, ts))
        if not os.path.isdir(REC_DIR):
            os.makedirs(REC_DIR, exist_ok=True)
        cmd = [
            "ffmpeg", "-y",
            "-user_agent", USER_AGENT,
            "-i", url,
            "-c", "copy",
            "-f", "mpegts",
            path,
        ]
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.output_path = path
        return path

    def stop(self):
        """Beendet die Aufnahme. Liefert den Ausgabepfad oder None."""
        if self.proc is None:
            return None
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()
        except Exception:
            pass
        path = self.output_path
        self.proc = None
        self.output_path = None
        return path


# Ein globaler Recorder (eine Aufnahme zur Zeit)
_recorder = None


def get_recorder():
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder
