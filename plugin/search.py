# -*- coding: utf-8 -*-
"""Smartys IPTV — Suche über Filme + Serien.

Zwei Wege, denselben Suchbegriff einzugeben:
  * Fernbedienung: GRUEN oeffnet die Enigma2-Tastatur (VirtualKeyBoard).
  * Handy: QR-Code scannen, Begriff im Browser tippen — praktisch bei
    langen Titeln, weil T9 auf der Fernbedienung elend ist.
Gleiche Such-Semantik wie die Desktop-Version: case-insensitive Substring
auf dem Namen, reines lokales Filtern, Treffer-Kappe.
"""

import os
import threading
import urllib.parse
import urllib.request

from Screens.Screen import Screen
from Screens.VirtualKeyBoard import VirtualKeyBoard
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
        self._live = []
        self._loaded = False
        self._pending_query = None
        # Hintergrund-Laden: der Abruf von vod_streams()/series_streams()
        # kann bei grossen Lines dauern und darf den Bildschirm nicht
        # einfrieren (sonst ist die Tastatur nicht bedienbar).
        self._bg_fertig = False
        self._bg_movies = []
        self._bg_series = []
        self._bg_live = []
        self._bg_fehler = None

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
            '%s'
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
                theme.tastenleiste([
                    (theme.TASTE_GRUEN, "GRÜN", "Eingabe"),
                    (theme.TASTE_GELB, "GELB", "Löschen"),
                    (theme.TASTE_BLAU, "BLAU", "Handy"),
                    (None, "OK", "Öffnen"),
                    (None, "EXIT", "Zurück"),
                ]),
            ))

        Screen.__init__(self, session)
        self.session = session
        self["header"] = Label(_("Suche"))
        self["subtitle"] = Label(_("Filme + Serien durchsuchen"))
        self["list"] = MenuList([])
        self["qr"] = Pixmap()
        self["status"] = Label(_("Lade …"))
        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions", "SearchActions"],
            {"ok": self.on_select,
             "cancel": self.close,
             "green": self.open_keyboard,
             "yellow": self.clear_search,
             "blue": self.show_handy},
            -1)

        # Handy-Eingabe (Text-Modus) + QR.
        self._web_url = None
        # Timer fuer die Tastatur (siehe _start).
        self._kb_timer = eTimer()
        try:
            self._kb_timer.callback.append(self.open_keyboard)
        except Exception:
            self._kb_timer.timeout.connect(self.open_keyboard)
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
        self._query = ""
        self.onLayoutFinish.append(self._start)

    def _start(self):
        """Beim Oeffnen: Tastatur zeigen und Daten im Hintergrund laden."""
        threading.Thread(target=self._preload, daemon=True).start()
        # Die Tastatur darf NICHT direkt aus onLayoutFinish geoeffnet werden:
        # zu dem Zeitpunkt ist der Dialog noch nicht fertig aufgebaut und
        # Enigma2 wirft "Modal open are allowed only from a screen which is
        # modal!". Ein kurzer Timer loest das sauber.
        self._kb_timer.start(400, True)

    def open_keyboard(self):
        """Fernbedienung: Suchbegriff ueber die Enigma2-Tastatur eingeben."""
        def fertig(text):
            text = (text or "").strip()
            if not text:
                return
            self._query = text
            self["subtitle"].setText(
                _("Filme + Serien durchsuchen — „%s“") % text)
            self._run_search(text)
        self.session.openWithCallback(fertig, VirtualKeyBoard,
                                      text=self._query,
                                      title=_("Suchbegriff"))

    def clear_search(self):
        """GELB: Suchbegriff und Trefferliste leeren."""
        self._query = ""
        self["list"].setList([])
        self["subtitle"].setText(_("Filme + Serien durchsuchen"))
        self._status_normal()

    def show_handy(self):
        """BLAU: Adresse fuer die Handy-Eingabe in den Status holen."""
        if self._web_url:
            self["status"].setText(
                _("Am Handy öffnen: %s") % self._web_url)
        else:
            self["status"].setText(
                _("Handy-Eingabe nicht verfügbar — nutze GRÜN"))

    def _preload(self):
        """Laedt Sender, Filme + Serien (laeuft im Hintergrund-Thread).

        Sender nur aus den EINGEBLENDETEN Gruppen: bei einer Testline mit
        hunderten Gruppen waere eine Suche ueber alles unbrauchbar — was man
        ausgeblendet hat, will man auch nicht in den Treffern sehen.
        """
        if self._loaded:
            return
        self._loaded = True
        if not self.api:
            self._bg_fehler = _("Nicht verbunden")
            self._bg_fertig = True
            return

        # --- Sender, nur eingeblendete Gruppen -------------------------
        try:
            self._bg_live = self._lade_gefiltert(
                "live", self.api.live_categories, self.api.live_streams)
        except Exception:
            self._bg_live = []

        try:
            self._bg_movies = self._lade_gefiltert(
                "vod", self.api.vod_categories, self.api.vod_streams)
        except Exception:
            self._bg_movies = []
        try:
            self._bg_series = self._lade_gefiltert(
                "series", self.api.series_categories, self.api.series_streams)
        except Exception:
            self._bg_series = []
        self._bg_fertig = True

    def _lade_gefiltert(self, bereich, hole_gruppen, hole_eintraege):
        """Eintraege nur aus den eingeblendeten Gruppen eines Bereichs.

        Filme und Serien kamen vorher ungefiltert aus allen Kategorien —
        bei einer Line mit |DE|/|EN|/|FR|/... -Paketen liefert die Suche
        nach 'lupin' dann jede Sprachfassung statt nur die eigenen.
        Ist im Bereich nichts ausgeblendet, wird in einem Zug alles geladen
        (deutlich schneller als ein Request je Gruppe).
        """
        versteckt = set(self.cfg.get("hidden_categories_%s" % bereich, []) or [])
        if not versteckt:
            return hole_eintraege() or []
        try:
            gruppen = hole_gruppen() or []
        except Exception:
            return hole_eintraege() or []
        sichtbar = [g for g in gruppen
                    if g.get("category_name") not in versteckt]
        if not sichtbar:
            # Alles ausgeblendet -> lieber alles als eine leere Suche.
            return hole_eintraege() or []
        ergebnis = []
        for g in sichtbar:
            try:
                teile = hole_eintraege(g.get("category_id")) or []
            except Exception:
                continue
            for x in teile:
                x.setdefault("_gruppe", g.get("category_name", ""))
            ergebnis.extend(teile)
        return ergebnis

    def _status_normal(self):
        if not self._bg_fertig:
            self["status"].setText(_("Lade Filme und Serien …"))
            return
        if self._bg_fehler:
            self["status"].setText(str(self._bg_fehler))
            return
        self["status"].setText(
            _("%d Sender · %d Filme · %d Serien — GRÜN für Eingabe, Handy: %s")
            % (len(self._live), len(self._movies), len(self._series),
               self._web_url or "—"))

    def _web_receive(self, text):
        # Läuft im Server-Thread — nur Variable setzen, UI-Update im Poll.
        self._pending_query = text
        return True

    def _web_poll(self):
        # MainThread: ausstehenden Suchtext verarbeiten und Hintergrund-Laden
        # uebernehmen (der Thread setzt nur Variablen, die UI liest sie hier).
        if self._bg_fertig and self._movies is not self._bg_movies:
            self._movies = self._bg_movies
            self._series = self._bg_series
            self._live = self._bg_live
            if not self._query:
                self._status_normal()
        if self._pending_query is not None:
            q = self._pending_query
            self._pending_query = None
            self._query = (q or "").strip()
            self._run_search(q)

    def _run_search(self, query):
        q = (query or "").strip().lower()
        if not q:
            return
        if not self._bg_fertig:
            self["status"].setText(
                _("Filme und Serien werden noch geladen — gleich nochmal"))
            self._pending_query = query
            return
        if self._movies is not self._bg_movies:
            self._movies = self._bg_movies
            self._series = self._bg_series
            self._live = self._bg_live
        results = []
        for st in self._live:
            name = st.get("name", "") or ""
            if q in name.lower():
                gruppe = st.get("_gruppe", "")
                label = name if not gruppe else "%s  (%s)" % (name, gruppe)
                results.append(("[Sender] " + label, ("live", st)))
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
        if kind == "live":
            from . import vlc_player
            url = self.api.creds.stream_url(item.get("stream_id"), "ts")
            vlc_player.open_player(self.session, url,
                                   name=item.get("name", ""),
                                   stream_id=item.get("stream_id"),
                                   api=self.api,
                                   stream_icon=item.get("stream_icon", ""))
            return
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
