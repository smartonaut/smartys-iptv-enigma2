# -*- coding: utf-8 -*-
"""Freies EPG als Fallback (Rytec) fuer Kanaele ohne Provider-EPG.

Backup-Kette im Player:
  1. Provider: short_epg (Xtream-API)
  2. Provider: xmltv.php
  3. Rytec (epg.vuplus-community.net) -- diese Datei

Download + Parse laufen im Hintergrund-Thread, der Index wird als JSON
gecacht (TTL 24h). lookup() liefert (now_event, next_event) oder None.
"""
import json
import lzma
import os
import re
import threading
import time
import urllib.request

try:
    import xml.etree.ElementTree as ET
except Exception:  # pragma: no cover
    ET = None

# Rytec-Quellen nach Land. Geladen wird nur, was gebraucht wird: die
# Laenderliste kommt aus den SICHTBAREN Gruppen (ausgeblendete Gruppen
# liefern kein EPG, ihre Sender werden nie angezeigt). Ohne Filter zog
# eine deutsche Box auch UK/NL/CH mit — mehrere MB fuer nichts.
# Belgien gibt es bei Rytec nicht (rytecBE_Basic -> HTTP 404); flaemische
# Sender stecken teilweise in der NL-Liste.
EPG_SOURCES = {
    "DE": ("http://epg.vuplus-community.net/rytecDE_Basic.xz",
           "http://epg.vuplus-community.net/rytecDE_Common.xz"),
    "AT": ("http://epg.vuplus-community.net/rytecAT_Basic.xz",),
    "CH": ("http://epg.vuplus-community.net/rytecCH_Basic.xz",),
    "NL": ("http://epg.vuplus-community.net/rytecNL_Basic.xz",),
    "BE": ("http://epg.vuplus-community.net/rytecNL_Basic.xz",),
    "UK": ("http://epg.vuplus-community.net/rytecUK_Basic.xz",),
}

# Gesetzt vom Plugin, sobald die sichtbaren Sender bekannt sind (Ländernamen
# aus den Sendernamen, z. B. "DE - Das Erste HD" -> DE). None = noch nicht
# bekannt, dann werden alle Quellen geladen.
_LAENDER = {"aktiv": None}


def laender_aus_sendern(namen):
    """Laenderkennungen aus Sendernamen ziehen ("DE - Das Erste HD" -> DE).

    Die IPTV-Listen praefixen fast jeden Sender mit dem Land. Was kein
    bekanntes Praefix hat, zaehlt nicht — dann wird fuer dieses Land
    nichts geladen, was bei reinen DE-Listen richtig ist.
    """
    gefunden = set()
    for name in namen or ():
        text = (name or "").strip().upper()
        if len(text) >= 3 and text[2] in "-| ":
            code = text[:2]
            if code in EPG_SOURCES:
                gefunden.add(code)
    return gefunden


def setze_laender(laender):
    """Merkt sich, fuer welche Laender EPG gebraucht wird.

    Wird beim Kategorien-Laden aufgerufen, sobald die sichtbaren Sender
    bekannt sind. Ein leerer Treffer laesst die Einstellung unveraendert —
    sonst wuerde ein einzelner fehlgeschlagener Abruf das EPG abschalten.
    """
    laender = [str(l).upper() for l in (laender or []) if l]
    laender = [l for l in laender if l in EPG_SOURCES]
    if laender:
        _LAENDER["aktiv"] = tuple(sorted(set(laender)))


CACHE_FILE = "/etc/enigma2/smartysiptv_epg.json"
CACHE_TTL = 24 * 3600
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 Chrome/145.0.0.0 Safari/537.36")

_QUALITY = ("hd", "fhd", "sd", "uhd", "4k", "8k", "fullhd", "h265", "qhd",
            "hevc", "fhd+")

_index = {}        # norm_name -> [[start_ts, stop_ts, title], ...]
_ready = False
_loading = False
_lock = threading.Lock()


def normalize(name):
    """Normalisiert einen Kanalnamen fuer das Matching.

    'DE - DAS ERSTE HD' -> 'das erste'
    'Das Erste HD'      -> 'das erste'
    """
    if not name:
        return ""
    s = name.lower()
    for a, b in (("ä", "a"), ("ö", "o"), ("ü", "u"), ("ß", "ss")):
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = s.split()
    # Laendercode-Praefix am Anfang entfernen (de, at, ch, be, nl, ...)
    if len(tokens) >= 2 and len(tokens[0]) in (2, 3) and tokens[0].isalpha():
        tokens = tokens[1:]
    # Qualitaets-Suffixe am Ende entfernen
    while tokens and tokens[-1] in _QUALITY:
        tokens.pop()
    return " ".join(tokens)


def _parse_ts(text):
    """'20261011051500 +0200' -> epoch-Sekunden."""
    try:
        t = time.strptime(text, "%Y%m%d%H%M%S %z")
        return int(time.mktime(t)) - time.timezone
    except Exception:
        return None


