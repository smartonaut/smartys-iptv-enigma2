# -*- coding: utf-8 -*-
"""EPG-Export fuer den zentralen Verteiler.

Eine Box mit Kabel- oder Satellitenanschluss hat das EPG aller empfangbaren
Sender im Speicher. Dieses Modul schreibt es als JSON heraus, damit ein Cron
es zum Server schieben kann und alle anderen Boxen es herunterladen koennen.

Format (bewusst schlicht, damit auch aeltere Boxen es lesen koennen)::

    {"stand": 1792960239,
     "sender": {"das erste": [[start, ende, "Titel"], ...], ...}}

Schluessel sind normalisierte Sendernamen — dieselbe Normalisierung, die
epgbackup fuer den Rytec-Cache benutzt, damit beide Quellen zusammenpassen.
"""

import json
import os
import time

EXPORT_FILE = "/tmp/smartysiptv_epg_export.json"
LOG_FILE = "/tmp/smartysiptv_export.log"


def _log(text):
    try:
        with open(LOG_FILE, "a") as f:
            f.write("%s  %s\n" % (time.strftime("%d.%m %H:%M:%S"), text))
    except Exception:
        pass


# Enigma2 laedt epg.dat erst NACH dem Sessionstart. Ein Export im
# Sekundenbereich nach dem Start findet einen leeren Cache und schreibt
# 0 Sendungen — deshalb wartet der Export, bis der Cache gefuellt ist.
START_VERZOEGERUNG = 90
# Wenn nach dieser Zeit immer noch nichts da ist, wird es noch einmal
# versucht (grosse epg.dat brauchen laenger).
NACHVERSUCHE = (120, 180)


def exportiere_thread(pfad=None):
    """Wie exportiere(), aber verzoegert im Hintergrund.

    Der Export laeuft ueber alle Services und dauert je nach Anzahl der
    Bouquets mehrere Sekunden. Synchron im Sessionstart wuerde er den
    Enigma2-Start aufhalten — die Box wirkt dann beim Einschalten tot.
    """
    import threading

    def lauf():
        time.sleep(START_VERZOEGERUNG)
        for versuch, extra in enumerate((0,) + NACHVERSUCHE):
            if extra:
                time.sleep(extra)
            n = exportiere(pfad)
            _log("Versuch %d: %s Sender" % (versuch + 1, n))
            if n and n > 0:
                return

    t = threading.Thread(target=lauf, daemon=True)
    t.start()
    return t
# So weit in die Zukunft wird exportiert. Das Enigma2-EPG reicht je nach
# Sender unterschiedlich weit; 7 Tage deckt alles ab, was da ist.
TAGE = 7
# Obergrenze, damit die Datei nicht unbegrenzt waechst. Bei 600 Sendern und
# 7 Tagen sind das grob 40.000 Sendungen — 60000 ist reichlich Luft.
MAX_EINTRAEGE = 60000


def _normalize(name):
    """Muss zu epgbackup.normalize() passen."""
    try:
        from .epgbackup import normalize
        return normalize(name)
    except Exception:
        text = (name or "").lower()
        for weg in ("hd", "uhd", "4k", "fhd", "hevc"):
            text = text.replace(weg, " ")
        return " ".join(text.split())


