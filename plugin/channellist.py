# -*- coding: utf-8 -*-
"""Smartys IPTV — Live-TV-Kanalliste (Kategorie-Filter, Aufnahme, Vorschau, EPG, Picon)."""

import base64

from Screens.MessageBox import MessageBox
from Components.Label import Label
from Components.MenuList import MenuList
from Components.Pixmap import Pixmap
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from .screens_base import BaseListScreen
from . import player as vlc_player
from . import recorder
from . import picon


def _b64(s):
    try:
        return base64.b64decode(s, validate=True).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _fmt_time(s):
    if not s:
        return ""
    s = s.strip()
    if len(s) >= 16:
        try:
            return s[11:16]
        except Exception:
            pass
    return s


class LiveListScreen(BaseListScreen):
    screen_name = "SmartysLiveList"
    header_text = "Live-TV"
    subtitle_text = "Sender wählen"
    preview = True
    epg = True
    picon = True
    from . import theme as _theme
    tasten = [
        (_theme.TASTE_OK, "OK", "Abspielen"),
        (_theme.TASTE_ROT, "ROT", "Aufnahme"),
        (_theme.TASTE_GELB, "GELB", "Favorit"),
        (_theme.TASTE_BLAU, "BLAU", "Sortierung"),
        (None, "EXIT", "Zurück"),
    ]

    # Sortiermodi in der Reihenfolge, in der BLAU sie durchschaltet.
    # "original" ist die Reihenfolge des Anbieters — die hat oft System
    # (HD vor SD, nach Region), deshalb bleibt sie der erste Zustand.
    SORT_MODES = ("original", "az", "za", "fav_first")
    SORT_LABEL = {
        "original": "Anbieter",
        "az": "A-Z",
        "za": "Z-A",
        "fav_first": "Favoriten zuerst",
    }

    def __init__(self, session, cfg, category_id=None,
                 header_text=None, subtitle_text=None):
        # Vorschau (PIP) aus den Einstellungen lesen, bevor der Skin gebaut wird.
        try:
            from .config import Config
            self.preview = bool(Config().load().get("preview", True))
        except Exception:
            self.preview = True
        # "__fav__" ist kein echtes Kategorie-ID, sondern der Wunsch nach
        # einer reinen Favoritenliste (kommt aus categories.py).
        self.favorites_only = (category_id == "__fav__")
        if self.favorites_only:
            category_id = None
        super().__init__(session, cfg, category_id, header_text, subtitle_text)

        self["epg"] = Label()
        self["picon"] = Pixmap()

        # Debounce-Timer: Vorschau erst nach kurzem Verharren auf einem Sender.
        self._preview_timer = eTimer()
        try:
            self._preview_timer.callback.append(self._preview_tick)
        except Exception:
            self._preview_timer.timeout.connect(self._preview_tick)

        # EPG-Timer (etwas schneller als die Vorschau).
        self._epg_timer = eTimer()
        try:
            self._epg_timer.callback.append(self._update_epg)
        except Exception:
            self._epg_timer.timeout.connect(self._update_epg)

        # Picon-Timer: Logo des markierten Senders aktualisieren.
        self._picon_timer = eTimer()
        try:
            self._picon_timer.callback.append(self._update_picon)
        except Exception:
            self._picon_timer.timeout.connect(self._update_picon)

        self["list"].onSelectionChanged.append(self._on_selection_changed)
        # Beim Verlassen der Liste: Vorschau stoppen (läuft sonst im
        # Hintergrund weiter) und Debounce-Timer abmelden (die würden
        # nach dem Close auf zerstörte Widgets zugreifen).
        self._preview_started = False
        self.onClose.append(self._on_close)

    def on_yellow(self):
        """GELB: markierten Sender als Favorit merken oder entfernen."""
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        sid = sel[1].get("stream_id")
        if sid is None:
            return
        neu = self.cfg.toggle_favorite(sid)
        name = sel[1].get("name", "?")
        self["status"].setText(
            _("%s ist jetzt Favorit") % name if neu
            else _("%s ist kein Favorit mehr") % name)
        # Liste neu aufbauen, damit das Sternchen sofort erscheint.
        self._reload()

    def on_blue(self):
        """BLAU: Sortierung durchschalten (Anbieter -> A-Z -> Z-A -> Favoriten)."""
        aktuell = self.cfg.get("sort_mode", "original")
        try:
            idx = self.SORT_MODES.index(aktuell)
        except ValueError:
            idx = 0
        neu = self.SORT_MODES[(idx + 1) % len(self.SORT_MODES)]
        self.cfg.set("sort_mode", neu)
        try:
            self.cfg.save()
        except Exception:
            pass
        # Markierung merken, damit man nach dem Umsortieren nicht wieder
        # oben in der Liste landet und den Sender suchen muss.
        sel = self["list"].getCurrent()
        merken = sel[1].get("stream_id") if sel and sel[1] else None
        self._reload()
        self["status"].setText(
            _("Sortierung: %s") % self.SORT_LABEL.get(neu, neu))
        self._springe_zu(merken)

    def _springe_zu(self, stream_id):
        """Cursor auf den zuvor markierten Sender setzen (nach Sortierung)."""
        if stream_id is None:
            return
        try:
            eintraege = self["list"].list or []
        except Exception:
            return
        for i, eintrag in enumerate(eintraege):
            daten = eintrag[1] if isinstance(eintrag, (tuple, list)) and len(eintrag) > 1 else None
            if isinstance(daten, dict) and daten.get("stream_id") == stream_id:
                try:
                    self["list"].moveToIndex(i)
                except Exception:
                    pass
                return

    def _reload(self):
        try:
            items, status = self._fetch()
        except Exception:
            return
        self["list"].setList(items)
        self["status"].setText(status)

    def _on_close(self):
        for t in (self._preview_timer, self._epg_timer, self._picon_timer):
            try:
                t.stop()
            except Exception:
                pass
        try:
            self._epg_poll_timer.stop()
        except Exception:
            pass
        if self._preview_started:
            try:
                self.session.nav.stopService()
            except Exception:
                pass

    def _fetch(self):
        streams = self.api.live_streams(self.category_id)
        # Manche Panels liefern Kategorie-Trenner als Pseudo-Sender mit
        # ("##### BELGIUM HD #####"). Sie haben keinen spielbaren Stream und
        # stehen als erste Zeile in der Liste — dann bleibt die Vorschau
        # schwarz und das Logo leer. Also rausfiltern.
        echte = []
        for s in streams:
            name = (s.get("name") or "").strip()
            if not name or name.startswith("#####") or name.startswith("----"):
                continue
            try:
                if int(s.get("stream_id") or 0) <= 0:
                    continue
            except Exception:
                continue
            echte.append(s)
        favs = self.cfg.favorites()
        if self.favorites_only:
            # Auf "echte" filtern, nicht auf "streams": daraus wird die Liste
            # gebaut, ein Filter auf streams haette keine Wirkung.
            favs_set = set(favs)
            echte = [s for s in echte
                     if str(s.get("stream_id")) in favs_set]
        eintraege = []
        for s in echte:
            name = s.get("name", "?")
            if str(s.get("stream_id")) in favs:
                # Kein Emoji: die Box rendert sie als leeres Kaestchen.
                name = "* " + name
            eintraege.append((name, s))

        # Sortierung anwenden. Der Vergleich läuft auf dem Sendernamen ohne
        # das Favoriten-Sternchen und ohne führende Zahlen, sonst sortiert
        # "1. Das Erste" vor "ARD" obwohl der Nutzer alphabetisch meint.
        modus = self.cfg.get("sort_mode", "original")
        if modus in ("az", "za", "fav_first"):
            eintraege = self._sortiere(eintraege, modus, favs)

        return (eintraege, _("%d Sender") % len(echte))

    def _sortiere(self, eintraege, modus, favs):
        """Sortiert die Liste nach dem gewählten Modus."""
        def schluessel(eintrag):
            daten = eintrag[1] if isinstance(eintrag, (tuple, list)) else eintrag
            name = (daten.get("name") or "").strip()
            # Favoriten-Sternchen abschneiden, sonst stehen alle Favoriten
            # gemeinsam unter "*" am Anfang.
            if name.startswith("* "):
                name = name[2:]
            return name.casefold()

        if modus == "az":
            return sorted(eintraege, key=schluessel)
        if modus == "za":
            return sorted(eintraege, key=schluessel, reverse=True)
        # fav_first: Favoriten nach oben, innerhalb der Gruppen alphabetisch
        fav_set = set(favs)

        def fav_schluessel(eintrag):
            daten = eintrag[1] if isinstance(eintrag, (tuple, list)) else eintrag
            ist_fav = str(daten.get("stream_id")) in fav_set
            return (0 if ist_fav else 1, schluessel(eintrag))

        return sorted(eintraege, key=fav_schluessel)

    def _on_select(self, ch):
        stream_id = ch.get("stream_id")
        name = ch.get("name", "")
        stream_icon = ch.get("stream_icon", "")
        url = self.api.creds.stream_url(stream_id, "ts")
        recorder.confirm_if_recording(
            self.session,
            lambda: self._open_player(url, name, stream_id, stream_icon))

    def _open_player(self, url, name="", stream_id=None, stream_icon=None):
        """Vollbild: StreamPlayer-Screen öffnen (rendert das Video + EPG)."""
        vlc_player.open_player(self.session, url, name=name,
                               stream_id=stream_id, api=self.api,
                               stream_icon=stream_icon)

    def _on_selection_changed(self):
        # Vorschau + EPG + Picon verzögert starten.
        self._preview_timer.start(600, True)
        self._epg_timer.start(300, True)
        self._picon_timer.start(150, True)

    def _current_stream(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return None
        return sel[1]

    def _preview_tick(self):
        """Spielt den markierten Sender im Pig-Fenster ab (Live-Vorschau)."""
        ch = self._current_stream()
        if not ch:
            return
        url = self.api.creds.stream_url(ch.get("stream_id"), "ts")
        # GStreamer (4097) fuer das Vorschaufenster: exteplayer3 uebernimmt
        # den Decoder im Vollbild und rendert nicht in ein Pig.
        if vlc_player.play_service(
                self.session, url, servicetype=vlc_player.SERVICE_EXTPLAYER3):
            self._preview_started = True

    def _update_picon(self):
        """Lädt/zeigt das Senderlogo des markierten Senders."""
        ch = self._current_stream()
        if not ch:
            return
        sid = str(ch.get("stream_id", ""))
        icon_url = ch.get("stream_icon", "")
        picon.request(icon_url, sid)
        path = picon.logo_path(sid)
        if picon.has_logo(sid):
            try:
                pix = LoadPixmap(path)
                if pix:
                    self["picon"].instance.setPixmap(pix)
            except Exception:
                pass

    def _update_epg(self):
        """Lädt short_epg asynchron (Thread) und zeigt 'Jetzt / Danach' unter der Liste."""
        ch = self._current_stream()
        if not ch:
            self["epg"].setText("")
            return
        stream_id = ch.get("stream_id")
        # Token: eine veraltete Antwort (Nutzer ist weitergescrollt) darf nicht
        # über einem anderen Sender landen.
        self._epg_token = getattr(self, "_epg_token", 0) + 1
        token = self._epg_token

        def _fetch():
            try:
                data = self.api.short_epg(stream_id, limit=2)
            except Exception:
                data = None
            self._epg_result = (token, stream_id, data)

        import threading
        threading.Thread(target=_fetch, daemon=True).start()

        # eTimer pollt das Ergebnis und aktualisiert das Label im Mainloop.
        def _poll():
            result = getattr(self, "_epg_result", None)
            if result is None:
                try:
                    self._epg_poll_timer.start(200, True)
                except Exception:
                    pass
                return
            self._epg_result = None
            tok, sid, data = result
            cur = self._current_stream()
            if tok != getattr(self, "_epg_token", 0) or \
                    (cur and cur.get("stream_id") != sid):
                return  # veraltet — Sender hat gewechselt
            if not data:
                self["epg"].setText(_("Keine EPG-Daten"))
                return
            listings = data.get("epg_listings", []) or []
            if not listings:
                self["epg"].setText(_("Keine EPG-Daten"))
                return
            now = listings[0]
            txt = "Jetzt: %s  (%s–%s)" % (
                _b64(now.get("title", "")),
                _fmt_time(now.get("start", "")),
                _fmt_time(now.get("end", "")),
            )
            if len(listings) > 1:
                nxt = listings[1]
                txt += "    ·    Danach: %s  (%s)" % (
                    _b64(nxt.get("title", "")),
                    _fmt_time(nxt.get("start", "")),
                )
            self["epg"].setText(txt)

        self._epg_poll_timer = eTimer()
        try:
            self._epg_poll_timer.callback.append(_poll)
        except Exception:
            self._epg_poll_timer.timeout.connect(_poll)
        self._epg_poll_timer.start(200, True)

    def on_red(self):
        """ROT = Aufnahme starten/stoppen für den markierten Sender."""
        ch = self._current_stream()
        if not ch:
            return
        name = ch.get("name", "Sender")
        stream_id = ch.get("stream_id")
        url = self.api.creds.stream_url(stream_id, "ts")

        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            def _starten(ja):
                if not ja:
                    return
                recorder.ask_recording(self.session, url, name,
                                       api=self.api, stream_id=stream_id)

            # Erst warnen, dann die eigentliche Aufnahmefrage — sonst
            # startet die Aufnahme und der Nutzer merkt zu spaet, dass er
            # nicht mehr umschalten kann.
            self.session.openWithCallback(
                _starten, MessageBox,
                _("Aufnahme starten: %s\n\n%s\n\nFortfahren?")
                % (name, recorder.verbindungs_hinweis(self.api)),
                MessageBox.TYPE_YESNO)

    def on_info(self):
        """EPG/INFO = EPG-Ansicht des markierten Senders öffnen."""
        ch = self._current_stream()
        if not ch:
            return
        from .epg import EpgScreen
        self.session.open(
            EpgScreen, self.api, ch.get("stream_id"), ch.get("name", ""))
