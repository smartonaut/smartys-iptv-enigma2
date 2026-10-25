# -*- coding: utf-8 -*-
"""Smartys IPTV — EPG-Uebersicht aller Sender zum Vormerken von Aufnahmen.

Zeigt die laufenden und folgenden Sendungen mehrerer Sender in einer flachen
Liste, nach Sendungsbeginn sortiert. OK auf einer Sendung legt direkt einen
Timer an — man muss nicht erst den Sender oeffnen.

Warum nicht alle Sender: short_epg ist ein Aufruf je Sender. Bei 4000 Sendern
waeren das 4000 Anfragen — der Server drosselt dann. Deshalb wird in Bloecken
geladen: erst die Favoriten, dann die Sender der aktuellen Kategorie.
"""

import base64
import threading
import time

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from enigma import eTimer

from . import theme
from . import recorder


def _b64(s):
    try:
        return base64.b64decode(s, validate=True).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _zeit(ts):
    """Unix-Zeitstempel als HH:MM, oder '' wenn unbrauchbar."""
    try:
        return time.strftime("%H:%M", time.localtime(int(ts)))
    except Exception:
        return ""


class EpgOverviewScreen(Screen):
    """Flache Liste: Zeit | Sender | Sendung — OK legt einen Timer an."""

    screen_name = "SmartysEpgOverview"

    # Sender werden EINZELN abgefragt, mit kurzer Pause dazwischen. Parallele
    # Anfragen beantwortet der Panel-Server mit Fehlern (gemessen: 8 von 8
    # gleichzeitigen short_epg-Aufrufen scheiterten, einzeln liefen sie durch).
    PAUSE = 0.30
    # Hoechstzahl Sender, die ueberhaupt geladen werden.
    MAX_SENDER = 40

    tasten = [
        (theme.TASTE_OK, "OK", "Timer setzen"),
        (theme.TASTE_ROT, "ROT", "Neu laden"),
        (None, "EXIT", "Zurück"),
    ]

    def __init__(self, session, api, cfg, category_id=None):
        self.skin = theme.build_skin(
            self.screen_name, tasten=getattr(self, "tasten", None))
        Screen.__init__(self, session)
        self.session = session
        self.api = api
        self.cfg = cfg
        self.category_id = category_id

        self["header"] = Label(_("EPG-Übersicht"))
        self["subtitle"] = Label(_("Sendung wählen und mit OK vormerken"))
        self["list"] = MenuList([])
        self["status"] = Label(_("Lade Sender …"))

        self._eintraege = []
        self._fertig = 0
        self._gesamt = 0
        self._sperre = threading.Lock()
        self._ergebnisse = {}

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self._timer_setzen,
                "cancel": self.close,
                "red": self._load,
            },
        )
        # Der Laden laeuft im Hintergrund; der Timer schiebt die Liste nach,
        # sobald neue Sendungen da sind. Ohne das bleibt der Screen leer,
        # bis alle Anfragen durch sind.
        self._poll = eTimer()
        try:
            self._poll.callback.append(self._nachziehen)
        except Exception:
            self._poll.timeout.connect(self._nachziehen)
        self.onClose.append(self._stop)
        self.onLayoutFinish.append(self._load)

    def _stop(self):
        try:
            self._poll.stop()
        except Exception:
            pass

    def _load(self):
        """Sender holen und EPG-Abfragen anwerfen (nicht blockierend)."""
        self["list"].setList([])
        self["status"].setText(_("Lade Sender …"))
        self._eintraege = []
        self._ergebnisse = {}
        self._fertig = 0
        try:
            sender = self.api.live_streams(self.category_id)
        except Exception as e:
            self["status"].setText(_("Sender konnten nicht geladen werden: %s")
                                   % str(e)[:50])
            return

        # Kategorie-Trenner und kaputte Eintraege aussortieren
        echte = []
        for s in sender:
            name = (s.get("name") or "").strip()
            if not name or name.startswith("#####") or name.startswith("----"):
                continue
            try:
                if int(s.get("stream_id") or 0) <= 0:
                    continue
            except Exception:
                continue
            echte.append(s)
        if not echte:
            self["status"].setText(_("Keine Sender gefunden"))
            return

        # Favoriten zuerst, dann der Rest — so ist die Uebersicht sofort
        # brauchbar, auch wenn noch nicht alles geladen ist.
        try:
            favs = set(str(f) for f in self.cfg.favorites())
        except Exception:
            favs = set()
        favoriten = [s for s in echte if str(s.get("stream_id")) in favs]
        rest = [s for s in echte if str(s.get("stream_id")) not in favs]
        auswahl = (favoriten + rest)[:self.MAX_SENDER]

        self._gesamt = len(auswahl)
        self["status"].setText(_("Lade EPG für %d Sender …") % self._gesamt)

        # Ein einzelner Arbeiter-Thread fragt der Reihe nach ab. Nebenlaeufig
        # waere schneller, aber der Server drosselt und liefert dann Fehler.
        threading.Thread(target=self._hole_alle, args=(auswahl,),
                         daemon=True).start()
        self._poll.start(700, False)

    def _hole_alle(self, sender):
        """Alle Sender nacheinander abfragen (ein Thread, mit Pausen)."""
        for s in sender:
            try:
                self._hole_epg(s)
            except Exception:
                with self._sperre:
                    self._ergebnisse[s.get("stream_id")] = []
                    self._fertig += 1
            time.sleep(self.PAUSE)

    def _hole_epg(self, sender):
        """EPG eines Senders holen (laeuft im Thread).

        Der Panel-Server laesst einzelne Anfragen gelegentlich in einen
        Timeout laufen (gemessen: 1 von 8 bei 0,35 s Pause). Ein zweiter
        Versuch holt die meisten davon zurueck — ohne ihn fehlt in der
        Uebersicht scheinbar willkuerlich die Haelfte der Sender.
        """
        sid = sender.get("stream_id")
        listings = []
        for versuch in (1, 2):
            try:
                daten = self.api.short_epg(sid, limit=4) or {}
                listings = daten.get("epg_listings", []) or []
                break
            except Exception:
                if versuch == 2:
                    listings = []
                else:
                    time.sleep(0.5)
        zeilen = []
        for ep in listings:
            try:
                start = int(ep.get("start_timestamp") or 0)
                ende = int(ep.get("stop_timestamp") or 0)
            except Exception:
                start = ende = 0
            if not start or not ende:
                continue
            zeilen.append({
                "sender": name,
                "stream_id": sid,
                "titel": _b64(ep.get("title", "")),
                "start": start,
                "ende": ende,
            })
        with self._sperre:
            self._ergebnisse[sid] = zeilen
            self._fertig += 1

    def _nachziehen(self):
        """Liste aus den bisher eingetroffenen Ergebnissen neu aufbauen."""
        with self._sperre:
            fertig = self._fertig
            gesamt = self._gesamt
            alle = []
            for zeilen in self._ergebnisse.values():
                alle.extend(zeilen)

        if not alle and fertig < gesamt:
            # Noch nichts da — weiter warten
            self._poll.start(700, False)
            return

        # Nur Sendungen, die noch nicht vorbei sind
        jetzt = int(time.time())
        alle = [z for z in alle if z["ende"] > jetzt]
        alle.sort(key=lambda z: (z["start"], z["sender"]))

        eintraege = []
        for z in alle:
            text = "%s–%s   %-18s %s" % (
                _zeit(z["start"]), _zeit(z["ende"]),
                z["sender"][:18], z["titel"])
            eintraege.append((text, z))
        self._eintraege = eintraege
        self["list"].setList(eintraege)

        if fertig < gesamt:
            self["status"].setText(
                _("%d Sendungen · lade %d/%d Sender …")
                % (len(eintraege), fertig, gesamt))
            self._poll.start(700, False)
        else:
            self["status"].setText(
                _("%d Sendungen von %d Sendern — OK merkt vor")
                % (len(eintraege), gesamt))

    def _timer_setzen(self):
        """OK: markierte Sendung als Timer-Aufnahme vormerken."""
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return
        z = sel[1]
        jetzt = int(time.time())
        if z["ende"] <= jetzt:
            self.session.open(
                MessageBox, _("Diese Sendung ist bereits vorbei."),
                MessageBox.TYPE_INFO, timeout=4)
            return

        url = self.api.creds.stream_url(z["stream_id"], "ts")
        name = "%s — %s" % (z["sender"], z["titel"])

        def _bestaetigt(ja):
            if not ja:
                return
            recorder.get_scheduler().schedule(url, name, z["start"], z["ende"])
            self.session.open(
                MessageBox,
                _("Timer-Aufnahme geplant:\n%s\n%s–%s") % (
                    name, _zeit(z["start"]), _zeit(z["ende"])),
                MessageBox.TYPE_INFO, timeout=6)

        self.session.openWithCallback(
            _bestaetigt, MessageBox,
            _("Aufnahme vormerken:\n\n%s\n%s–%s\n\n%s\n\nFortfahren?") % (
                name, _zeit(z["start"]), _zeit(z["ende"]),
                recorder.verbindungs_hinweis(self.api)),
            MessageBox.TYPE_YESNO)
