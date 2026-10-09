# -*- coding: utf-8 -*-
"""Smartys IPTV — Film-Detailseite (Beschreibung, Metadaten, Trailer).

Zeigt die Filminfos aus get_vod_info vor dem Abspielen.
OK = abspielen, YELLOW = Trailer (sofern vorhanden).
"""

import base64

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from enigma import eServiceReference

from . import theme
from . import player as vlc_player


def _b64(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _wrap(text, width=52):
    """Bricht Text grob auf mehrere Zeilen um (für Label-Anzeige)."""
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
    return "\n".join(lines[:8])  # max 8 Zeilen


class VodDetailScreen(Screen):
    """Film-Detailseite."""

    def __init__(self, session, api, stream_id, name=""):
        self.skin = theme.build_skin(
            "SmartysVodDetail", logo=False,
            footer="OK = Abspielen   ·   GELB = Trailer   ·   EXIT = Zurück")
        Screen.__init__(self, session)
        self.session = session
        self.api = api
        self.stream_id = stream_id
        self.name = name

        self["header"] = Label(_(name))
        self["subtitle"] = Label(_(""))
        self["list"] = Label(_(""))
        self["status"] = Label(_(""))

        self._trailer = None

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.play,
                "cancel": self.close,
                "yellow": self.trailer,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _load(self):
        info = {}
        try:
            data = self.api.vod_info(self.stream_id)
            info = data.get("info", {}) or {}
        except Exception:
            pass

        title = _b64(info.get("name", "")) or self.name
        plot = _b64(info.get("plot", "") or info.get("description", ""))
        duration = info.get("duration", "")
        genre = info.get("genre", "")
        rating = info.get("rating", "")
        year = (info.get("releasedate", "") or "")[:4]
        self._trailer = info.get("youtube_trailer", "")

        if title:
            self["header"].setText(_(title))

        meta = []
        if year:
            meta.append(_("Jahr: %s") % year)
        if duration:
            meta.append(_("Dauer: %s min") % duration)
        if rating:
            meta.append(_("Bewertung: %s") % rating)
        if genre:
            meta.append(_("Genre: %s") % genre)
        self["subtitle"].setText("  ·  ".join(meta) if meta else "")

        self["list"].setText(_wrap(plot) if plot else _("Keine Beschreibung"))
        self["status"].setText(_("Trailer verfügbar") if self._trailer else "")

    def play(self):
        ext = self._ext()
        url = self.api.creds.movie_url(self.stream_id, ext)
        vlc_player.open_player(self.session, url, name=self.name)

    def _ext(self):
        return "mp4"

    def trailer(self):
        if not self._trailer:
            self.session.open(
                MessageBox, _("Kein Trailer verfügbar."),
                MessageBox.TYPE_INFO, timeout=4)
            return
        # Trailer (YouTube) über den Stream-Player abspielen.
        vlc_player.open_player(self.session, self._trailer, name="Trailer")
