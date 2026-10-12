# Changelog

Alle nennenswerten Änderungen am Smartys-IPTV-Enigma2-Plugin werden hier
dokumentiert. Format orientiert an [Keep a Changelog](https://keepachangelog.com/de/1.1.0/)
und [Semantic Versioning](https://semver.org/lang/de/).

## [0.1.0] — 2026-10-10 (Alpha)

Erste veröffentlichte Version als `.ipk` (Architecture: all) für Enigma2-Boxen
(OpenATV, OpenPLi, OpenViX, BlackHole, VTi, OpenVision, PurE2 u. a.).

Download: `https://player.smartys.tech/download/enigma2`

### Neu

- **Live-TV** mit Kanalliste, Senderlogos (Picons) und Kategorie-/Unterkategorie-Navigation.
- **Vollbild-Player** mit EPG-Infobar: Sendername, EPG-Titel mit Sendezeit
  (`HH:MM–HH:MM`), Fortschrittsbalken, Uhrzeit, Videoformat/Auflösung und
  Programm-Logo. Auto-Hide nach 6 s, Umschalten per OK.
- **Filme (VOD)**: Cover-Liste (Poster links) + Film-Detailseite mit großem
  Cover, Titel, Metadaten (Jahr · Dauer · IMDb · Genre) und großer Beschreibung.
- **Serien**: Cover-Liste + Serien-Detailseite (Cover, Beschreibung, Metadaten)
  + Episoden-Liste (Staffel/Episode).
- **Trailer**: Wiedergabe von YouTube-Trailern (per `yt-dlp` als gemergte
  H.264/AAC-MP4 geladen, exteplayer3 spielt lokal ab).
- **Aufnahme**: ROT-Taste im Player, Abfrage „endlos vs. bis Sendungsende",
  Timer-Aufnahmen (persistent über Neustart).
- **Timeshift**: Live-TV pausieren (ffmpeg-Puffer auf Festplatte).
- **Umschalt-Schutz**: Bestätigungs-Abfrage bei laufender Aufnahme (Line erlaubt
  meist nur eine Verbindung), abschaltbar.
- **Einstellungsmenü**: Aufnahme-Verzeichnis, Timeshift, Umschalt-Schutz.
- **Pairing**: Player-ID + Passwort (Anbindung an panel.smartys.tech).

### Technik / Fixes

- Plugin-Registrierung auf openATV 7.6 stabilisiert (kein zweiter
  `Plugins()`-Einstiegspunkt in `__init__.py`).
- Cover-Pipeline: Bilder mit korrekter Endung + Skalierung auf Widget-Größe
  (`ffmpeg -vf scale`), `LoadPixmap` lädt JPEG und PNG.
- Skin läuft in allen OSD-Auflösungen (720p/1080p/4K).

---

## [0.3.0] — 2026-10-12 (Beta)

Download: `https://player.smartys.tech/download/enigma2`

### Neu

- **Handy-Passworteingabe**: QR-Code im Entsperren-Screen scannen → Passwort
  übers Handy (gleiches WLAN) eingeben statt Fernbedienung. Lokaler Web-Server
  (Python-Stdlib, Port 8080) läuft nur, solange der Screen offen ist.
- **Pairing löschen (GELB-Taste)**: löscht Line + Pairing + Panel-Eintrag +
  EPG-Cache komplett (mit Warnung). Panel-Route `/api/v1/player/delete`.
- **Entsperren-Fix**: grüne Taste im Passwort-Feld übernimmt das Passwort und
  entsperrt automatisch (kein doppelter Tastendruck mehr).
- QR-Code im Pairing-Screen skaliert korrekt auf alle OSD-Auflösungen.

### Technik

- Generische QR-Route `/qrdata` im Panel (die Box hat kein QR-Modul).
- `unlock_web.py`: lokaler Web-Server (nur `http.server` + `threading`).

---

## [Unreleased]

- exteplayer3 als eigenständiges Binary für ARM/MIPS (Cross-Compile) — bis dahin
  nutzt das Plugin den systemeigenen Player (serviceapp/GStreamer).
