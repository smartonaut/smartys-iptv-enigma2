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
import base64
import json

try:
    from enigma import eTimer
except Exception:
    eTimer = None

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")

# Aufnahme-Verzeichnis (Standard; überschreibbar in den Einstellungen)
REC_DIR = "/media/hdd/movie"


def _rec_dir():
    """Aktuelles Aufnahme-Verzeichnis aus den Einstellungen."""
    try:
        from .config import Config
        return Config().load().get("rec_dir", REC_DIR)
    except Exception:
        return REC_DIR


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
        rdir = _rec_dir()
        path = os.path.join(rdir, "%s_%s.ts" % (safe, ts))
        if not os.path.isdir(rdir):
            os.makedirs(rdir, exist_ok=True)
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


TIMERS_FILE = "/etc/enigma2/smartysiptv_timers.json"


class TimerScheduler(object):
    """Geplante (Timer-)Aufnahmen: startet/stoppt ffmpeg zur eingetragenen Zeit.

    Ein eTimer prüft alle 30 Sekunden, ob eine geplante Aufnahme fällig ist.
    Die Timer werden in einer JSON-Datei persistiert und überleben so
    Enigma2-Neustarts; der Scheduler läuft unabhängig vom Player.
    """

    def __init__(self):
        self.timers = self._load()  # dicts: url, name, start, end, proc, done
        self._timer = None
        if eTimer is not None:
            self._timer = eTimer()
            try:
                self._timer.callback.append(self._check)
            except Exception:
                self._timer.timeout.connect(self._check)
        # Timer sofort aufnehmen, falls schon etwas fällig ist.
        self._ensure_running()

    def _load(self):
        now = int(time.time())
        out = []
        try:
            if os.path.exists(TIMERS_FILE):
                with open(TIMERS_FILE, "r") as f:
                    data = json.load(f)
                for t in data:
                    try:
                        if int(t["end"]) > now:
                            out.append({
                                "url": t["url"], "name": t["name"],
                                "start": int(t["start"]), "end": int(t["end"]),
                                "proc": None, "done": False,
                            })
                    except Exception:
                        continue
        except Exception:
            pass
        return out

    def _save(self):
        try:
            data = [{"url": t["url"], "name": t["name"],
                     "start": t["start"], "end": t["end"]}
                    for t in self.timers if not t["done"]]
            with open(TIMERS_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass

    def schedule(self, url, name, start_ts, end_ts):
        """Plant eine Aufnahme (Unix-Timestamps). Liefert die Timer-ID (dict)."""
        entry = {
            "url": url, "name": name,
            "start": int(start_ts), "end": int(end_ts),
            "proc": None, "done": False,
        }
        self.timers.append(entry)
        self._save()
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
            # Zeitfenster verstrichen, ohne dass die Aufnahme je gestartet
            # wurde (z.B. Box war beim Start aus) -> aufräumen, sonst bleibt
            # der Eintrag für immer in der Timer-Liste hängen.
            if t["proc"] is None and now >= t["end"]:
                t["done"] = True
                changed = True
                continue
            # Start fällig?
            if t["proc"] is None and now >= t["start"] and now < t["end"]:
                safe = "".join(
                    c if c.isalnum() or c in " .-_" else "_" for c in t["name"])
                if not safe.strip():
                    safe = "recording"
                import datetime
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                rdir = _rec_dir()
                path = os.path.join(rdir, "%s_%s.ts" % (safe, ts))
                if not os.path.isdir(rdir):
                    os.makedirs(rdir, exist_ok=True)
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
            self._save()
            self._ensure_running()

    def cancel(self, entry):
        if entry["proc"] is not None:
            try:
                entry["proc"].terminate()
            except Exception:
                pass
        entry["done"] = True
        self._save()


_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = TimerScheduler()
    return _scheduler


# Zuletzt bekannte Verbindungszahl. auth() wird gecacht, weil der Server
# bei mehreren Abrufen kurz hintereinander mit einem Fehler antwortet —
# dann wuerde die Warnung faelschlich "unbekannt" melden, obwohl die Zahl
# beim ersten Abruf schon bekannt war.
_VERBINDUNGEN = {"wert": None, "gefragt": False}


def max_verbindungen(api, neu_laden=False):
    """Erlaubte Parallel-Verbindungen der Line (None, wenn unbekannt)."""
    if _VERBINDUNGEN["gefragt"] and not neu_laden:
        return _VERBINDUNGEN["wert"]
    if api is None:
        return _VERBINDUNGEN["wert"]
    _VERBINDUNGEN["gefragt"] = True
    try:
        info = api.auth() or {}
        wert = (info.get("user_info") or {}).get("max_connections")
        _VERBINDUNGEN["wert"] = int(wert) if wert else None
    except Exception:
        # Fehler: alten Wert behalten, nicht auf None zuruecksetzen.
        pass
    return _VERBINDUNGEN["wert"]


def verbindungs_hinweis(api):
    """Warntext zur Verbindungszahl der Line.

    Eine Aufnahme belegt eine Verbindung. Bei nur einer erlaubten kann
    waehrend der Aufnahme nicht umgeschaltet werden — das muss vor dem
    Start klar sein, sonst wirkt die Box spaeter kaputt.
    """
    max_v = max_verbindungen(api)
    if max_v is None:
        return ("Eine Aufnahme belegt eine Verbindung deiner Line. "
                "Lässt die Line nur eine zu, kann während der Aufnahme "
                "kein anderer Sender geschaut werden.")
    if max_v <= 1:
        return ("Deine Line erlaubt EINE Verbindung. Während der Aufnahme "
                "läuft belegt sie diese — du kannst in dieser Zeit keinen "
                "anderen Sender schauen.")
    return ("Deine Line erlaubt %d Verbindungen. Während der Aufnahme bleiben "
            "%d zum Schauen übrig — du kannst also weiter umschalten."
            % (max_v, max_v - 1))


def ask_recording(session, url, name, api=None, stream_id=None):
    """Zeigt die Aufnahme-Abfrage (endlos vs. bis Sendungsende) und startet."""
    from Screens.ChoiceBox import ChoiceBox
    from Screens.MessageBox import MessageBox
    import datetime

    rec = get_recorder()

    # EPG-Ende + Sendungstitel ermitteln (falls verfügbar).
    end_ts = None
    end_label = ""
    epg_title = None
    if api and stream_id:
        try:
            data = api.short_epg(stream_id, limit=1)
            listings = data.get("epg_listings", []) or []
            if listings:
                now = listings[0]
                t = now.get("title", "")
                try:
                    epg_title = base64.b64decode(t).decode("utf-8", "replace")
                    if not epg_title.strip():
                        epg_title = None
                except Exception:
                    epg_title = t or None
                end_ts = int(now.get("stop_timestamp", "0"))
                if end_ts:
                    end_label = datetime.datetime.fromtimestamp(
                        end_ts).strftime("%H:%M")
        except Exception:
            end_ts = None

    # Dateiname: EPG-Titel bevorzugen, Sendername nur als Fallback.
    rec_title = (epg_title or name).strip()

    choices = [(_("Endlos (bis manuell gestoppt)"), "endless")]
    if end_ts:
        choices.append((_("Bis Ende der Sendung (%s)") % end_label, "epg"))

    def _done(result):
        if result is None:
            return
        mode = result[1] if isinstance(result, (tuple, list)) else "endless"
        try:
            if mode == "epg" and end_ts:
                path = rec.start(url, rec_title, end_ts=end_ts)
            else:
                path = rec.start(url, rec_title)
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


def confirm_if_recording(session, proceed):
    """Wenn eine Aufnahme läuft, vor dem Umschalten bestätigen lassen.

    Beim Umschalten auf einen anderen Sender wird die Aufnahme beendet
    (die IPTV-Line erlaubt meist nur eine gleichzeitige Verbindung).
    proceed() wird nur ausgeführt, wenn keine Aufnahme läuft ODER der
    Nutzer das Umschalten bestätigt.
    """
    rec = get_recorder()
    if not rec.recording:
        proceed()
        return

    def _done(answer):
        if answer:
            rec.stop()
            proceed()

    from Screens.MessageBox import MessageBox
    session.openWithCallback(
        _done, MessageBox,
        _("Aufnahme läuft!\nBeim Umschalten wird sie beendet.\n"
          "Wirklich umschalten?"),
        MessageBox.TYPE_YESNO)
