# -*- coding: utf-8 -*-
"""Smartys IPTV — VOD (Filme) Liste (mit Kategorie-Filter)."""

from .screens_base import BaseListScreen
from . import player as vlc_player


class VodListScreen(BaseListScreen):
    screen_name = "SmartysVodList"
    header_text = "Filme"
    subtitle_text = "Video-on-Demand"
    footer = "OK = Abspielen   ·   EXIT = Zurück"

    def _fetch(self):
        movies = self.api.vod_streams(self.category_id)
        return (
            [(m.get("name", "?"), m) for m in movies],
            _("%d Filme") % len(movies),
        )

    def _on_select(self, item):
        stream_id = item.get("stream_id")
        name = item.get("name", "")
        from .voddetail import VodDetailScreen
        self.session.open(VodDetailScreen, self.api, stream_id, name)
