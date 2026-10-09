# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Aufnahme (ffmpeg-basiert).

Die Aufnahme nutzt ffmpeg (auf der Box vorhanden) und schreibt den Stream
direkt als MPEG-TS nach /media/hdd/movie/ — identisch zum libVLC-Ansatz der
Desktop-Version (sout=#standard{access=file,mux=ts,dst=...}).

Der User-Agent ist entscheidend (sonst 407 vom Stream-Server).
"""

import os
import subprocess
import time

try:
    from enigma import eTimer
except Exception:
    eTimer = None

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
        self._stop_timer = None

    @property
    def recording(self):
        return self.proc is not None and self.proc.poll() is None

    def start(self, url, name, end_ts=None):
        """Startet die Aufnahme. Liefert den Ausgabepfad oder wirft.

        end_ts: optionaler Unix-Timestamp — die Aufnahme stoppt dann
        automatisch zu dieser Zeit (z.B. Ende der Sendung).
        """
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
        if end_ts:
            self._schedule_stop(end_ts)
        return path

    def _schedule_stop(self, end_ts):
        """Plant das automatische Stoppen zur Endzeit."""
        delay_ms = max(1000, int((end_ts - time.time()) * 1000))
        self._stop_timer = eTimer()
        try:
            self._stop_timer.callback.append(self._auto_stop)
        except Exception:
            self._stop_timer.timeout.connect(self._auto_stop)
        self._stop_timer.start(delay_ms, True)

    def _auto_stop(self):
        if self.recording:
            self.stop()

    def stop(self):
        """Beendet die Aufnahme. Liefert den Ausgabepfad oder None."""
        if self._stop_timer is not None:
            try:
                self._stop_timer.stop()
            except Exception:
                pass
            self._stop_timer = None
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


class TimerScheduler(object):
    """Geplante (Timer-)Aufnahmen: startet/stoppt ffmpeg zur eingetragenen Zeit.

    Ein eTimer prüft alle 30 Sekunden, ob eine geplante Aufnahme fällig ist.
    """

    def __init__(self):
        self.timers = []  # dicts: url, name, start, end, proc
        self._timer = None
        if eTimer is not None:
            self._timer = eTimer()
            try:
                self._timer.callback.append(self._check)
            except Exception:
                self._timer.timeout.connect(self._check)

    def schedule(self, url, name, start_ts, end_ts):
        """Plant eine Aufnahme (Unix-Timestamps). Liefert die Timer-ID (dict)."""
        entry = {
            "url": url, "name": name,
            "start": int(start_ts), "end": int(end_ts),
            "proc": None, "done": False,
        }
        self.timers.append(entry)
        self._ensure_running()
        return entry

    def pending(self):
        """Liste aller geplanten, noch nicht abgeschlossenen Timer."""
        return [t for t in self.timers if not t["done"]]

    def _ensure_running(self):
        if self._timer is not None:
            try:
                self._timer.start(30000, False)
            except Exception:
                pass

    def _check(self):
        now = int(time.time())
        changed = False
        for t in self.timers:
            if t["done"]:
                continue
            # Start fällig?
            if t["proc"] is None and now >= t["start"] and now < t["end"]:
                safe = "".join(
                    c if c.isalnum() or c in " .-_" else "_" for c in t["name"])
                if not safe.strip():
                    safe = "recording"
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                path = os.path.join(REC_DIR, "%s_%s.ts" % (safe, ts))
                if not os.path.isdir(REC_DIR):
                    os.makedirs(REC_DIR, exist_ok=True)
                cmd = ["ffmpeg", "-y", "-user_agent", USER_AGENT,
                       "-i", t["url"], "-c", "copy", "-f", "mpegts", path]
                try:
                    t["proc"] = subprocess.Popen(
                        cmd, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
                except Exception:
                    t["proc"] = None
                changed = True
            # Stop fällig?
            elif t["proc"] is not None and now >= t["end"]:
                try:
                    t["proc"].terminate()
                    try:
                        t["proc"].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        t["proc"].kill()
                        t["proc"].wait()
                except Exception:
                    pass
                t["proc"] = None
                t["done"] = True
                changed = True
        if changed:
            self._ensure_running()

    def cancel(self, entry):
        if entry["proc"] is not None:
            try:
                entry["proc"].terminate()
            except Exception:
                pass
        entry["done"] = True


_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = TimerScheduler()
    return _scheduler


def ask_recording(session, url, name, api=None, stream_id=None):
    """Zeigt die Aufnahme-Abfrage (endlos vs. bis Sendungsende) und startet."""
    from Screens.ChoiceBox import ChoiceBox
    from Screens.MessageBox import MessageBox
    import datetime

    rec = get_recorder()

    # EPG-Ende ermitteln (falls verfügbar).
    end_ts = None
    end_label = ""
    if api and stream_id:
        try:
            data = api.short_epg(stream_id, limit=1)
            listings = data.get("epg_listings", []) or []
            if listings:
                end_ts = int(listings[0].get("stop_timestamp", "0"))
                if end_ts:
                    end_label = datetime.datetime.fromtimestamp(
                        end_ts).strftime("%H:%M")
        except Exception:
            end_ts = None

    choices = [(_("Endlos (bis manuell gestoppt)"), "endless")]
    if end_ts:
        choices.append((_("Bis Ende der Sendung (%s)") % end_label, "epg"))

    def _done(result):
        if result is None:
            return
        mode = result[1] if isinstance(result, (tuple, list)) else "endless"
        try:
            if mode == "epg" and end_ts:
                path = rec.start(url, name, end_ts=end_ts)
            else:
                path = rec.start(url, name)
        except Exception as e:
            session.open(
                MessageBox, _("Aufnahme fehlgeschlagen: %s") % str(e),
                MessageBox.TYPE_ERROR, timeout=5)
            return
        session.open(
            MessageBox, _("Aufnahme gestartet:\n%s") % path,
            MessageBox.TYPE_INFO, timeout=5)

    session.openWithCallback(
        _done, ChoiceBox, title=_("Aufnahme"), list=choices)
