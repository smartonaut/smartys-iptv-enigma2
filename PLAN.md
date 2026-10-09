# Smartys IPTV — Enigma2-Plugin (OpenATV, Dreambox/VU+)

## Ziel
Eigenes Enigma2-Plugin, das die Smartys-IPTV-Panel-API (Xtream-Codes-kompatibel)
auf Sat-Receivern mit **OpenATV** abspielt. Wiederverwendung der API-Logik des
Desktop-Players, aber komplett neue Plattform.

## Ziel-Architekturen (Nutzer-Vorgabe)
- **ARM** (`armv7a` 32-bit + `aarch64` 64-bit)  → bauen
- **MIPS** (`mips32el`)                        → bauen
- **SH4**                                      → weglassen

## Technische Basis (recherchiert, 2026-10-08)

### Plattform
- Enigma2-Plugins sind **Python 3** (kein Kotlin/Compose wie Desktop).
- UI über Enigma2-`Screens`/Skins, nicht Compose.
- Paketformat: **`.ipk`** (opkg); neueste Dreambox-Images (OE2.5) nutzen `.deb`.

### Wiedergabe-Engines (automatisch durchprobieren)
1. **exteplayer3** (ffmpeg-basiert) — am robustesten für Xtream-Streams.
   **Getrennte Binaries pro Architektur** (exteplayer3-mipsel / -arm).
2. **GStreamer** — Standard, oft zickig bei Redirects/403.
3. **serviceapp** — Umschalt-Player.

### Xtream-API (bereits vorhanden aus Desktop-Player)
- `player_api.php?username=..&password=..` + `action=get_live_streams|get_vod_streams|get_series`
- Stream-URL: `http://<server>/live/<user>/<pass>/<stream_id>.ts`
- Backend: `panel.smartys.tech` (Pairing wie Desktop).

### Referenz-Implementierungen (Open Source)
- **XKlass** / **XStreamity** (biko-73) — Xtream-Codes-Plugin, architektur-agnostisch.
- **IPTV-BOX by Mike68** — leichtgewichtiges OpenATV-Plugin, probiert
  GStreamer → exteplayer3 → serviceapp automatisch durch.
- **e2iplayer** — großes Streaming-Plugin (Referenz für Player-Anbindung).

## Umsetzungs-Schritte

### Phase 1 — Grundgerüst (Python-Plugin)
1. Neues Repo `SmartysIPTV-Enigma2` anlegen.
2. Plugin-Struktur:
   - `plugin/` (Python-Paket) mit `plugin.py` (Einstieg, `Plugins.Plugin`),
     `__init__.py`, Screens für Live/VOD/Serien/Einstellungen.
   - `CONTROL/control` (ipk-Metadaten: Arch, Depends, Version).
3. Pairing-Screen (Player-ID + Passwort, wie Desktop) → Token gegen panel.smartys.tech.
4. Kanal-/VOD-/Serienliste aus der Xtream-API laden (Retrofit-Logik nach Python portieren).

### Phase 2 — Wiedergabe
5. exteplayer3-Anbindung (Binary je Arch) + Fallback GStreamer.
6. Live-TV-Stream-URL aufrufen, EPG (XMLTV) einbinden.
7. VOD/Serien-Wiedergabe (Resume-Position optional später).

### Phase 3 — Build/Paketierung
8. Cross-Compile exteplayer3 für `armv7a` + `aarch64` + `mips32el`
   (OpenATV SDK / oe-alliance Toolchain je Arch).
9. Drei `.ipk` bauen: `..._armv7a.ipk`, `..._aarch64.ipk`, `..._mips32el.ipk`.
10. Install-Test auf echter Box (welche Box verfügbar? → klären).

## Offene Fragen (vor Start klären)
- Welche **konkrete Test-Box** liegt vor (Modell + CPU-Arch)? → entscheidet
  Build-Priorität.
- Soll der Player **dieselbe Panel-API** (panel.smartys.tech) nutzen wie Desktop?
- exteplayer3 selbst kompilieren oder vorkompilierte Binaries aus dem
  oe-alliance-Feed nehmen?

## Status
- [ ] Phase 1 (Grundgerüst)
- [ ] Phase 2 (Wiedergabe)
- [ ] Phase 3 (Build + Box-Test)
- Recherche + Architektur-Fakten im Brain gesichert (`iptv/enigma2_architektur`,
  `iptv/enigma2_target`).
