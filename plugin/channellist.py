# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste (Kategorie-Filter, Aufnahme, Vorschau)."""

from Screens.MessageBox import MessageBox
from enigma import eTimer

from .screens_base import BaseListScreen
from . import player as vlc_player
from . import recorder


class LiveListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Live-TV"
    subtitle_text = "Sender wählen"
    preview = True

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        super().__init__(session, cfg, category_id, header_text, subtitle_text)
        # Debounce-Timer: Vorschau erst nach kurzem Verharren auf einem Sender.
        self._preview_timer = eTimer()
        try:
            self._preview_timer.callback.append(self._preview_tick)
        except Exception:
            self._preview_timer.timeout.connect(self._preview_tick)
        self["list"].onSelectionChanged.append(self._on_selection_changed)

    def _fetch(self):
        streams = self.api.live_streams(self.category_id)
        return (
            [(s.get("name", "?"), s) for s in streams],
            _("%d Sender") % len(streams),
        )

    def _on_select(self, ch):
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")
        self._open_player(url)

    def _open_player(self, url):
        """Vollbild: StreamPlayer-Screen öffnen (rendert das Video)."""
        vlc_player.open_player(self.session, url)

    def _on_selection_changed(self):
        # Vorschau verzögert starten, damit schnelles Scrollen nicht ruckelt.
        self._preview_timer.start(600, True)

    def _preview_tick(self):
        """Spielt den markierten Sender im Pig-Fenster ab (Live-Vorschau)."""
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        ch = sel[1]
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")
        vlc_player.play_service(self.session, url)

    def on_red(self):
        """ROT = Aufnahme starten/stoppen für den markierten Sender."""
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        ch = sel[1]
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
