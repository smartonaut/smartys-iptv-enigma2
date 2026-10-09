# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste (mit Kategorie-Filter + Aufnahme)."""

from Screens.MessageBox import MessageBox
from .screens_base import BaseListScreen
from . import player as vlc_player
from . import recorder


class LiveListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Live-TV"
    subtitle_text = "Sender wählen"

    def _fetch(self):
        streams = self.api.live_streams(self.category_id)
        return (
            [(s.get("name", "?"), s) for s in streams],
            _("%d Sender") % len(streams),
        )

    def _on_select(self, ch):
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")
        vlc_player.play(self.session, url)

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