def _parse_xz_stream(stream):
    """Parst eine geoeffnete .xz-XMLTV-Datei in den Index."""
    if ET is None:
        return {}
    result = {}
    channels = {}
    for _event, elem in ET.iterparse(stream, events=("end",)):
        tag = elem.tag
        if tag == "channel":
            dn = elem.find("display-name")
            if dn is not None and dn.text:
                channels[elem.get("id")] = dn.text
        elif tag == "programme":
            ch = elem.get("channel")
            start = _parse_ts(elem.get("start") or "")
            stop = _parse_ts(elem.get("stop") or "")
            ti = elem.find("title")
            title = ti.text if ti is not None and ti.text else ""
            if ch in channels and start is not None and stop is not None:
                key = normalize(channels[ch])
                result.setdefault(key, []).append((start, stop, title))
            # Text NACH Zugriff loeschen, dann Element freigeben.
            elem.clear()
    return result


def _quellen():
    """URLs der Quellen, die fuer die aktiven Laender gebraucht werden."""
    laender = _LAENDER["aktiv"]
    if not laender:
        laender = tuple(EPG_SOURCES.keys())
    urls = []
    for land in laender:
        for url in EPG_SOURCES.get(land, ()):
            if url not in urls:      # NL deckt auch BE ab — nicht doppelt laden
                urls.append(url)
    return urls


def _download_and_parse(path):
    """Laedt die benoetigten Quellen (Streaming-Dekompression), baut den Index."""
    merged = {}
    tmp = path + ".tmp"
    for url in _quellen():
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            with open(tmp, "wb") as f:
                f.write(data)
            with lzma.open(tmp, "rb") as stream:
                neu = _parse_xz_stream(stream)
            for name, zeilen in neu.items():
                alt_v = merged.get(name)
                if alt_v is None or len(zeilen) > len(alt_v):
                    merged[name] = zeilen
        except Exception as e:
            print("[SmartysIPTV] EPG-Quelle fehlgeschlagen %s: %r" % (url, e))
        finally:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
    return merged


def ensure_loaded():
    """Startet den Lade-Thread, falls noetig. Blockiert nicht."""
    global _loading
    with _lock:
        if _ready or _loading:
            return
        _loading = True
    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def _worker():
    global _ready, _loading, _index
    try:
        # Cache zuerst (schnell, kompakt).
        if _load_cache():
            with _lock:
                _ready = True
                _loading = False
            return
        merged = _download_and_parse(CACHE_FILE)
        if merged:
            with _lock:
                _index = merged
                _ready = True
                _loading = False
            try:
                with open(CACHE_FILE + ".tmp", "w") as f:
                    json.dump(merged, f)
                os.replace(CACHE_FILE + ".tmp", CACHE_FILE)
            except Exception as e:
                print("[SmartysIPTV] EPG-Cache schreiben fehlgeschlagen: %r" % e)
            return
    except Exception as e:
        print("[SmartysIPTV] EPG-Backup-Fehler: %r" % e)
    with _lock:
        _loading = False


def _load_cache():
    global _index
    try:
        st = os.stat(CACHE_FILE)
        if time.time() - st.st_mtime > CACHE_TTL:
            return False
        with open(CACHE_FILE) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
        with _lock:
            _index = data
        return True
    except Exception:
        return False


def ready():
    return _ready


# --------------------------------------------------------------------------
# Enigma2-eigenes EPG (DVB vom Tuner)
#
# Die Boxen haengen an Kabel oder Satellit und haben das EPG der empfangbaren
# Sender direkt im Speicher (`eEPGCache`). Das ist die bessere Quelle fuer
# alles, was ueber den Tuner laeuft: aktuell, vollstaendig, ohne Download —
# und es deckt genau die Sender ab, die im Rytec-Bestand fehlen (SAT.1,
# ORF, SRF, RTLZWEI ...).
#
# IPTV-Sender haben keine DVB-ServiceReference, deshalb wird ueber den NAMEN
# gematcht: der Anzeigename des Tuner-Senders gegen den IPTV-Namen.
# --------------------------------------------------------------------------

_ENIGMA_CACHE = {"gefragt": False, "namen": {}}


def _enigma_namen():
    """Alle Sender mit EPG aus dem Enigma2-Cache: {normalisiert: (ref, name)}.

    Wird einmal aufgebaut und behalten. Ohne Enigma2-Kontext (Testskript per
    SSH) wirft der Import — dann bleibt das Dict leer und alles laeuft wie
    bisher ueber Rytec.
    """
    if _ENIGMA_CACHE["gefragt"]:
        return _ENIGMA_CACHE["namen"]
    _ENIGMA_CACHE["gefragt"] = True
    namen = {}
    try:
        from enigma import eEPGCache, eServiceReference
        from ServiceReference import ServiceReference as SR

        cache = eEPGCache.getInstance()
        # Alle Service-Referenzen, die der EPG-Cache kennt
        refs = cache.search(("R", "I")) or []
        for ref in refs:
            try:
                text = str(ref) if not isinstance(ref, (list, tuple)) else str(ref[0])
                if not text:
                    continue
                r = eServiceReference(text)
                name = SR(r).getServiceName()
                if not name:
                    continue
                namen[normalize(name)] = text
            except Exception:
                continue
        print("[SmartysIPTV] Enigma2-EPG: %d Sender" % len(namen))
    except Exception as e:
        print("[SmartysIPTV] Enigma2-EPG nicht verfuegbar: %r" % (e,))
    _ENIGMA_CACHE["namen"] = namen
    return namen


