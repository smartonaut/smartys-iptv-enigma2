# Smartys IPTV — Enigma2-Plugin

Eigenes IPTV-Plugin für Enigma2-Boxen (OpenATV, Dreambox/VU+), das die
Smartys-Panel-API (Xtream-Codes-kompatibel) abspielt.

## Download (Alpha)

```
https://player.smartys.tech/download/enigma2
```

Das `.ipk` ist ein Debian-`ar`-Archiv (Architecture: all, da das Python-Plugin
architektur-unabhängig ist) und läuft auf ARM (armv7a/aarch64) und MIPS
(mips32el). SH4 wird nicht gebaut. Installieren mit:

```
opkg install /tmp/enigma2-plugin-extensions-smartysiptv_0.1.0_all.ipk
# danach Enigma2 neu starten (GUI-Neustart)
```

## Struktur

```
plugin/
  plugin.py          Einstiegspunkt (PluginDescriptor, 3 Descriptors)
  api.py             Xtream-API-Client (urllib, kein externes Paket nötig)
  config.py          Persistenz (/etc/enigma2/smartysiptv.json)
  player.py          Wiedergabe (playService → exteplayer3/GStreamer) + Trailer-Download
  mainmenu.py        Hauptmenü
  pairing.py         Pairing-Screen (Player-ID + Passwort)
  channellist.py     Live-TV-Kanalliste
  vodlist.py         Filme (VOD, Cover + Liste)
  voddetail.py       Film-Detailseite (Cover + Beschreibung)
  serieslist.py      Serien (Cover + Liste + Episoden)
  seriesdetail.py    Serien-Detailseite (Cover + Beschreibung)
  picon.py           Senderlogo/Cover-Downloader (Cache + Skalierung)
  streamplayer.py    Vollbild-Player mit EPG-Infobar
  recorder.py        Aufnahme + Timeshift
  epg.py             EPG-Screen
  categories.py      Kategorie-Auswahl (Live/Filme/Serien)
  theme.py           Skin/Template (alle OSD-Modi 720p/1080p/4K)
  screens_base.py    Basis-Screen (ActionMap)
  settings.py        Einstellungsmenü
  images/            logo.png + background.png
CONTROL/control      ipk-Metadaten (Version, Architecture: all, Depends)
build.sh             baut das .ipk (ar-Archiv)
```

## Wichtige technische Fakten (Box, OpenATV 7.6)

- **Kein `__init__.py` im Plugin-Ordner.** Ein zweiter `Plugins()`-Einstiegspunkt
  in `__init__.py` ließ das Plugin stillschweigend verschwinden. `plugin.py`
  braucht zwingend `from Components.PluginComponent import plugins` am Kopf.
- **Cover:** `LoadPixmap` lädt JPEG und PNG (Magic-Bytes). Poster-Widgets brauchen
  **kein** `render="Pixmap"` (blockiert die Anzeige), und Bilder müssen beim
  Download auf die Widget-Größe skaliert werden (`ffmpeg -vf scale`).
- **PIL im Enigma2-Prozess ist defekt** (`failed to map segment`). Bildkonvertierung
  immer via `ffmpeg` und `subprocess.Popen` (Muster: recorder.py).
- **Trailer:** YouTube wird per `yt-dlp` als gemergte MP4 geladen (H.264+AAC
  erzwingen — `bestvideo[height<=480][vcodec^=avc1]+bestaudio[acodec^=mp4a]/best`;
  AV1/Opus kann die Box nicht dekodieren). exteplayer3 spielt die lokale Datei ab.

## Build

```bash
./build.sh
# erzeugt enigma2-plugin-extensions-smartysiptv_0.1.0_all.ipk
```

## Deploy auf die Box (Entwicklung)

```bash
scp plugin/*.py root@<box>:/usr/lib/enigma2/python/Plugins/Extensions/SmartysIPTV/
# dann auf der Box: rm -f <modul>.pyc && sync && init 4; sleep 4; init 3
```
