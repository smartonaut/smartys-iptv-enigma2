# -*- coding: utf-8 -*-
"""Smartys IPTV — VOD (Filme) Liste mit Poster-Cover.

Großes Cover links (des markierten Films) + Filmliste rechts.
OK öffnet die Detailseite (Cover + Beschreibung).
"""

import os

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap

from . import theme
from . import picon
from .api import Credentials, XtreamApi


class VodListScreen(Screen):
    """Film-Liste: Poster links, Liste rechts."""

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        w, h = theme.osd_size()
        bg = theme._images_dir()
        self._header = header_text or "Filme"
        self._subtitle = subtitle_text or "Video-on-Demand"
        self.skin = (
            '<screen name="SmartysVodList" position="0,0" size="%d,%d" '
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
            # Poster (Cover) links
            '<widget name="poster" render="Pixmap" position="%d,%d" '
            'size="%d,%d" alphatest="blend" zPosition="2"/>'
            # Liste rechts
            '<widget name="list" position="%d,%d" size="%d,%d" '
            'render="Listbox" itemHeight="%d" scrollbarMode="showOnDemand" '
            'foregroundColor="%s" foregroundColorSelected="%s" '
            'backgroundColor="%s" backgroundColorSelected="%s" '
            'transparent="1" zPosition="2"/>'
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
                theme.scale(48), theme.scale_y(96), theme.scale(1100),
                theme.scale_y(34), theme.font(22), theme.TEXT,
                theme.scale(48), theme.scale_y(132), theme.scale(1100),
                theme.scale_y(20), theme.font(14), theme.MUTED,
                # poster
                theme.scale(60), theme.scale_y(180), theme.scale(200),
                theme.scale_y(300),
                # liste
                theme.scale(300), theme.scale_y(180), theme.scale(920),
                theme.scale_y(400), theme.scale(38),
                theme.TEXT, theme.GOLD, theme.PANEL, theme.SELECT_BG,
                # status
                theme.scale(48), theme.scale_y(600), theme.scale(1184),
                theme.scale_y(30), theme.font(15), theme.MUTED,
            )
        )
        Screen.__init__(self, session)
        self.session = session
        self.cfg = cfg
        self.category_id = category_id

        self.api = self._build_api()

        self["header"] = Label(_(self._header))
        self["subtitle"] = Label(_(self._subtitle))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))
        self["poster"] = Pixmap()

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.on_select,
                "cancel": self.close,
            },
        )
        self["list"].onSelectionChanged.append(self._on_selection_changed)
        self.onLayoutFinish.append(self._load)

    def _build_api(self):
        providers = self.cfg.providers()
        if not providers:
            return None
        p = providers[0]
        return XtreamApi(Credentials(p["server_url"], p["username"], p["password"]))

    def _load(self):
        if not self.api:
            self["list"].setList([(_("Nicht verbunden"), None)])
            return
        try:
            movies = self.api.vod_streams(self.category_id)
        except Exception as e:
            self["list"].setList([(_("Fehler: %s") % str(e), None)])
            return
        self["list"].setList(
            [(m.get("name", "?"), m) for m in movies])
        self["status"].setText(_("%d Filme") % len(movies))
        self._on_selection_changed()

    def _on_selection_changed(self):
        """Lädt das Poster des markierten Films."""
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            self["poster"].hide()
            return
        item = sel[1]
        cover = item.get("stream_icon", "") or ""
        print("[SmartysIPTV] vodlist selection: stream_icon=%s" % (cover[:80] if cover else "LEER"))
        if not cover:
            self["poster"].hide()
            return
        try:
            path = picon._download(cover, "vod_%s" % item.get("stream_id"))
            print("[SmartysIPTV] vodlist poster path=%s" % path)
            if path and os.path.exists(path):
                self["poster"].instance.setPixmap(LoadPixmap(path))
                self["poster"].show()
                return
        except Exception as e:
            print("[SmartysIPTV] vodlist poster FEHLER: %r" % e)
        self["poster"].hide()

    def on_select(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        item = sel[1]
        stream_id = item.get("stream_id")
        name = item.get("name", "")
        stream_icon = item.get("stream_icon", "")
        from .voddetail import VodDetailScreen
        self.session.open(VodDetailScreen, self.api, stream_id, name, stream_icon)
