# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste."""

from .screens_base import BaseListScreen
from . import player as vlc_player


class LiveListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Live-TV"
    subtitle_text = "Sender wählen"

    def _fetch(self):
        streams = self.api.live_streams()
        return (
            [(s.get("name", "?"), s) for s in streams],
            _("%d Sender") % len(streams),
        )

    def _on_select(self, ch):
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")
        vlc_player.play(self.session, url)
