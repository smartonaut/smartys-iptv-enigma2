# Smartys IPTV — Enigma2-Plugin

IPTV-Client für Enigma2-Receiver (VU+, openATV) über Xtream-Codes.

## Features

- **Live-TV** mit EPG (asynchron geladen, keine UI-Freezes)
- **VOD** (Filme) und **Serien** (Staffeln & Episoden)
- **Timeshift / echte Pause** — Aufnahme läuft im Hintergrund bis Sendungsende weiter
- **Timer-Aufnahmen** (anzeigen + abbrechen)
- **Trailer-Wiedergabe** (Hintergrund-Download, kein UI-Freeze)
- **Picons** mit Negativ-Cache

## Installation

1. Aktuelle `.ipk` von [player.smartys.tech](https://player.smartys.tech) herunterladen
2. Auf dem Receiver installieren (USB / `/tmp` + `opkg install`)
3. Plugin öffnen → **Pairing** → Code vom [Panel](https://panel.smartys.tech) eingeben

## Hinweis

Das Plugin enthält **keine Zugangsdaten**. Die Provider-Credentials werden zur
Laufzeit per Pairing vom Panel geladen und lokal auf dem Gerät gespeichert.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
