# -*- coding: utf-8 -*-
"""Smartys IPTV — Serienliste (Serien → Episoden, mit Kategorie-Filter)."""

from .screens_base import BaseListScreen
from . import player as vlc_player


class SeriesListScreen(BaseListScreen):
    screen_name = "SmartysSeriesList"
    header_text = "Serien"
    subtitle_text = "Staffeln & Episoden"
    footer = "OK = Öffnen   ·   EXIT = Zurück"

    def _fetch(self):
        series = self.api.series_streams(self.category_id)
        return (
            [(s.get("name", "?"), s) for s in series],
            _("%d Serien") % len(series),
        )

    def _on_select(self, item):
        series_id = item.get("series_id")
        self.session.open(EpisodeListScreen, self.api, series_id)


class EpisodeListScreen(BaseListScreen):
    screen_name = "SmartysEpisodes"
    header_text = "Episoden"
    subtitle_text = ""

    def __init__(self, session, api, series_id):
        # Episode-Screen erhält die fertige API statt cfg
        self._series_id = series_id
        self._api_override = api
        super().__init__(session, None)

    def _build_api(self):
        return self._api_override

    def _fetch(self):
        info = self.api.series_info(self._series_id)
        eps = info.get("episodes") or {}
        flat = []
        for season, ep_list in eps.items():
            for ep in ep_list:
                ep = dict(ep)
                ep["_season"] = season
                flat.append(ep)
        return (
            [("S%sE%s — %s" % (
                e.get("_season", "?"),
                e.get("episode_num", "?"),
                e.get("title") or ""), e) for e in flat],
            _("%d Episoden") % len(flat),
        )

    def _on_select(self, item):
        ep_id = item.get("id")
        ext = item.get("container_extension") or "mp4"
        url = self.api.creds.series_url(ep_id, ext)
        vlc_player.open_player(self.session, url)
