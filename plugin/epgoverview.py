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
        (theme.TASTE_GRUEN, "GRÜN", "Tag vor"),
        (theme.TASTE_GELB, "GELB", "Tag zurück"),
        (theme.TASTE_BLAU, "BLAU", "Wiederholen"),
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

        # Tagesversatz: 0 = heute, 1 = morgen … Der EPG-Cache reicht
        # mehrere Tage voraus, deshalb laesst sich hier durchblaettern.
        self._tag = 0
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
                "green": self._tag_vor,
                "yellow": self._tag_zurueck,
                "blue": self._wiederholen,
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

    def _fenster(self):
        """Zeitfenster des angezeigten Tages als (von, bis) in Unix-Zeit."""
        heute = time.localtime()
        mitternacht = time.mktime((
            heute.tm_year, heute.tm_mon, heute.tm_mday, 0, 0, 0,
            heute.tm_wday, heute.tm_yday, -1))
        ab = int(mitternacht) + self._tag * 86400
        # Ueber den Tag hinaus: was nach 23:59 laeuft, soll noch sichtbar
        # sein — sonst fehlen Sendungen, die ueber Mitternacht gehen.
        return ab, ab + 86400 + 4 * 3600

    def _tag_vor(self):
        """GRÜN: einen Tag weiter — hoechstens bis zum Ende des EPG.

        Wie weit das reicht, haengt von der Quelle ab (der Rytec-Cache
        liefert etwa eine Woche). Ueber das Ende hinaus waere die Liste
        leer, ohne dass klar ist warum.
        """
        grenze = self._letzter_tag()
        if self._tag >= grenze:
            self["status"].setText(
                _("Weiter reicht das EPG nicht (%s)") % self._datum_text())
            return
        self._tag += 1
        self._load()

    def _letzter_tag(self):
        """Index des letzten Tages, fuer den es noch Daten gibt."""
        try:
            from . import epgbackup
            _ab, ende = epgbackup.zeitraum()
            if not ende:
                return self._tag
            heute = time.localtime()
            mitternacht = time.mktime((
                heute.tm_year, heute.tm_mon, heute.tm_mday, 0, 0, 0,
                heute.tm_wday, heute.tm_yday, -1))
            return max(0, int((ende - mitternacht) // 86400))
        except Exception:
            return self._tag

    def _tag_zurueck(self):
        """GELB: einen Tag zurueck (nicht vor heute)."""
        if self._tag > 0:
            self._tag -= 1
        self._load()

    def _datum_text(self):
        if self._tag == 0:
            return "Heute"
        if self._tag == 1:
            return "Morgen"
        ab, _bis = self._fenster()
        return time.strftime("%A, %d.%m.", time.localtime(ab))

    def _aus_cache(self, sender):
        """Sendungen eines Senders aus dem EPG-Cache (ohne Netzwerk).

        Der Cache wird beim Plugin-Start gefuellt (epgbackup) und deckt die
        gaengigen Sender ab. Was dort steht, ist sofort da — das Netz braucht
        es nur fuer Sender, die der Cache nicht kennt.
        """
        try:
            from . import epgbackup
            epgbackup.ensure_loaded()
            ab, bis = self._fenster()
            treffer = epgbackup.alle_sendungen(sender.get("name", ""),
                                              ab_ts=ab,
                                              stunden=(bis - ab) / 3600.0)
        except Exception:
            return []
        zeilen = []
        for start, ende, titel in treffer:
            zeilen.append({
                "sender": sender.get("name", "?"),
                "stream_id": sender.get("stream_id"),
                "titel": titel,
                "start": int(start),
                "ende": int(ende),
            })
        return zeilen

    def _load(self):
        """Erst den Cache auswerten, dann nur den Rest live nachladen."""
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

        # Zuerst der Cache — deckt die gaengigen Sender sofort ab.
        offen = []
        for s in auswahl:
            zeilen = self._aus_cache(s)
            if zeilen:
                self._ergebnisse[s.get("stream_id")] = zeilen
                self._fertig += 1
            else:
                offen.append(s)
        self._gesamt = len(auswahl)

        if offen:
            self["status"].setText(
                _("%d Sender aus dem Cache, lade %d nach …")
                % (self._fertig, len(offen)))
            # Nur der Rest geht ins Netz — einzeln, weil der Server bei
            # parallelen Anfragen in Timeouts laeuft.
            threading.Thread(target=self._hole_alle, args=(offen,),
                             daemon=True).start()
        else:
            self["status"].setText(
                _("%d Sender aus dem Cache") % self._gesamt)

        # Liste sofort zeigen, dann weiter nachziehen
        self._nachziehen()

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

        # Auf den gewaehlten Tag begrenzen
        ab, bis = self._fenster()
        alle = [z for z in alle if z["ende"] > ab and z["start"] < bis]
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
                _("%s · %d Sendungen — GRÜN/GELB blättert Tage")
                % (self._datum_text(), len(eintraege)))

    def _timer_setzen(self):
        """OK: markierte Sendung als Timer-Aufnahme vormerken."""
        self._vormerken(None)

    def _wiederholen(self):
        """BLAU: Sendung als wiederkehrende Aufnahme vormerken.

        Eine Serie laeuft meist woechchentlich zur gleichen Zeit — dann
        reicht ein Timer, der sich selbst fortsetzt.
        """
        self._vormerken("woechentlich")

    def _vormerken(self, wieder):
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
        zusatz = ""
        if wieder == "woechentlich":
            zusatz = _("\n\nWiederholt sich jede Woche am %s um %s.") % (
                time.strftime("%A", time.localtime(z["start"])),
                _zeit(z["start"]))

        def _bestaetigt(ja):
            if not ja:
                return
            recorder.get_scheduler().schedule(url, name, z["start"], z["ende"],
                                              wieder=wieder)
            self.session.open(
                MessageBox,
                _("Timer-Aufnahme geplant:\n%s\n%s–%s%s") % (
                    name, _zeit(z["start"]), _zeit(z["ende"]),
                    "\n(woechentlich)" if wieder else ""),
                MessageBox.TYPE_INFO, timeout=6)

        self.session.openWithCallback(
            _bestaetigt, MessageBox,
            _("Aufnahme vormerken:\n\n%s\n%s–%s%s\n\n%s\n\nFortfahren?") % (
                name, _zeit(z["start"]), _zeit(z["ende"]), zusatz,
                recorder.verbindungs_hinweis(self.api)),
            MessageBox.TYPE_YESNO)
