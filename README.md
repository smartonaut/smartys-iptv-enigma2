# Smartys IPTV — Enigma2-Plugin

Eigenes IPTV-Plugin für Enigma2-Boxen (OpenATV, Dreambox/VU+), das die
Smartys-Panel-API (Xtream-Codes-kompatibel) abspielt.

## Struktur

```
plugin/
  __init__.py       Einstiegspunkt (PluginDescriptor)
  api.py            Xtream-API-Client (urllib, kein externes Paket nötig)
  config.py         Persistenz (/etc/enigma2/smartysiptv.json)
  player.py         Wiedergabe (exteplayer3 → GStreamer → serviceapp)
  mainmenu.py       Hauptmenü
  pairing.py        Pairing-Screen (Player-ID + Passwort)
  channellist.py    Live-TV-Kanalliste
  vodlist.py        Filme (VOD)
  serieslist.py     Serien (Staffeln → Episoden)
CONTROL/control     ipk-Metadaten
```

## Ziel-Architekturen

- **ARM** (`armv7a` + `aarch64`)  → bauen
- **MIPS** (`mips32el`)           → bauen
- **SH4**                        → weglassen

Das Python-Plugin selbst ist architektur-unabhängig (`Architecture: all`).
Die Architektur-Abhängigkeit steckt im **exteplayer3**-Binary (Phase 3).

## Wiedergabe-Engines

`player.py` probiert automatisch: exteplayer3 → GStreamer → serviceapp.
Der User-Agent ist gesetzt (viele Xtream-Server blocken sonst mit 403).

## Build (Phase 3, noch offen)

Drei `.ipk` bauen (armv7a / aarch64 / mips32el), jeweils mit dem passenden
exteplayer3-Binary. Cross-Compile via OpenATV-SDK / oe-alliance-Toolchain.
