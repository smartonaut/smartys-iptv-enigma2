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

## [0.4.0] — 2026-10-25 (Beta)

Download: `https://player.smartys.tech/download/enigma2`

### Neu

- **Sortierung der Senderliste (BLAU)**: `original` → `az` → `za` →
  `fav_first` im Kreis, gespeichert als `sort_mode`. Der Cursor bleibt auf
  demselben Sender stehen, Favoriten-Sternchen werden beim Sortieren
  ignoriert.
- **Gruppen ausblenden (GELB)** in der Kategorienliste, BLAU holt alle
  zurück. Gilt **getrennt für Live-TV, Filme und Serien** — ausgeblendete
  Gruppen hängen als `- Name` am Listenende, damit man sie wiederfindet.
- **Aufnahmeverzeichnis frei wählbar** (Einstellungen): Ordner-Browser mit
  Schreibtest und Anzeige des freien Platzes. BLAU legt einen neuen Ordner an.
- **EPG-Übersicht aller Sender** (Timer-Aufnahmen → GELB): flache Liste
  `Zeit · Sender · Sendung`, OK merkt vor, BLAU merkt **wöchentlich** vor,
  GRÜN/GELB blättert durch die Tage. Die Daten kommen aus dem EPG-Cache, ohne
  Netzabruf — so ist die Liste sofort da.
- **Wiederkehrende Aufnahmen**: täglich, werktags (Mo–Fr) oder wöchentlich;
  der Scheduler legt nach dem Lauf selbst den nächsten Termin an.

### Behoben

- **Filme blieben schwarz**: Die Wiedergabe forderte hart `.mp4` an, auch
  wenn der Film als MKV vorliegt. Der Server antwortet dann mit HTTP 551.
  Die echte `container_extension` aus der API wird jetzt durchgereicht.
- **Timer-Aufnahmen liefen nur bei geöffnetem Plugin**: Der Scheduler hängt
  jetzt an Autostart und Sessionstart. Verifiziert: Box neu gestartet,
  Plugin nie geöffnet, Aufnahme lief (40 MB). Läuft damit auch, während
  normales Sat-TV über den Tuner läuft.
- **Ausblenden wirkte in allen Bereichen gleichzeitig**: Ein gemeinsamer
  Config-Schlüssel führte dazu, dass 99 ausgeblendete Live-Gruppen auch die
  Film- und Serienliste leerten. Jetzt `hidden_categories_live|vod|series`
  mit Migration des Altbestands.

### Warnung vor Aufnahmen

Vor jeder Aufnahme erscheint ein Hinweis zur Verbindungszahl der Line
(`max_connections` aus der API). Bei einer Verbindung: „Während der Aufnahme
belegt sie diese — du kannst in dieser Zeit keinen anderen IPTV-Sender
schauen." Bei mehreren Verbindungen passt sich der Text an. Der Wert wird
einmal geholt und behalten, weil der Server wiederholte Abfragen drosselt.

### EPG-Cache

Der Rytec-Cache umfasst jetzt **549 Sender mit rund 127.000 Sendungen**
(sechs Länderquellen: DE, AT, CH, NL, UK, 6 MB, etwa 7 Tage voraus). Er wird
beim Plugin-Start im Hintergrund aufgebaut. Der Namensabgleich arbeitet nur
an Wortgrenzen — lieber kein Treffer als eine falsche Sendung.

### Technik

- Diagnose-Log `/tmp/smartysiptv_timer.log` für den Aufnahme-Scheduler.
  Bisher wurden Fehler dort still geschluckt, ein Fehlschlag war unsichtbar.
- Neue Module: `epgoverview.py`, `recdir.py`.

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
