# -*- coding: utf-8 -*-
"""Smartys IPTV — Serien-Detailseite (Cover + Beschreibung).

Nach dem Vorbild der Film-Detailseite: großes Cover links,
Titel/Metadaten/Beschreibung rechts. OK öffnet die Episoden-Liste.
"""

import base64
import os

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap

from . import theme
from . import picon


def _b64(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _wrap(text, width=52):
    if not text:
        return ""
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return "\n".join(lines[:14])


class SeriesDetailScreen(Screen):
    """Serien-Detailseite: Cover links, Beschreibung rechts."""

    def __init__(self, session, api, item):
        self.api = api
        self.item = item or {}
        self.series_id = self.item.get("series_id")
        self.name = self.item.get("name", "")
        self.cover = self.item.get("cover", "") or ""

        w, h = theme.osd_size()
        bg = theme._images_dir()
        self.skin = (
            '<screen name="SmartysSeriesDetail" position="0,0" size="%d,%d" '
            'backgroundColor="%s" flags="wfNoBorder">'
            '<ePixmap pixmap="%s/background.png" position="0,0" size="%d,%d" '
            'alphatest="off" zPosition="-1"/>'
            '<eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" '
            'zPosition="2"/>'
            '<widget name="poster" position="%d,%d" '
            'size="%d,%d" alphatest="blend" zPosition="2"/>'
            '<widget name="header" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="2"/>'
            '<widget name="subtitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="top" zPosition="2"/>'
            '<widget name="desc" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="top" zPosition="2"/>'
            '<widget name="status" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '</screen>' % (
                w, h, theme.BG,
                bg, w, h,
                theme.scale(48), theme.scale_y(40), theme.scale(500),
                theme.scale_y(56), theme.font(28), theme.GOLD,
                theme.scale(48), theme.scale_y(158), theme.scale(200),
                theme.scale_y(3), theme.GOLD,
                theme.scale(60), theme.scale_y(180), theme.scale(240),
                theme.scale_y(360),
                theme.scale(340), theme.scale_y(180), theme.scale(880),
                theme.scale_y(60), theme.font(30), theme.GOLD,
                theme.scale(340), theme.scale_y(248), theme.scale(880),
                theme.scale_y(34), theme.font(18), theme.MUTED,
                theme.scale(340), theme.scale_y(290), theme.scale(880),
                theme.scale_y(320), theme.font(22), theme.TEXT,
                theme.scale(340), theme.scale_y(620), theme.scale(880),
                theme.scale_y(30), theme.font(16), theme.GOLD,
            )
        )
        Screen.__init__(self, session)
        self.session = session

        self["header"] = Label(_(self.name))
        self["subtitle"] = Label(_(""))
        self["desc"] = Label(_(""))
        self["status"] = Label(_(""))
        self["poster"] = Pixmap()

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.episodes,
                "cancel": self.close,
                "yellow": self.trailer,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _load(self):
        plot = _b64(self.item.get("plot", ""))
        genre = self.item.get("genre", "")
        rating = self.item.get("rating", "")
        year = (self.item.get("releaseDate", "") or "")[:4]

        self._load_poster(self.cover)

        if self.name:
            self["header"].setText(_(self.name))

        meta = []
        if year:
            meta.append(_("Jahr %s") % year)
        if rating and rating != "0":
            meta.append(_("IMDb %s") % rating)
        if genre:
            meta.append(_(genre))
        self["subtitle"].setText("   ·   ".join(meta) if meta else "")

        self["desc"].setText(_wrap(plot, 52) if plot else _("Keine Beschreibung"))
        has_trailer = bool(self.item.get("youtube_trailer", ""))
        self["status"].setText(_("OK = Episoden   ·   GELB = Trailer")
                               if has_trailer else _("OK = Episoden"))

    def _load_poster(self, cover_url):
        if not cover_url:
            self["poster"].hide()
            return
        try:
            path = picon._download(cover_url, "vod_%s" % self.series_id,
                                   size=(theme.scale(240), theme.scale_y(360)))
            if path and os.path.exists(path):
                self["poster"].instance.setPixmap(LoadPixmap(path))
                self["poster"].show()
                return
        except Exception:
            pass
        self["poster"].hide()

    def episodes(self):
        from .serieslist import EpisodeListScreen
        self.session.open(EpisodeListScreen, self.api, self.series_id,
                          self.name)

    def trailer(self):
        from Screens.MessageBox import MessageBox
        from . import player as vlc_player
        url = self.item.get("youtube_trailer", "")
        if not url:
            self.session.open(
                MessageBox, _("Kein Trailer verfügbar."),
                MessageBox.TYPE_INFO, timeout=4)
            return
        self["status"].setText(_("Lade Trailer …"))
        path = vlc_player.download_trailer(url)
        if not path:
            self.session.open(
                MessageBox, _("Trailer konnte nicht geladen werden."),
                MessageBox.TYPE_ERROR, timeout=4)
            self["status"].setText(_("OK = Episoden   ·   GELB = Trailer"))
            return
        vlc_player.open_player(self.session, path, name="Trailer")
