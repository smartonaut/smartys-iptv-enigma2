# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Player-Screen (nach XStreamity-Vorbild).

Das Video wird über den Hardware-Decoder gerendert (session.nav.playService).
Der Screen legt ein transparentes OSD darüber. Bei OK wird eine Infobar mit
EPG (Titel, Laufzeit-Balken, Uhrzeit) ein-/ausgeblendet — exakt wie
XStreamity_StreamPlayer.
"""

import base64
import time

from Screens.Screen import Screen
from Screens.MessageBox import MessageBox
from Components.ServiceEventTracker import InfoBarBase
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ProgressBar import ProgressBar
from enigma import eServiceReference, eTimer

from . import theme
from . import recorder


class StreamPlayerScreen(InfoBarBase, Screen):
    """Vollbild-Player für einen IPTV-Stream, mit EPG-Infobar."""

    def __init__(self, session, url, servicetype=4097, name="",
                 stream_id=None, api=None):
        Screen.__init__(self, session)
        self.session = session
        self.streamurl = url
        self.servicetype = servicetype
        self.stream_name = name or ""
        self.stream_id = stream_id
        self.api = api

        # EPG-Daten (start_timestamp / stop_timestamp / titel)
        self._epg_now = None
        self._epg_next = None

        w, h = theme.osd_size()
        # Transparenter Vollbild-Skin + Infobar unten.
        self.skin = (
            '<screen name="SmartysStreamPlayer" position="0,0" '
            'size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">'
            '<widget name="actions" position="0,0" size="1,1" '
            'transparent="1" zPosition="0"/>'
            # --- Infobar (unten) ---
            '<eLabel name="infobar_bg" position="0,%d" size="%d,%d" '
            'backgroundColor="#a0000000" zPosition="3"/>'
            '<widget name="nowchannel" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ffffff" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="nowtitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ffc94d" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="4"/>'
            '<widget name="nowtime" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="#ffffff" transparent="1" '
            'halign="right" valign="center" zPosition="4"/>'
            '<widget name="progress" position="%d,%d" size="%d,%d" '
            'foregroundColor="#ffc94d" backgroundColor="#20000000" '
            'zPosition="4"/>'
            '</screen>' % (
                w, h,
                # Infobar-Hintergrund: unten, volle Breite
                0, theme.scale_y(600), w, theme.scale_y(120),
                # nowchannel
                theme.scale(48), theme.scale_y(612), theme.scale(800),
                theme.scale_y(44), theme.font(26),
                # nowtitle
                theme.scale(48), theme.scale_y(656), theme.scale(800),
                theme.scale_y(40), theme.font(20),
                # nowtime (rechts)
                theme.scale(900), theme.scale_y(612), theme.scale(330),
                theme.scale_y(44), theme.font(26),
                # progress (dünner Balken)
                theme.scale(48), theme.scale_y(668), theme.scale(800),
                theme.scale_y(6),
            )
        )

        InfoBarBase.__init__(self)

        self["nowchannel"] = Label()
        self["nowtitle"] = Label()
        self["nowtime"] = Label()
        self["progress"] = ProgressBar()

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions", "ColorActions"],
            {
                "ok": self.toggle_infobar,
                "cancel": self.quit,
                "stop": self.quit,
                "up": self.quit,
                "down": self.quit,
                "red": self.toggle_recording,
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

    def play_stream(self):
        try:
            ref = eServiceReference(int(self.servicetype), 0, self.streamurl)
            ref.setName(self.streamurl)
            self.session.nav.playService(ref)
        except Exception:
            pass
        self._load_epg()
        self._show_infobar()

    def _load_epg(self):
        """Lädt short_epg und setzt Titel + Laufzeit-Daten."""
        if not self.api or not self.stream_id:
            return
        try:
            data = self.api.short_epg(self.stream_id, limit=2)
            listings = data.get("epg_listings", []) or []
            if listings:
                self._epg_now = listings[0]
            if len(listings) > 1:
                self._epg_next = listings[1]
        except Exception:
            self._epg_now = None
            self._epg_next = None
        self._apply_epg()

    def _apply_epg(self):
        """Setzt Sendername, Titel und berechnet den Laufzeit-Balken."""
        self["nowchannel"].setText(self.stream_name or "")
        title = ""
        if self._epg_now:
            title = self._b64(self._epg_now.get("title", ""))
        self["nowtitle"].setText(title)
        self._refresh_clock()

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
                    self["progress"].show()
                else:
                    self["progress"].hide()
            except Exception:
                self["progress"].hide()
        else:
            self["progress"].hide()

    @staticmethod
    def _b64(s):
        try:
            return base64.b64decode(s).decode("utf-8", "replace")
        except Exception:
            return s

    # --- Infobar Show/Hide ---

    def toggle_infobar(self):
        if self._infobar_visible:
            self._hide_infobar()
        else:
            self._show_infobar()

    def _show_infobar(self):
        self._infobar_visible = True
        for w in ("nowchannel", "nowtitle", "nowtime", "progress", "infobar_bg"):
            try:
                self[w].show()
            except Exception:
                pass
        self._refresh_clock()
        self._progress_timer.start(30000, False)
        self._hide_timer.start(6000, True)

    def _hide_infobar(self):
        self._infobar_visible = False
        for w in ("nowchannel", "nowtitle", "nowtime", "progress", "infobar_bg"):
            try:
                self[w].hide()
            except Exception:
                pass

    def _auto_hide(self):
        self._hide_infobar()

    # --- Aufnahme (ROT) ---

    def toggle_recording(self):
        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            try:
                path = rec.start(self.streamurl,
                                 self.stream_name or "Aufnahme")
            except Exception as e:
                self.session.open(
                    MessageBox, _("Aufnahme fehlgeschlagen: %s") % str(e),
                    MessageBox.TYPE_ERROR, timeout=5)
                return
            self.session.open(
                MessageBox, _("Aufnahme gestartet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)

    # --- Beenden ---

    def quit(self):
        try:
            self._progress_timer.stop()
            self._hide_timer.stop()
        except Exception:
            pass
        try:
            self.session.nav.stopService()
        except Exception:
            pass
        self.close()
