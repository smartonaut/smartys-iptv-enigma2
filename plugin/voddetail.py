# -*- coding: utf-8 -*-
"""Smartys IPTV — Film-Detailseite (Cover + große Beschreibung).

Nach dem Vorbild der Desktop/APK-Version (MovieDetailScreen):
großes Poster links, Titel/Metadaten/Beschreibung rechts.
OK = abspielen, GELB = Trailer (sofern vorhanden).
"""

import base64
import os

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from . import theme
from . import player as vlc_player
from . import picon


def _b64(s):
    try:
        return base64.b64decode(s, validate=True).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _wrap(text, width=52):
    """Bricht Text auf Zeilen um (für die große Beschreibung)."""
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


class VodDetailScreen(Screen):
    """Film-Detailseite: Cover links, Beschreibung rechts."""

    def __init__(self, session, api, stream_id, name="", stream_icon=None):
        self.api = api
        self.stream_id = stream_id
        self.name = name
        self.stream_icon = stream_icon or ""

        w, h = theme.osd_size()
        bg = theme._images_dir()
        self.skin = (
            '<screen name="SmartysVodDetail" position="0,0" size="%d,%d" '
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
                # poster (Cover) links, 2:3
                theme.scale(60), theme.scale_y(180), theme.scale(240),
                theme.scale_y(360),
                # header (Titel)
                theme.scale(340), theme.scale_y(180), theme.scale(880),
                theme.scale_y(60), theme.font(30), theme.GOLD,
                # subtitle (Metadaten)
                theme.scale(340), theme.scale_y(248), theme.scale(880),
                theme.scale_y(34), theme.font(18), theme.MUTED,
                # desc (Beschreibung, groß)
                theme.scale(340), theme.scale_y(290), theme.scale(880),
                theme.scale_y(320), theme.font(22), theme.TEXT,
                # status (Trailer-Hinweis)
                theme.scale(340), theme.scale_y(620), theme.scale(880),
                theme.scale_y(30), theme.font(16), theme.GOLD,
            )
        )
        Screen.__init__(self, session)
        self.session = session

        self["header"] = Label(_(name))
        self["subtitle"] = Label(_(""))
        self["desc"] = Label(_(""))
        self["status"] = Label(_(""))
        self["poster"] = Pixmap()

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

        # Cover laden (stream_icon aus der Liste, Fallback auf vod_info-Cover).
        cover_url = self.stream_icon or info.get("stream_icon", "") or \
            info.get("cover_big", "") or info.get("movie_image", "")
        self._load_poster(cover_url)

        if title:
            self["header"].setText(_(title))

        meta = []
        if year:
            meta.append(_("Jahr %s") % year)
        if duration:
            meta.append(_("%s min") % duration)
        if rating and rating != "0":
            meta.append(_("IMDb %s") % rating)
        if genre:
            meta.append(_(genre))
        self["subtitle"].setText("   ·   ".join(meta) if meta else "")

        self["desc"].setText(_wrap(plot, 52) if plot else _("Keine Beschreibung"))
        self["status"].setText(_("GELB = Trailer ansehen") if self._trailer else "")

    def _load_poster(self, cover_url):
        """Lädt das Film-Cover (Poster) in das Pixmap."""
        if not cover_url:
            self["poster"].hide()
            return
        try:
            path = picon._download(cover_url, "vod_%s" % self.stream_id,
                                   size=(theme.scale(240), theme.scale_y(360)))
            if path and os.path.exists(path):
                self["poster"].instance.setPixmap(LoadPixmap(path))
                self["poster"].show()
                return
        except Exception:
            pass
        self["poster"].hide()

    def play(self):
        ext = "mp4"
        url = self.api.creds.movie_url(self.stream_id, ext)
        vlc_player.open_player(self.session, url, name=self.name)

    def trailer(self):
        if not self._trailer:
            self.session.open(
                MessageBox, _("Kein Trailer verfügbar."),
                MessageBox.TYPE_INFO, timeout=4)
            return
        self["status"].setText(_("Lade Trailer …"))
        self._trailer_result = {}

        # Download im Hintergrund-Thread — sonst friert der Mainloop bis zu
        # 180 s ein (yt-dlp + Merge), und die Box wirkt tot.
        def _download():
            self._trailer_result["path"] = vlc_player.download_trailer(
                self._trailer)

        import threading
        threading.Thread(target=_download, daemon=True).start()

        # eTimer pollt das Ergebnis und öffnet den Player im Mainloop.
        def _poll():
            if "path" not in self._trailer_result:
                try:
                    self._trailer_timer.start(300, True)
                except Exception:
                    pass
                return
            try:
                self._trailer_timer.stop()
            except Exception:
                pass
            path = self._trailer_result.get("path")
            if not path:
                self.session.open(
                    MessageBox, _("Trailer konnte nicht geladen werden."),
                    MessageBox.TYPE_ERROR, timeout=4)
                self["status"].setText(_("GELB = Trailer ansehen"))
                return
            vlc_player.open_player(self.session, path, name="Trailer")

        self._trailer_timer = eTimer()
        try:
            self._trailer_timer.callback.append(_poll)
        except Exception:
            self._trailer_timer.timeout.connect(_poll)
        self._trailer_timer.start(300, True)
