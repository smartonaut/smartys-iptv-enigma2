# -*- coding: utf-8 -*-
"""Smartys IPTV — Suche über Filme + Serien (Handy-Texteingabe via QR).

Handy-Scan → Suchbegriff übers Handy eingeben → Treffer erscheinen sofort.
Gleiche Such-Semantik wie die Desktop-Version: case-insensitive Substring
auf dem Namen, reines lokales Filtern, Treffer-Kappe.
"""

import os
import urllib.parse
import urllib.request

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from . import theme
from . import unlock_web
from .serieslist import _build_api

MAX_RESULTS = 100


class SearchScreen(Screen):
    def __init__(self, session, cfg):
        w, h = theme.osd_size()
        bg = theme._images_dir()
        self.cfg = cfg
        self.api = _build_api(cfg)
        self._movies = []
        self._series = []
        self._loaded = False
        self._pending_query = None

        self.skin = (
            '<screen name="SmartysSearch" position="0,0" size="%d,%d" '
            'backgroundColor="%s" flags="wfNoBorder">'
            '<ePixmap pixmap="%s/background.png" position="0,0" size="%d,%d" '
            'alphatest="off" zPosition="-1"/>'
            '<eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<widget name="header" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<widget name="subtitle" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" transparent="1" '
            'halign="left" valign="center" zPosition="2"/>'
            '<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" '
            'zPosition="2"/>'
            '<widget name="qr" position="%d,%d" size="%d,%d" scale="1" '
            'zPosition="3" transparent="1" alphatest="blend"/>'
            '<widget name="list" position="%d,%d" size="%d,%d" '
            'render="Listbox" itemHeight="%d" scrollbarMode="showOnDemand" '
            'foregroundColor="%s" foregroundColorSelected="%s" '
            'backgroundColor="%s" backgroundColorSelected="%s" '
            'transparent="1" zPosition="2"/>'
            '<widget name="status" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" halign="center" '
            'valign="center" transparent="1" zPosition="2"/>'
            '<eLabel text="%s" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" halign="left" '
            'valign="center" transparent="1" zPosition="2"/>'
            '</screen>' % (
                w, h, theme.BG,
                bg, w, h,
                theme.scale(150), theme.scale_y(40), theme.scale(500),
                theme.scale_y(56), theme.font(28), theme.GOLD,
                theme.scale(48), theme.scale_y(96), theme.scale(1100),
                theme.scale_y(34), theme.font(22), theme.TEXT,
                theme.scale(48), theme.scale_y(132), theme.scale(1100),
                theme.scale_y(20), theme.font(14), theme.MUTED,
                theme.scale(48), theme.scale_y(158), theme.scale(200),
                theme.scale_y(3), theme.GOLD,
                # QR (links unten)
                theme.scale(48), theme.scale_y(300), theme.scale(160),
                theme.scale_y(160),
                # Liste (rechts)
                theme.scale(240), theme.scale_y(200), theme.scale(920),
                theme.scale_y(400), theme.scale(38),
                theme.TEXT, theme.BG, theme.BG, theme.GOLD,
                # Status
                theme.scale(48), theme.scale_y(620), theme.scale(1184),
                theme.scale_y(30), theme.font(16), theme.MUTED,
                # Footer
                "OK = Öffnen   ·   EXIT = Zurück",
                theme.scale(48), theme.scale_y(678), theme.scale(1184),
                theme.scale_y(30), theme.font(15), theme.MUTED,
            ))

        Screen.__init__(self, session)
        self.session = session
        self["header"] = Label(_("Suche"))
        self["subtitle"] = Label(_("Filme + Serien durchsuchen"))
        self["list"] = MenuList([])
        self["qr"] = Pixmap()
        self["status"] = Label(_("Lade …"))
        self["actions"] = ActionMap(
            ["OkCancelActions"],
            {"ok": self.on_select, "cancel": self.close})

        # Handy-Eingabe (Text-Modus) + QR.
        self._web_url = None
        self._web_timer = eTimer()
        try:
            self._web_timer.callback.append(self._web_poll)
        except Exception:
            self._web_timer.timeout.connect(self._web_poll)
        self._web_timer.start(500, False)
        try:
            port = unlock_web.start(
                self._web_receive,
                title="Smartys Suche",
                hint="Gib einen Suchbegriff ein (Film oder Serie).",
                field_type="text",
                placeholder="Suchbegriff",
                button="Suchen")
            self._web_url = "http://%s:%d" % (unlock_web.lan_ip(), port)
            self.onLayoutFinish.append(self._load_qr)
        except Exception:
            self._web_url = None
        self.onClose.append(self._web_close)
        self.onLayoutFinish.append(self._preload)

    def _preload(self):
        """Lädt Filme + Serien einmalig (für die lokale Suche)."""
        if self._loaded:
            return
        self._loaded = True
        if not self.api:
            self["status"].setText(_("Nicht verbunden"))
            return
        try:
            self._movies = self.api.vod_streams() or []
        except Exception:
            self._movies = []
        try:
            self._series = self.api.series_streams() or []
        except Exception:
            self._series = []
        self["status"].setText(
            _("%d Filme · %d Serien — Suchbegriff übers Handy (%s)")
            % (len(self._movies), len(self._series), self._web_url or "—"))

    def _web_receive(self, text):
        # Läuft im Server-Thread — nur Variable setzen, UI-Update im Poll.
        self._pending_query = text
        return True

    def _web_poll(self):
        # MainThread: ausstehenden Suchtext verarbeiten.
        if self._pending_query is not None:
            q = self._pending_query
            self._pending_query = None
            self._run_search(q)

    def _run_search(self, query):
        q = (query or "").strip().lower()
        if not q:
            return
        results = []
        for m in self._movies:
            if q in (m.get("name", "") or "").lower():
                results.append(("[Film]  " + m.get("name", "?"), ("movie", m)))
        for s in self._series:
            if q in (s.get("name", "") or "").lower():
                results.append(("[Serie] " + s.get("name", "?"), ("series", s)))
        if len(results) > MAX_RESULTS:
            results = results[:MAX_RESULTS]
        self["list"].setList(results)
        self["status"].setText(_("%d Treffer für „%s“") % (len(results), query.strip()))

    def on_select(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        kind, item = sel[1]
        if kind == "movie":
            from .voddetail import VodDetailScreen
            self.session.open(VodDetailScreen, self.api, item.get("stream_id"),
                              item.get("name", ""), item.get("stream_icon", ""))
        else:
            from .serieslist import EpisodeListScreen
            self.session.open(EpisodeListScreen, self.session, self.api,
                              item.get("series_id"), item.get("name", ""))

    def _load_qr(self):
        qr_path = "/tmp/smartys_search_qr.png"
        if not self._web_url:
            self["qr"].hide()
            return
        try:
            from . import qr as qrgen
            if not qrgen.make_png(self._web_url, qr_path):
                self["qr"].hide()
                return
            pix = LoadPixmap(qr_path)
            if pix is not None:
                self["qr"].instance.setPixmap(pix)
                self["qr"].show()
                return
        except Exception:
            pass
        self["qr"].hide()

    def _web_close(self):
        unlock_web.stop()
