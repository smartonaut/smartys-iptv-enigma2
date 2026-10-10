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

## [Unreleased]

- exteplayer3 als eigenständiges Binary für ARM/MIPS (Cross-Compile) — bis dahin
  nutzt das Plugin den systemeigenen Player (serviceapp/GStreamer).