def enigma_epg(channel_name, ab_ts=None, stunden=24):
    """Sendungen eines Senders aus dem Enigma2-EPG (Tuner).

    Liefert dieselbe Struktur wie alle_sendungen(): [(start, ende, titel)].
    Leer, wenn der Sender nicht ueber den Tuner empfangbar ist.
    """
    try:
        from enigma import eEPGCache, eServiceReference
        from ServiceReference import ServiceReference as SR
    except Exception:
        return []

    eintraege = _enigma_namen()
    if not eintraege:
        return []
    key = normalize(channel_name)
    if not key:
        return []

    # Gleiche Stufen wie _finde(), nur auf der Enigma2-Namensliste
    treffer = eintraege.get(key)
    if not treffer:
        kompakt = key.replace(" ", "")
        for k, v in eintraege.items():
            if k.replace(" ", "") == kompakt:
                treffer = v
                break
    if not treffer:
        for k, v in eintraege.items():
            if len(k) >= 5 and (key.endswith(" " + k) or k.endswith(" " + key)):
                treffer = v
                break
    if not treffer:
        return []

    if ab_ts is None:
        ab_ts = time.time()
    bis = ab_ts + stunden * 3600
    ergebnis = []
    try:
        cache = eEPGCache.getInstance()
        events = cache.lookupService(eServiceReference(treffer)) or []
        for ev in events:
            start = ev.getBeginTime()
            ende = ev.getDuration() + start
            if ende <= ab_ts or start >= bis:
                continue
            titel = ev.getEventName() or ""
            ergebnis.append((start, ende, titel))
    except Exception:
        return []
    return ergebnis


def _finde(channel_name):
    """Passende Eintraege im Index finden — in drei Stufen.

    Die Namen passen selten zeichengenau: "DE - Das Erste HD" wird zu
    "das erste", im Cache steht aber nur "erste". "DE - SAT.1 HD" wird zu
    "sat 1", im Cache "sat1". Stufe 1 exakt, Stufe 2 ohne Leerzeichen,
    Stufe 3 Teilstring (nur ab 4 Zeichen, sonst passt "rtl" auf "rtlup").
    """
    key = normalize(channel_name)
    if not key:
        return None
    if key in _index:
        return _index[key]
    kompakt = key.replace(" ", "")
    for k, v in _index.items():
        if k.replace(" ", "") == kompakt:
            return v
    # Stufe 3 nur an Wortgrenzen: "das erste" passt auf "erste", aber
    # "rtlzwei" darf NICHT auf "rtl" passen und "een" nicht irgendwo
    # mitten in einem fremden Namen. Ein falscher Treffer ist schlimmer
    # als keiner — der Nutzer merkt es erst bei der Aufnahme.
    for k, v in _index.items():
        if len(k) < 5:
            continue
        if key.endswith(" " + k) or k.endswith(" " + key):
            return v
    return None


def zeitraum():
    """Erster und letzter Zeitstempel im Cache (oder (None, None))."""
    if not _ready or not _index:
        return None, None
    min_ts, max_ts = None, None
    for zeilen in _index.values():
        for s, e, _titel in zeilen:
            if min_ts is None or s < min_ts:
                min_ts = s
            if max_ts is None or e > max_ts:
                max_ts = e
    return min_ts, max_ts


def alle_sendungen(channel_name, ab_ts=None, stunden=12):
    """Alle bevorstehenden Sendungen eines Senders aus dem Cache.

    Fuer die EPG-Uebersicht: lookup() liefert nur jetzt/danach, hier kommt
    das ganze Zeitfenster. Ohne Netzwerk, weil der Cache beim Start gefuellt
    wird — die Uebersicht ist damit sofort da.
    """
    if not _ready or not channel_name:
        return []
    events = _finde(channel_name)
    if not events:
        return []
    if ab_ts is None:
        ab_ts = time.time()
    bis = ab_ts + stunden * 3600
    return [(s, e, titel) for s, e, titel in events
            if e > ab_ts and s < bis]


def sende_namen():
    """Alle Sender, fuer die der Cache Sendungen kennt (normalisiert)."""
    if not _ready:
        return []
    return sorted(_index.keys())


def lookup(channel_name):
    """Liefert (now_event, next_event) fuer den Kanal oder (None, None).

    Event = (start_ts, stop_ts, title).
    """
    if not _ready or not channel_name:
        return None, None
    events = _finde(channel_name)
    if not events:
        return None, None
    now = time.time()
    now_ev = None
    next_ev = None
    for start, stop, title in events:
        if start <= now < stop:
            now_ev = (start, stop, title)
        elif start > now:
            if next_ev is None or start < next_ev[0]:
                next_ev = (start, stop, title)
    return now_ev, next_ev
