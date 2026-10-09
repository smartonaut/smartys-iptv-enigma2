# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste (Kategorie-Filter, Aufnahme, Vorschau, EPG, Picons)."""

import base64

from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.Sources.List import List
from Components.MultiContent import MultiContentEntryText, MultiContentEntryPixmapAlphaBlend
from enigma import eTimer, gFont, RT_HALIGN_LEFT, RT_VALIGN_CENTER, loadPixmap

from .screens_base import BaseListScreen
from . import player as vlc_player
from . import recorder
from . import picon
from . import theme


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
    footer = "OK = Abspielen   ·   ROT = Aufnahme   ·   EPG = Sendeplan   ·   EXIT = Zurück"

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        super().__init__(session, cfg, category_id, header_text, subtitle_text)

        # MultiContent-Liste (Picons) statt reiner Textliste.
        self["list"] = List([])

        self["epg"] = Label()

        self._font = gFont("Regular", theme.font(22))

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

        # Picon-Refresh: baut die Liste neu, sobald Logos geladen sind.
        self._picon_timer = eTimer()
        try:
            self._picon_timer.callback.append(self._picon_refresh)
        except Exception:
            self._picon_timer.timeout.connect(self._picon_refresh)
        self._picon_count = 0
        self._picon_cycles = 0

        self["list"].onSelectionChanged.append(self._on_selection_changed)

    # --- Laden ---

    def _load(self):
        if not self.api:
            self["list"].setList([(_("Nicht verbunden"), None)])
            return
        try:
            streams = self.api.live_streams(self.category_id)
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self._streams = streams
        self._build_list()
        self["status"].setText(_("%d Sender") % len(streams))

        # Logos für die ersten Sender im Hintergrund laden.
        for s in streams[:120]:
            picon.request(s.get("stream_icon"), str(s.get("stream_id", "")))
        self._picon_cycles = 0
        self._picon_count = self._cached_logo_count()
        self._picon_timer.start(1500, False)

    def _build_list(self):
        self["list"].setList([self._build_entry(s) for s in self._streams])

    def _build_entry(self, s):
        name = s.get("name", "?")
        sid = str(s.get("stream_id", ""))
        res = [s]  # data (dict) als erstes Element
        logo = picon.logo_path(sid)
        if logo:
            try:
                pix = loadPixmap(logo)
                if pix:
                    res.append(MultiContentEntryPixmapAlphaBlend(
                        pos=(6, 5), size=(32, 32), png=pix))
            except Exception:
                pass
        res.append(MultiContentEntryText(
            pos=(48, 2), size=(700, 34), font=self._font,
            flags=RT_HALIGN_LEFT | RT_VALIGN_CENTER, text=name))
        return res

    @staticmethod
    def _cached_logo_count():
        try:
            import os
            return len([f for f in os.listdir(picon.CACHE_DIR)
                        if f.endswith(".png")])
        except Exception:
            return 0

    def _picon_refresh(self):
        """Baut die Liste neu, wenn neue Logos geladen wurden."""
        self._picon_cycles += 1
        cnt = self._cached_logo_count()
        if cnt != self._picon_count:
            self._picon_count = cnt
            self._build_list()
        if self._picon_cycles >= 20:
            self._picon_timer.stop()

    def _fetch(self):
        # Wird nicht mehr genutzt (überschrieben durch _load).
        return [], ""

    # --- Auswahl ---

    def _current_stream(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[0]:
            return None
        return sel[0]

    def on_select(self):
        ch = self._current_stream()
        if not ch:
            return
        self._on_select(ch)

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
        # Vorschau + EPG verzögert starten, damit schnelles Scrollen nicht ruckelt.
        self._preview_timer.start(600, True)
        self._epg_timer.start(300, True)

    def _preview_tick(self):
        """Spielt den markierten Sender im Pig-Fenster ab (Live-Vorschau)."""
        ch = self._current_stream()
        if not ch:
            return
        url = self.api.creds.stream_url(ch.get("stream_id"), "ts")
        vlc_player.play_service(self.session, url)

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

    # --- Aktionen ---

    def on_red(self):
        """ROT = Aufnahme starten/stoppen für den markierten Sender."""
        ch = self._current_stream()
        if not ch:
            return
        name = ch.get("name", "Sender")
        url = self.api.creds.stream_url(ch.get("stream_id"), "ts")

        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            try:
                path = rec.start(url, name)
            except Exception as e:
                self.session.open(
                    MessageBox, _("Aufnahme fehlgeschlagen: %s") % str(e),
                    MessageBox.TYPE_ERROR, timeout=5)
                return
            self.session.open(
                MessageBox, _("Aufnahme gestartet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)

    def on_info(self):
        """EPG/INFO = EPG-Ansicht des markierten Senders öffnen."""
        ch = self._current_stream()
        if not ch:
            return
        from .epg import EpgScreen
        self.session.open(
            EpgScreen, self.api, ch.get("stream_id"), ch.get("name", ""))