def exportiere(pfad=None):
    """Schreibt das Enigma2-EPG als JSON. Liefert die Zahl der Sender oder -1.

    Laeuft im Enigma2-Prozess; ausserhalb (Testskript per SSH) gibt es kein
    `enigma`-Modul und die Funktion meldet -1 statt zu werfen.
    """
    pfad = pfad or EXPORT_FILE
    _log("Export startet")
    try:
        from enigma import eEPGCache, eServiceReference
        from ServiceReference import ServiceReference as SR
    except Exception as e:
        _log("kein enigma-Modul: %r" % (e,))
        return -1

    jetzt = int(time.time())
    bis = jetzt + TAGE * 86400
    ergebnis = {}
    anzahl = 0

    try:
        from enigma import eServiceCenter

        cache = eEPGCache.getInstance()
        # Ueber die Serviceliste gehen statt ueber eine Sammel-Suche: das ist
        # der dokumentierte Weg (search(("B", ...)) ist nicht verlaesslich)
        # und liefert zu jedem Sender den Anzeigenamen mit.
        handler = eServiceCenter.getInstance()
        liste = handler.list(eServiceReference(
            '1:7:1:0:0:0:0:0:0:0:FROM BOUQUET "bouquets.tv" ORDER BY bouquet'))

        refs = []
        while liste is not None:
            ref = liste.getNext()
            if ref is None or not ref.valid():
                break
            # Bouquet-Eintraege aufloesen
            if ref.flags & 7 == 7 or "FROM BOUQUET" in ref.toString():
                unter = handler.list(ref)
                while unter is not None:
                    r2 = unter.getNext()
                    if r2 is None or not r2.valid():
                        break
                    refs.append(r2)
            else:
                refs.append(ref)

        # Erste Referenzen protokollieren: ohne das ist nicht zu erkennen,
        # ob die Liste Service-Referenzen oder Bouquet-Eintraege enthaelt.
        for r in refs[:3]:
            try:
                _log("ref: %s | flags=%s | name=%s"
                     % (r.toString()[:60], r.flags, SR(r).getServiceName()))
            except Exception as e:
                _log("ref nicht lesbar: %r" % (e,))

        for ref in refs:
            try:
                name = SR(ref).getServiceName()
            except Exception:
                continue
            if not name or name.startswith("= "):
                continue
            key = _normalize(name)
            if not key or key in ergebnis:
                continue
            # Zwei Wege probieren: lookupService() lieferte auf der Box
            # trotz gefuelltem Cache 0 Events. search(("I", ref)) ist der
            # aeltere, weiter verbreitete Aufruf — je nach Image ist nur
            # einer von beiden implementiert.
            events = []
            try:
                events = cache.lookupService(ref) or []
            except Exception as e:
                _log("lookupService-Fehler: %r" % (e,))
            if not events:
                try:
                    erg = cache.search(("I", ref)) or []
                    # search liefert (ref, begin, duration, title, ...)
                    for zeile in erg:
                        try:
                            start = int(zeile[1])
                            ende = start + int(zeile[2])
                            if ende <= jetzt or start >= bis:
                                continue
                            zeilen.append([start, ende, zeile[3] or ""])
                        except Exception:
                            continue
                    if zeilen:
                        _log("  %s: %d via search()" % (name, len(zeilen)))
                        zeilen.sort()
                        ergebnis[key] = zeilen
                        anzahl += len(zeilen)
                        continue
                except Exception as e:
                    _log("search-Fehler: %r" % (e,))
            zeilen = []
            for ev in events:
                try:
                    start = ev.getBeginTime()
                    ende = start + ev.getDuration()
                    if ende <= jetzt or start >= bis:
                        continue
                    zeilen.append([int(start), int(ende),
                                   ev.getEventName() or ""])
                except Exception:
                    continue
            if zeilen:
                zeilen.sort()
                ergebnis[key] = zeilen
                anzahl += len(zeilen)
        _log("%d Services, %d Sendungen" % (len(refs), anzahl))
        # Diagnose: liefert der Cache grundsaetzlich etwas?
        try:
            probe = cache.search(("R", ".")) or []
            _log("Cache-Probe (Titelsuche '.'): %d Treffer" % len(probe))
        except Exception as e:
            _log("Cache-Probe fehlgeschlagen: %r" % (e,))
    except Exception as e:
        _log("FEHLER: %r" % (e,))
        return -1

    if not ergebnis:
        return 0

    for zeilen in ergebnis.values():
        zeilen.sort()

    daten = {"stand": jetzt, "sender": ergebnis}
    try:
        tmp = pfad + ".tmp"
        with open(tmp, "w") as f:
            json.dump(daten, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, pfad)
    except Exception as e:
        print("[SmartysIPTV] EPG-Export schreiben fehlgeschlagen: %r" % (e,))
        return -1
    _log("fertig: %d Sender, %d Sendungen -> %s"
         % (len(ergebnis), anzahl, pfad))
    return len(ergebnis)
