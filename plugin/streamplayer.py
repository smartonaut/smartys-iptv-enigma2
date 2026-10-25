# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Player-Screen (nach XStreamity-Vorbild).

Das Video wird über den Hardware-Decoder gerendert (session.nav.playService).
Der Screen legt ein transparentes OSD darüber. Bei OK wird eine Infobar mit
EPG (Titel, Laufzeit-Balken, Uhrzeit) ein-/ausgeblendet — exakt wie
XStreamity_StreamPlayer.
"""

import base64
import time
import os
import subprocess
import datetime

from enigma import iServiceInformation
from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ServiceEventTracker import InfoBarBase
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eServiceReference, eTimer

from . import theme
from . import recorder


def _cfg(key, default):
    """Liest eine Einstellung (mit Fallback)."""
    try:
        from .config import Config
        return Config().load().get(key, default)
    except Exception:
        return default


class StreamPlayerScreen(InfoBarBase, Screen):
    """Vollbild-Player für einen IPTV-Stream, mit EPG-Infobar."""

    def __init__(self, session, url, servicetype=4097, name="",
                 stream_id=None, api=None, stream_icon=None,
                 next_url=None, next_name=""):
        Screen.__init__(self, session)
        self.session = session
        self.streamurl = url
        self.servicetype = servicetype
        self.stream_name = name or ""
        self.stream_id = stream_id
        self.api = api
        self.stream_icon = stream_icon or ""
        try:
            self.onClose.append(self._on_close_flags)
        except Exception:
            pass
        # Naechste Folge (Serien): laeuft der Dienst aus, startet der Player
        # sie selbst — Paritaet zum Auto-Next der anderen Plattformen.
        self._next_url = next_url
        self._next_name = next_name or ""
        self._closed = False
        self._end_timer = None

        # EPG-Daten (start_timestamp / stop_timestamp / titel)
        self._epg_now = None
        self._epg_next = None

        # Timeshift (Pause = automatische Aufnahme in den Buffer).
        self._timeshift_proc = None
        self._timeshift_path = None
        self._ts_end_timer = None

        w, h = theme.osd_size()
        # Transparenter Vollbild-Skin + Infobar unten (Android-Stil: linksbündiges
        # Panel mit Abstand, 40% alpha Dunkelblau #660b0e14, abgerundete Optik).
        self.skin = (
            '<screen name="SmartysStreamPlayer" position="0,0" '
            'size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">'
            '<widget name="actions" position="0,0" size="1,1" '
            'transparent="1" zPosition="0"/>'
            # --- Infobar (unten links) ---
            '<widget name="infobar_bg" position="%d,%d" '
            'size="%d,%d" backgroundColor="#660b0e14" zPosition="3"/>'
            # Picon (Programm-Logo)
            '<widget name="logo" position="%d,%d" size="%d,%d" '
            'alphatest="blend" zPosition="4"/>'
            '<widget name="nowchannel" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#e8eefc" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="nowtime" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#e8eefc" transparent="1" '
            'halign="right" valign="center" zPosition="4"/>'
            '<widget name="recbadge" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ff6b6b" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="videoinfo" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ffc94d" transparent="1" '
            'halign="right" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="nowtitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ffc94d" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="nexttitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#8fa3c8" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="progress" position="%d,%d" size="%d,%d" '
            'foregroundColor="#ffc94d" backgroundColor="#232c42" '
            'zPosition="4"/>'
            '<widget name="help" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#888888" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '</screen>' % (
                w, h,
                # Infobar-Hintergrund: unten links, Android-Stil
                theme.scale(20), theme.scale_y(580), theme.scale(800),
                theme.scale_y(140),
                # logo (Picon)
                theme.scale(36), theme.scale_y(594), theme.scale(56),
                theme.scale_y(56),
                # nowchannel (Sendername)
                theme.scale(104), theme.scale_y(592), theme.scale(400),
                theme.scale_y(28), theme.font(23),
                # nowtime (Uhrzeit, rechts)
                theme.scale(660), theme.scale_y(592), theme.scale(144),
                theme.scale_y(28), theme.font(21),
                # recbadge (Aufnahme-Laufanzeige)
                theme.scale(104), theme.scale_y(622), theme.scale(220),
                theme.scale_y(20), theme.font(14),
                # videoinfo (Auflösung, rechts)
                theme.scale(660), theme.scale_y(622), theme.scale(144),
                theme.scale_y(20), theme.font(14),
                # nowtitle (EPG jetzt, mit Zeiten)
                theme.scale(104), theme.scale_y(646), theme.scale(700),
                theme.scale_y(28), theme.font(18),
                # nexttitle (EPG danach)
                theme.scale(104), theme.scale_y(674), theme.scale(700),
                theme.scale_y(20), theme.font(15),
                # progress (dünner goldener Balken)
                theme.scale(36), theme.scale_y(694), theme.scale(760),
                theme.scale_y(4),
                # help (Tastenerklärung, ganz unten)
                theme.scale(20), theme.scale_y(704), theme.scale(800),
                theme.scale_y(14), theme.font(13),
            )
        )

        InfoBarBase.__init__(self)

        self["nowchannel"] = Label()
        self["nowtitle"] = Label()
        self["nowtime"] = Label()
        self["videoinfo"] = Label()
        self["recbadge"] = Label()
        self["nexttitle"] = Label()
        self["progress"] = ProgressBar()
        self["logo"] = Pixmap()
        self["infobar_bg"] = Label()
        self["help"] = Label(
            "OK = Info    ROT = Aufnahme    PAUSE = Timeshift    "
            "EXIT = Zurück")

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "ColorActions",
             "InfobarActions"],
            {
                "ok": self.toggle_infobar,
                "cancel": self._confirm_switch,
                "stop": self._confirm_switch,
                "up": self._confirm_switch,
                "down": self._confirm_switch,
                "red": self.toggle_recording,
                "pause": self.toggle_timeshift,
                "playpause": self.toggle_timeshift,
            },
        )

        # Laufzeit-Balken + Uhrzeit regelmässig aktualisieren.
        self._progress_timer = eTimer()
        try:
            self._progress_timer.callback.append(self._refresh_clock)
        except Exception:
            self._progress_timer.timeout.connect(self._refresh_clock)

        # Infobar anfangs sichtbar, Auto-Hide nach 6s.
        self._hide_timer = eTimer()
        try:
            self._hide_timer.callback.append(self._auto_hide)
        except Exception:
            self._hide_timer.timeout.connect(self._auto_hide)

        self._infobar_visible = True

        self.onFirstExecBegin.append(self.play_stream)

    # --- Playback + EPG ---

    def _on_close_flags(self):
        self._closed = True
        try:
            if self._end_timer is not None:
                self._end_timer.stop()
        except Exception:
            pass

    def play_stream(self, watchdog=True):
        try:
            ref = eServiceReference(int(self.servicetype), 0, self.streamurl)
            ref.setName(self.streamurl)
            self.session.nav.playService(ref)
        except Exception:
            pass
        self._load_epg()
        self._show_infobar()
        if watchdog:
            self._watchdog_start()
            self._end_watch_start()

    # ------------------------------------------------------------------
    # Verbindungswaechter
    #
    # Paritaet zum Desktop-Player (dort 3 s Stillstand -> reconnect).
    # Auf Enigma2 gibt es fuer Live-Stroeme keine verlaessliche Position,
    # deshalb wird geprueft, ob der Dienst ueberhaupt noch laeuft und ob
    # der Decoder eine Bildgroesse meldet. Reagiert nur nach einer
    # Anlaufphase (Pufferaufbau ist kein Stillstand) und nicht waehrend
    # Timeshift oder Aufnahme.
    # ------------------------------------------------------------------

    def _end_watch_start(self):
        """Merkt, wenn der Dienst von selbst endet (VOD zu Ende) und startet
        dann die naechste Folge."""
        if not self._next_url:
            return
        if self._end_timer is None:
            self._end_timer = eTimer()
            try:
                self._end_timer.callback.append(self._end_tick)
            except Exception:
                self._end_timer.timeout.connect(self._end_tick)
        try:
            self._end_timer.start(5000, False)
        except Exception:
            pass

    def _end_tick(self):
        try:
            if self._closed or not self._next_url:
                return
            if self.session.nav.getCurrentService() is not None:
                return
            # Dienst weg -> naechste Folge uebernehmen
            self._next_url, url = None, self._next_url
            name, self._next_name = self._next_name, ""
            self.streamurl = url
            self.stream_name = name
            self._end_timer.stop()
            self.play_stream()
        except Exception:
            pass

    def _watchdog_start(self):
        self._wd_start = time.time()
        if not hasattr(self, "_wd_tries"):
            self._wd_tries = 0
        if not hasattr(self, "_wd_timer"):
            self._wd_timer = eTimer()
            try:
                self._wd_timer.callback.append(self._watchdog_tick)
            except Exception:
                self._wd_timer.timeout.connect(self._watchdog_tick)
        try:
            self._wd_timer.start(2000, False)
        except Exception:
            pass

    def _watchdog_tick(self):
        try:
            if self._wd_tries >= 3:
                self._wd_timer.stop()
                return
            # Anlaufphase: der Puffer muss sich erst fuellen.
            if time.time() - getattr(self, "_wd_start", 0) < 15:
                return
            # Timeshift/Aufnahme laufen ueber eigene Prozesse — nicht dazwischenfunken.
            if getattr(self, "_timeshift_proc", None) is not None:
                return
            svc = self.session.nav.getCurrentService()
            if svc is None:
                self._wd_tries += 1
                self.play_stream(watchdog=False)
                return
            # Decoder meldet keine Bildgroesse -> kein Bild trotz Dienst.
            # Die Konstanten heissen je nach Enigma2-Version anders; fehlen
            # sie, bleibt nur die Dienst-Pruefung oben (kein Fehler).
            try:
                w_key = getattr(iServiceInformation, "iVideoWidth", None)
                h_key = getattr(iServiceInformation, "iVideoHeight", None)
                if w_key is not None and h_key is not None:
                    info = svc.info()
                    if info is not None:
                        if (info.getInfo(w_key) == 0
                                and info.getInfo(h_key) == 0):
                            self._wd_tries += 1
                            self.play_stream(watchdog=False)
            except Exception:
                pass
        except Exception:
            pass

    def _load_epg(self):
        """Lädt short_epg und setzt Titel + Laufzeit-Daten.

        Backup-Kette: Provider short_epg -> freies EPG (Rytec).
        """
        print("[SmartysIPTV] _load_epg api=%s stream_id=%s" % (
            self.api is not None, self.stream_id))
        self._backup_tried = False
        if not self.api or not self.stream_id:
            return
        try:
            data = self.api.short_epg(self.stream_id, limit=2)
            listings = data.get("epg_listings", []) or []
            if listings:
                self._epg_now = listings[0]
            if len(listings) > 1:
                self._epg_next = listings[1]
            print("[SmartysIPTV] EPG listings=%d" % len(listings))
        except Exception as e:
            print("[SmartysIPTV] EPG-Fehler: %r" % e)
            self._epg_now = None
            self._epg_next = None
        if self._epg_now is None:
            self._try_backup_epg()
        self._apply_epg()

    def _try_backup_epg(self):
        """Freies EPG (Rytec) als Fallback, wenn der Provider nichts liefert."""
        try:
            from . import epgbackup
            epgbackup.ensure_loaded()
            if not epgbackup.ready():
                return
            self._backup_tried = True
            now_ev, next_ev = epgbackup.lookup(self.stream_name or "")
            if now_ev:
                self._epg_now = {
                    "title": now_ev[2],
                    "start_timestamp": str(now_ev[0]),
                    "stop_timestamp": str(now_ev[1]),
                }
                print("[SmartysIPTV] EPG-Backup now: %s" % now_ev[2])
            if next_ev:
                self._epg_next = {
                    "title": next_ev[2],
                    "start_timestamp": str(next_ev[0]),
                    "stop_timestamp": str(next_ev[1]),
                }
        except Exception as e:
            print("[SmartysIPTV] EPG-Backup-Fehler: %r" % e)

    def _apply_epg(self):
        """Setzt Sendername, Titel (mit Sendezeit), Danach-Zeile und Balken."""
        self["nowchannel"].setText(self.stream_name or "")
        title = ""
        if self._epg_now:
            title = self._b64(self._epg_now.get("title", ""))
            start = self._epg_now.get("start_timestamp", "")
            end = self._epg_now.get("stop_timestamp", "")
            if start and end:
                title = "%s   (%s - %s)" % (
                    title, self._fmt_ts(start), self._fmt_ts(end))
        self["nowtitle"].setText(title)
        # "Danach: HH:MM Titel" (Android-Stil)
        if self._epg_next:
            nxt_title = self._b64(self._epg_next.get("title", ""))
            nxt_start = self._epg_next.get("start_timestamp", "")
            if nxt_start:
                self["nexttitle"].setText(
                    "Danach:  %s  %s" % (self._fmt_ts(nxt_start), nxt_title))
            else:
                self["nexttitle"].setText("Danach:  %s" % nxt_title)
        else:
            self["nexttitle"].setText("")
        self._load_logo()
        self._load_videoinfo()
        self._refresh_clock()

    def _load_logo(self):
        """Lädt das Senderlogo (Picon) und setzt das Pixmap (asynchron)."""
        try:
            from . import picon
            if self.stream_icon and self.stream_id:
                sid = str(self.stream_id)
                if picon.has_logo(sid):
                    self["logo"].instance.setPixmap(LoadPixmap(picon.logo_path(sid)))
                    if self._infobar_visible:
                        self["logo"].show()
                    else:
                        self["logo"].hide()
                    return
                picon.request(self.stream_icon, sid)
            self["logo"].hide()
        except Exception:
            self["logo"].hide()

    def _load_videoinfo(self):
        """Liest die Video-Auflösung aus dem laufenden Stream."""
        try:
            from enigma import iServiceInformation
            service = self.session.nav.getCurrentService()
            if service:
                info = service.info()
                w = info.getInfo(iServiceInformation.sVideoWidth)
                h = info.getInfo(iServiceInformation.sVideoHeight)
                if w and h:
                    self["videoinfo"].setText("%dx%d" % (w, h))
                    if self._infobar_visible:
                        self["videoinfo"].show()
                    else:
                        self["videoinfo"].hide()
                    return
            self["videoinfo"].hide()
        except Exception:
            self["videoinfo"].hide()

    def _refresh_clock(self):
        """Aktualisiert Uhrzeit + Laufzeit-Balken."""
        try:
            now = time.localtime()
            self["nowtime"].setText("%02d:%02d" % (now.tm_hour, now.tm_min))
        except Exception:
            pass

        if self._epg_now:
            try:
                start = int(self._epg_now.get("start_timestamp", "0"))
                end = int(self._epg_now.get("stop_timestamp", "0"))
                now_ts = int(time.time())
                if end > start > 0:
                    total = end - start
                    elapsed = now_ts - start
                    pct = max(0, min(100, int(elapsed * 100 / total)))
                    self["progress"].setValue(pct)
                    if self._infobar_visible:
                        self["progress"].show()
                    else:
                        self["progress"].hide()
                else:
                    self["progress"].hide()
            except Exception:
                self["progress"].hide()
        else:
            self["progress"].hide()

        # EPG-Backup nachziehen, sobald der Lade-Thread fertig ist.
        if (self._epg_now is None and not getattr(self, "_backup_tried", True)
                and self.stream_id):
            try:
                from . import epgbackup
                if epgbackup.ready():
                    self._backup_tried = True
                    self._try_backup_epg()
                    if self._epg_now is not None:
                        self._apply_epg()
            except Exception:
                pass

        # Logo + Auflösung nachziehen (asynchron geladen, erst nach Streamstart).
        self._load_logo()
        self._load_videoinfo()

    @staticmethod
    def _b64(s):
        try:
            return base64.b64decode(s, validate=True).decode("utf-8", "replace")
        except Exception:
            return s

    @staticmethod
    def _fmt_ts(ts):
        """Formatiert einen Unix-Timestamp als HH:MM."""
        try:
            t = time.localtime(int(ts))
            return "%02d:%02d" % (t.tm_hour, t.tm_min)
        except Exception:
            return ""

    # --- Infobar Show/Hide ---

    def toggle_infobar(self):
        if self._infobar_visible:
            self._hide_infobar()
        else:
            self._show_infobar()

    def _show_infobar(self):
        self._infobar_visible = True
        for w in ("nowchannel", "nowtitle", "nowtime", "videoinfo",
                  "recbadge", "nexttitle", "progress", "help", "infobar_bg"):
            try:
                self[w].show()
            except Exception:
                pass
        self._refresh_recbadge()
        self._refresh_clock()
        self._progress_timer.start(30000, False)
        self._hide_timer.start(6000, True)

    def _hide_infobar(self):
        self._infobar_visible = False
        for w in ("nowchannel", "nowtitle", "nowtime", "videoinfo",
                  "recbadge", "nexttitle", "progress", "help", "infobar_bg",
                  "logo"):
            try:
                self[w].hide()
            except Exception:
                pass

    def _refresh_recbadge(self):
        """Zeigt das REC-Badge, solange eine Aufnahme läuft."""
        try:
            rec = recorder.get_recorder()
            if rec.recording:
                self["recbadge"].setText("● REC")
                if self._infobar_visible:
                    self["recbadge"].show()
            else:
                self["recbadge"].setText("")
                self["recbadge"].hide()
        except Exception:
            pass

    def _auto_hide(self):
        self._hide_infobar()

    # --- Aufnahme (ROT) ---

    def toggle_recording(self):
        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self["recbadge"].setText("")
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            self["recbadge"].setText("● REC")
            recorder.ask_recording(
                self.session, self.streamurl,
                self.stream_name or "Aufnahme",
                api=self.api, stream_id=self.stream_id)
        self._refresh_recbadge()

    # --- Timeshift (PAUSE = automatische Aufnahme) ---

    def toggle_timeshift(self):
        """PAUSE = Aufnahme in den Buffer starten; nochmal = Buffer abspielen."""
        if not _cfg("timeshift", True):
            return
        if self._timeshift_proc is None:
            self._start_timeshift()
        else:
            self._resume_timeshift()

    def _start_timeshift(self):
        ts_dir = "/media/hdd/timeshift"
        try:
            os.makedirs(ts_dir, exist_ok=True)
        except Exception:
            ts_dir = "/tmp"
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._timeshift_path = os.path.join(ts_dir, "timeshift_%s.ts" % ts)
        cmd = [
            "ffmpeg", "-y",
            "-user_agent", recorder.USER_AGENT,
            "-i", self.streamurl,
            "-c", "copy",
            "-f", "mpegts",
            self._timeshift_path,
        ]
        try:
            self._timeshift_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.session.open(
                MessageBox, _("Timeshift fehlgeschlagen: %s") % str(e),
                MessageBox.TYPE_ERROR, timeout=5)
            self._timeshift_proc = None
            return
        # Live-Bild anhalten; der Stream läuft weiter, die Aufnahme fängt ihn.
        try:
            self.session.nav.stopService()
        except Exception:
            pass
        self["nowtitle"].setText(_("Timeshift: Aufnahme läuft bis Sendungsende"))
        self["nowtime"].setText("")
        self["progress"].setValue(0)
        self._show_infobar()
        # ffmpeg am Sendungsende automatisch stoppen (falls EPG-Ende bekannt).
        self._schedule_timeshift_end()

    def _schedule_timeshift_end(self):
        """Stoppt die Timeshift-Aufnahme am EPG-Sendungsende (falls bekannt)."""
        end = None
        try:
            if self._epg_now:
                end = int(self._epg_now.get("stop_timestamp", "0"))
        except Exception:
            pass
        self._ts_end_timer = eTimer()
        try:
            self._ts_end_timer.callback.append(self._stop_timeshift_proc)
        except Exception:
            self._ts_end_timer.timeout.connect(self._stop_timeshift_proc)
        if end and end > time.time():
            delay_ms = int((end - time.time()) * 1000)
            try:
                self._ts_end_timer.start(delay_ms, True)
            except Exception:
                pass
        # Kein EPG-Ende: Aufnahme läuft, bis der Screen verlassen wird.

    def _stop_timeshift_proc(self):
        """Beendet den ffmpeg-Aufnahmeprozess (Sendungsende erreicht)."""
        if self._timeshift_proc is None:
            return
        try:
            self._timeshift_proc.terminate()
            try:
                self._timeshift_proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._timeshift_proc.kill()
                self._timeshift_proc.wait()
        except Exception:
            pass
        self._timeshift_proc = None

    def _resume_timeshift(self):
        # ffmpeg läuft im Hintergrund weiter (Aufnahme bis Sendungsende) — wir
        # spielen nur den wachsenden Buffer zeitversetzt ab, statt die Aufnahme
        # zu stoppen. So kann der Nutzer die Sendung weiter verfolgen, während
        # im Hintergrund bis zum Sendungsende aufgenommen wird.
        path = self._timeshift_path
        if path and os.path.exists(path):
            try:
                self.session.nav.playService(
                    eServiceReference(self.servicetype, 0, path))
                self["nowtitle"].setText(
                    _("Timeshift-Wiedergabe (Aufnahme läuft bis Sendungsende)"))
                self._show_infobar()
            except Exception as e:
                self.session.open(
                    MessageBox, _("Wiedergabe fehlgeschlagen: %s") % str(e),
                    MessageBox.TYPE_ERROR, timeout=5)

    # --- Beenden ---

    def _confirm_switch(self):
        """Kanalwechsel/Beenden: vorher bestätigen, wenn eine Aufnahme läuft."""
        rec = recorder.get_recorder()
        has_rec = rec.recording
        has_ts = self._timeshift_proc is not None
        # Umschalt-Schutz deaktiviert? Dann direkt beenden.
        if not _cfg("confirm_switch", True):
            if has_rec:
                rec.stop()
            self.quit()
            return
        if not has_rec and not has_ts:
            self.quit()
            return

        def _done(answer):
            if answer:
                if has_rec:
                    rec.stop()
                self.quit()
            else:
                # Zurück zum Sender: Overlay ausblenden, Video läuft weiter.
                self._hide_infobar()

        self.session.openWithCallback(
            _done, MessageBox,
            _("Aufnahme läuft!\nBeim Umschalten wird sie beendet.\n"
              "Wirklich umschalten?"),
            MessageBox.TYPE_YESNO)

    def quit(self):
        try:
            self._progress_timer.stop()
            self._hide_timer.stop()
            if self._ts_end_timer is not None:
                self._ts_end_timer.stop()
        except Exception:
            pass
        # Laufende Timeshift-Aufnahme beenden (Buffer bleibt erhalten).
        if self._timeshift_proc is not None:
            try:
                self._timeshift_proc.terminate()
                try:
                    self._timeshift_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._timeshift_proc.kill()
                    self._timeshift_proc.wait()
            except Exception:
                pass
            self._timeshift_proc = None
        try:
            self.session.nav.stopService()
        except Exception:
            pass
        self.close()
