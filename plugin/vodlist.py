# -*- coding: utf-8 -*-
"""Smartys IPTV — VOD (Filme) Liste."""

from .screens_base import BaseListScreen
from . import player as vlc_player


class VodListScreen(BaseListScreen):
    screen_name = "SmartysVodList"
    header_text = "Filme"
    subtitle_text = "Video-on-Demand"

    def _fetch(self):
        movies = self.api.vod_streams()
        return (
            [(m.get("name", "?"), m) for m in movies],
            _("%d Filme") % len(movies),
        )

    def _on_select(self, item):
        stream_id = item.get("stream_id")
        ext = item.get("container_extension") or "mp4"
        url = self.api.creds.movie_url(stream_id, ext)
        vlc_player.play(self.session, url)
