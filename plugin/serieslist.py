# -*- coding: utf-8 -*-
"""Smartys IPTV — Serien (Cover + Liste + Detailseite mit Episoden).

Nach dem Vorbild der Film-Ansicht: großes Cover links, Liste rechts;
Detailseite mit Cover + Beschreibung; OK öffnet die Episoden-Liste.
"""

import base64
import os

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap

from . import theme
from . import picon
from . import player as vlc_player
from .api import Credentials, XtreamApi


def _b64(s):
    try:
        return base64.b64decode(s, validate=True).decode("utf-8", "replace")
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
    return "\n".join(lines[:10])


def _build_api(cfg):
    providers = cfg.providers() if cfg else []
    if not providers:
        return None
    p = providers[0]
    return XtreamApi(Credentials(p["server_url"], p["username"], p["password"]))


class SeriesListScreen(Screen):
    """Serien-Liste: Poster links, Liste rechts."""

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        w, h = theme.osd_size()
        bg = theme._images_dir()
        self._header = header_text or "Serien"
        self._subtitle = subtitle_text or "Staffeln & Episoden"
        self.skin = (
            '<screen name="SmartysSeriesList" position="0,0" size="%d,%d" '
            'backgroundColor="%s" flags="wfNoBorder">'
            '<ePixmap pixmap="%s/background.png" position="0,0" size="%d,%d" '
            'alphatest="off" zPosition="-1"/>'
            '<eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" '
            'zPosition="2"/>'
            '<widget name="header" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<widget name="subtitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<widget name="poster" position="%d,%d" size="%d,%d" '
            'alphatest="blend" zPosition="2"/>'
            '<widget name="list" position="%d,%d" size="%d,%d" '
            'render="Listbox" itemHeight="%d" scrollbarMode="showOnDemand" '
            'foregroundColor="%s" foregroundColorSelected="%s" '
            'backgroundColor="%s" backgroundColorSelected="%s" '
            'transparent="1" zPosition="2"/>'
            '<widget name="status" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '</screen>' % (
                w, h, theme.BG, bg, w, h,
                theme.scale(48), theme.scale_y(40), theme.scale(500),
                theme.scale_y(56), theme.font(28), theme.GOLD,
                theme.scale(48), theme.scale_y(158), theme.scale(200),
                theme.scale_y(3), theme.GOLD,
                theme.scale(48), theme.scale_y(96), theme.scale(1100),
                theme.scale_y(34), theme.font(22), theme.TEXT,
                theme.scale(48), theme.scale_y(132), theme.scale(1100),
                theme.scale_y(20), theme.font(14), theme.MUTED,
                theme.scale(60), theme.scale_y(180), theme.scale(200),
                theme.scale_y(300),
                theme.scale(300), theme.scale_y(180), theme.scale(920),
                theme.scale_y(400), theme.scale(38),
                theme.TEXT, theme.GOLD, theme.PANEL, theme.SELECT_BG,
                theme.scale(48), theme.scale_y(600), theme.scale(1184),
                theme.scale_y(30), theme.font(15), theme.MUTED,
            )
        )
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.category_id = category_id
        self.api = _build_api(cfg)

        self["header"] = Label(_(self._header))
        self["subtitle"] = Label(_(self._subtitle))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))
        self["poster"] = Pixmap()

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {"ok": self.on_select, "cancel": self.close},
        )
        self["list"].onSelectionChanged.append(self._on_selection_changed)
        self.onLayoutFinish.append(self._load)

    def _load(self):
        if not self.api:
            self["list"].setList([(_("Nicht verbunden"), None)])
            return
        try:
            series = self.api.series_streams(self.category_id)
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self["list"].setList([(s.get("name", "?"), s) for s in series])
        self["status"].setText(_("%d Serien") % len(series))
        self._on_selection_changed()

    def _on_selection_changed(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            self["poster"].hide()
            return
        item = sel[1]
        cover = item.get("cover", "") or ""
        if not cover:
            self["poster"].hide()
            return
        try:
            path = picon._download(cover, "vod_%s" % item.get("series_id"),
                                   size=(theme.scale(200), theme.scale_y(300)))
            if path and os.path.exists(path):
                self["poster"].instance.setPixmap(LoadPixmap(path))
                self["poster"].show()
                return
        except Exception:
            pass
        self["poster"].hide()

    def on_select(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        item = sel[1]
        from .seriesdetail import SeriesDetailScreen
        self.session.open(SeriesDetailScreen, self.api, item)


class EpisodeListScreen(Screen):
    """Episoden-Liste (Staffeln/Episoden), OK = abspielen."""

    def __init__(self, session, api, series_id, name=""):
        w, h = theme.osd_size()
        bg = theme._images_dir()
        self._series_id = series_id
        self._name = name
        self.api = api
        self.skin = (
            '<screen name="SmartysEpisodes" position="0,0" size="%d,%d" '
            'backgroundColor="%s" flags="wfNoBorder">'
            '<ePixmap pixmap="%s/background.png" position="0,0" size="%d,%d" '
            'alphatest="off" zPosition="-1"/>'
            '<eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" '
            'zPosition="2"/>'
            '<widget name="header" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" noWrap="1" zPosition="2"/>'
            '<widget name="list" position="%d,%d" size="%d,%d" '
            'render="Listbox" itemHeight="%d" scrollbarMode="showOnDemand" '
            'foregroundColor="%s" foregroundColorSelected="%s" '
            'backgroundColor="%s" backgroundColorSelected="%s" '
            'transparent="1" zPosition="2"/>'
            '<widget name="status" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="center" valign="center" zPosition="2"/>'
            '</screen>' % (
                w, h, theme.BG, bg, w, h,
                theme.scale(48), theme.scale_y(40), theme.scale(500),
                theme.scale_y(56), theme.font(28), theme.GOLD,
                theme.scale(48), theme.scale_y(158), theme.scale(200),
                theme.scale_y(3), theme.GOLD,
                theme.scale(48), theme.scale_y(96), theme.scale(1100),
                theme.scale_y(40), theme.font(24), theme.TEXT,
                theme.scale(48), theme.scale_y(160), theme.scale(1184),
                theme.scale_y(430), theme.scale(40),
                theme.TEXT, theme.GOLD, theme.PANEL, theme.SELECT_BG,
                theme.scale(48), theme.scale_y(620), theme.scale(1184),
                theme.scale_y(30), theme.font(15), theme.MUTED,
            )
        )
        Screen.__init__(self, session)
        self.session = session
        self["header"] = Label(_(name))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.on_select, "cancel": self.close},
        )
        self.onLayoutFinish.append(self._load)

    def _load(self):
        try:
            info = self.api.series_info(self._series_id)
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        eps = info.get("episodes") or {}

        def _season_key(k):
            """Numerische Staffel-Sortierung ('10' würde sonst vor '2' stehen)."""
            try:
                return (0, int(k), "")
            except (TypeError, ValueError):
                return (1, 0, str(k))

        flat = []
        for season in sorted(eps.keys(), key=_season_key):
            for ep in eps[season]:
                ep = dict(ep)
                ep["_season"] = season
                flat.append(ep)
        self._flat = flat
        self["list"].setList([
            ("S%sE%s — %s" % (
                e.get("_season", "?"),
                e.get("episode_num", "?"),
                _b64(e.get("title") or "")), e) for e in flat])
        self["status"].setText(_("%d Episoden") % len(flat))

    def on_select(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        item = sel[1]
        ep_id = item.get("id")
        ext = item.get("container_extension") or "mp4"
        url = self.api.creds.series_url(ep_id, ext)
        # Auto-Next: die naechste Folge der Liste mitgeben. Laeuft der
        # Stream aus, wechselt der Player selbst weiter.
        next_url, next_name = None, ""
        try:
            flach = getattr(self, "_flat", [])
            idx = self["list"].getSelectedIndex()
            if idx is not None and 0 <= idx < len(flach) - 1:
                nxt = flach[idx + 1]
                n_ext = nxt.get("container_extension") or "mp4"
                next_url = self.api.creds.series_url(nxt.get("id"), n_ext)
                next_name = "S%sE%s — %s" % (
                    nxt.get("_season", "?"), nxt.get("episode_num", "?"),
                    _b64(nxt.get("title") or ""))
        except Exception:
            pass
        vlc_player.open_player(self.session, url, name=self._name,
                               servicetype=vlc_player.SERVICE_EXTPLAYER3,
                               next_url=next_url, next_name=next_name)
