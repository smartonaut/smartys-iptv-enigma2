# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste (Kategorie-Filter, Aufnahme, Vorschau, EPG, Picon)."""

import base64

from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from .screens_base import BaseListScreen
from . import player as vlc_player
from . import recorder
from . import picon


def _b64(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _fmt_time(s):
    if not s:
        return ""
    s = s.strip()
    if len(s) >= 16:
        try:
            return s[11:16]
        except Exception:
            pass
    return s


class LiveListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Live-TV"
    subtitle_text = "Sender wählen"
    preview = True
    epg = True
    picon = True
    footer = "OK = Abspielen   ·   ROT = Aufnahme   ·   EPG = Sendeplan   ·   EXIT = Zurück"

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        super().__init__(session, cfg, category_id, header_text, subtitle_text)

        self["epg"] = Label()
        self["picon"] = Pixmap()

        # Debounce-Timer: Vorschau erst nach kurzem Verharren auf einem Sender.
        self._preview_timer = eTimer()
        try:
            self._preview_timer.callback.append(self._preview_tick)
        except Exception:
            self._preview_timer.timeout.connect(self._preview_tick)

        # EPG-Timer (etwas schneller als die Vorschau).
        self._epg_timer = eTimer()
        try:
            self._epg_timer.callback.append(self._update_epg)
        except Exception:
            self._epg_timer.timeout.connect(self._update_epg)

        # Picon-Timer: Logo des markierten Senders aktualisieren.
        self._picon_timer = eTimer()
        try:
            self._picon_timer.callback.append(self._update_picon)
        except Exception:
            self._picon_timer.timeout.connect(self._update_picon)

        self["list"].onSelectionChanged.append(self._on_selection_changed)

    def _fetch(self):
        streams = self.api.live_streams(self.category_id)
        return (
            [(s.get("name", "?"), s) for s in streams],
            _("%d Sender") % len(streams),
        )

    def _on_select(self, ch):
        stream_id = ch.get("stream_id")
        name = ch.get("name", "")
        url = self.api.creds.stream_url(stream_id, "ts")
        self._open_player(url, name, stream_id)

    def _open_player(self, url, name="", stream_id=None):
        """Vollbild: StreamPlayer-Screen öffnen (rendert das Video + EPG)."""
        vlc_player.open_player(self.session, url, name=name,
                               stream_id=stream_id, api=self.api)

    def _on_selection_changed(self):
        # Vorschau + EPG + Picon verzögert starten.
        self._preview_timer.start(600, True)
        self._epg_timer.start(300, True)
        self._picon_timer.start(150, True)

    def _current_stream(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return None
        return sel[1]

    def _preview_tick(self):
        """Spielt den markierten Sender im Pig-Fenster ab (Live-Vorschau)."""
        ch = self._current_stream()
        if not ch:
            return
        url = self.api.creds.stream_url(ch.get("stream_id"), "ts")
        vlc_player.play_service(self.session, url)

    def _update_picon(self):
        """Lädt/zeigt das Senderlogo des markierten Senders."""
        ch = self._current_stream()
        if not ch:
            return
        sid = str(ch.get("stream_id", ""))
        icon_url = ch.get("stream_icon", "")
        picon.request(icon_url, sid)
        path = picon.logo_path(sid)
        if picon.has_logo(sid):
            try:
                pix = LoadPixmap(path)
                if pix:
                    self["picon"].instance.setPixmap(pix)
            except Exception:
                pass

    def _update_epg(self):
        """Lädt short_epg und zeigt 'Jetzt / Danach' unter der Liste."""
        ch = self._current_stream()
        if not ch:
            self["epg"].setText("")
            return
        stream_id = ch.get("stream_id")
        try:
            data = self.api.short_epg(stream_id, limit=2)
            listings = data.get("epg_listings", []) or []
            if not listings:
                self["epg"].setText(_("Keine EPG-Daten"))
                return
            now = listings[0]
            txt = "Jetzt: %s  (%s–%s)" % (
                _b64(now.get("title", "")),
                _fmt_time(now.get("start", "")),
                _fmt_time(now.get("end", "")),
            )
            if len(listings) > 1:
                nxt = listings[1]
                txt += "    ·    Danach: %s  (%s)" % (
                    _b64(nxt.get("title", "")),
                    _fmt_time(nxt.get("start", "")),
                )
            self["epg"].setText(txt)
        except Exception:
            self["epg"].setText(_("Keine EPG-Daten"))

    def on_red(self):
        """ROT = Aufnahme starten/stoppen für den markierten Sender."""
        ch = self._current_stream()
        if not ch:
            return
        name = ch.get("name", "Sender")
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")

        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            recorder.ask_recording(self.session, url, name,
                                   api=self.api, stream_id=stream_id)

    def on_info(self):
        """EPG/INFO = EPG-Ansicht des markierten Senders öffnen."""
        ch = self._current_stream()
        if not ch:
            return
        from .epg import EpgScreen
        self.session.open(
            EpgScreen, self.api, ch.get("stream_id"), ch.get("name", ""))
