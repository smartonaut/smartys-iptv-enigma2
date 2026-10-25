# -*- coding: utf-8 -*-
"""Smartys IPTV — Farben, Auflösungs-Erkennung und Skin-Builder.

Die Box unterstützt mehrere OSD-Auflösungen (720p / 1080p / 4K). Statt
fester Pixelwerte skalieren wir alle Layouts proportional zur aktuellen
Skin-Auflösung (Referenz: 1280x720).

Farbschema identisch zum Web-Panel (panel.smartys.tech).

Aufbau eines Screens (von oben nach unten):
  Goldkante am linken Rand | Logo + Titel + Untertitel | Goldlinie
  Karte (Rahmen + Fläche) mit der Liste darin | Statuszeile | Tastenleiste
"""

# Smartys-Branding
BG = "#0b0e14"        # sehr dunkler Hintergrund (Fallback ohne Bild)
PANEL = "#11172a"     # Panel/Karte
CARD = "#141a2a"      # Kartenfläche
CARD_ALT = "#182034"  # Kartenfläche, zweite Ebene
BORDER = "#232c42"    # Rahmen
BORDER_HELL = "#2f3a56"  # Rahmen, betont
TEXT = "#e8eefc"      # Haupttext
MUTED = "#7c8aa8"     # gedämpfter Text
GOLD = "#ffc94d"      # Akzent/Gold
GOLD_DUNKEL = "#8a6d2a"  # Gold, abgedunkelt (Linien)
GREEN = "#6fcf9f"     # ok/aktiv
RED = "#ff9b9b"       # Fehler
BLUE = "#6fa8ff"      # Hinweis
SELECT_BG = "#2a3550" # Auswahl-Hintergrund (Liste)

# Farbtasten der Fernbedienung (für die Tastenleiste unten)
TASTE_ROT = "#d9534f"
TASTE_GRUEN = "#5cb85c"
TASTE_GELB = "#e0b34a"
TASTE_BLAU = "#5b8fd6"
TASTE_OK = "#8a93a8"

# Referenz-Auflösung, auf die alle Layouts ausgelegt sind
REF_W = 1280
REF_H = 720

_cached_size = None


def osd_size():
    """Liefert (breite, hoehe) der aktuellen OSD/Skin-Auflösung."""
    global _cached_size
    if _cached_size is not None:
        return _cached_size
    try:
        from enigma import getDesktop
        d = getDesktop(0)
        w = int(d.size().width())
        h = int(d.size().height())
    except Exception:
        w, h = REF_W, REF_H
    _cached_size = (w, h)
    return _cached_size


def scale(x):
    """Skaliert eine Referenz-Koordinate (1280x720) auf die echte Auflösung."""
    w, h = osd_size()
    return int(round(x * w / REF_W))


def scale_y(y):
    w, h = osd_size()
    return int(round(y * h / REF_H))


def font(size):
    """Schriftgrösse proportional skalieren."""
    w, h = osd_size()
    return int(round(size * w / REF_W))


def _images_dir():
    """Absoluter Pfad zum images-Verzeichnis (neben den Plugin-Modulen)."""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")


def _flaeche(x, y, w, h, farbe, z=1):
    """Einfarbige Fläche (Rahmen, Karte, Kante)."""
    return (
        f'<eLabel position="{scale(x)},{scale_y(y)}" '
        f'size="{scale(w)},{scale_y(h)}" backgroundColor="{farbe}" '
        f'zPosition="{z}" />'
    )


def _text(x, y, w, h, inhalt, groesse, farbe, halign="left", z=2, fett=False):
    """Fester Text (Titel, Hinweise)."""
    return (
        f'<eLabel text="{inhalt}" position="{scale(x)},{scale_y(y)}" '
        f'size="{scale(w)},{scale_y(h)}" font="Regular;{font(groesse)}" '
        f'foregroundColor="{farbe}" backgroundColor="{BG}" '
        f'halign="{halign}" valign="center" transparent="1" zPosition="{z}" />'
    )


def _widget(name, x, y, w, h, groesse, farbe, halign="left", z=2):
    """Vom Code befüllbares Text-Widget."""
    return (
        f'<widget name="{name}" position="{scale(x)},{scale_y(y)}" '
        f'size="{scale(w)},{scale_y(h)}" font="Regular;{font(groesse)}" '
        f'foregroundColor="{farbe}" backgroundColor="{BG}" '
        f'halign="{halign}" valign="center" transparent="1" zPosition="{z}" />'
    )


def tastenleiste(eintraege, y=682):
    """Farbige Tasten-Hinweise: [("ROT", "Aufnahme"), ("GRÜN", "OK"), …].

    Jede Taste bekommt ein farbiges Quadrat mit Kürzel und den Text daneben.
    Erwartet eine Liste aus (farbe, kuerzel, text); farbe ist ein Farbwert
    aus diesem Modul oder None (= neutrale Taste).
    """
    if not eintraege:
        return ""
    teile = []
    x = 48
    for farbe, kuerzel, beschriftung in eintraege:
        farbe = farbe or MUTED
        breite_kuerzel = max(38, 7 * len(kuerzel))
        teile.append(_flaeche(x, y + 1, breite_kuerzel, 22, farbe, z=2))
        teile.append(_text(x, y, breite_kuerzel, 24, kuerzel, 13, "#0b0e14",
                           halign="center", z=3))
        text_w = max(60, 8 * len(beschriftung))
        teile.append(_text(x + breite_kuerzel + 10, y, text_w, 24,
                           beschriftung, 14, TEXT, z=3))
        x += breite_kuerzel + 10 + text_w + 26
    return "".join(teile)


def build_skin(name, logo=True, list_h=None, extra_widgets="", preview=False,
               footer="", epg=False, picon=False, tasten=None, karte=True):
    """Baut einen vollständigen Vollbild-Skin.

    Alle Koordinaten in Referenz-Einheiten (1280x720) und werden skaliert.
    list_h: Hoehe der Liste in Referenz-Einheiten (Standard 400).
    preview: Pig-Fenster (Live-Vorschau) oben rechts einblenden.
    footer: Tasten-Hinweise als Text (alt); tasten: farbige Leiste (neu).
    epg: EPG-Label (Jetzt/Danach) für den markierten Sender.
    picon: Senderlogo-Pixmap (markierter Sender).
    karte: Liste auf eine Karte (Rahmen + Fläche) legen.
    """
    if list_h is None:
        # Vielfaches der Zeilenhoehe (48), damit unten kein Eintrag
        # angeschnitten wird: 9 Zeilen.
        list_h = 432
    w, h = osd_size()

    teile = []

    # Hintergrundbild
    teile.append(
        f'<ePixmap pixmap="{_images_dir()}/background.png" position="0,0" '
        f'size="{w},{h}" alphatest="off" zPosition="-1" />'
    )

    # Goldkante am linken Bildrand — Markenzeichen, gibt dem Bild Halt
    teile.append(_flaeche(0, 0, 5, 720, GOLD, z=2))

    # Kopfbereich
    if logo:
        teile.append(
            f'<ePixmap pixmap="{_images_dir()}/logo.png" position="{scale(46)},{scale_y(34)}" '
            f'size="{scale(64)},{scale_y(64)}" alphatest="blend" transparent="1" zPosition="2" />'
        )
        titel_x = 126
    else:
        titel_x = 48
    teile.append(_text(titel_x, 28, 520, 44, "Smartys IPTV", 30, GOLD))
    teile.append(_widget("header", titel_x, 74, 1100, 30, 20, TEXT))
    teile.append(_widget("subtitle", titel_x, 102, 1100, 22, 14, MUTED))
    # Goldlinie unter dem Kopf
    teile.append(_flaeche(titel_x, 128, 148, 3, GOLD, z=2))
    teile.append(_flaeche(titel_x + 156, 129, 420, 1, BORDER_HELL, z=2))

    # Karte hinter der Liste
    karte_y = 146
    if preview:
        list_x, list_w = 48, 744
        karte_w = list_w + 24
    else:
        list_x, list_w = 48, 1150
        karte_w = list_w + 24

    if karte:
        teile.append(_flaeche(list_x - 12, karte_y, karte_w, list_h + 24, BORDER, z=1))
        teile.append(_flaeche(list_x - 11, karte_y + 1, karte_w - 2, list_h + 22, CARD, z=1))

    # Pig-Vorschau rechts
    if preview:
        teile.append(_flaeche(806, karte_y, 426, 254, BORDER, z=1))
        teile.append(
            f'<widget source="session.VideoPicture" render="Pig" '
            f'position="{scale(807)},{scale_y(karte_y + 1)}" '
            f'size="{scale(424)},{scale_y(252)}" backgroundColor="#000000" '
            f'transparent="1" zPosition="3" />'
        )

    # Liste
    teile.append(
        f'<widget name="list" position="{scale(list_x)},{scale_y(karte_y + 12)}" '
        f'size="{scale(list_w)},{scale_y(list_h)}" render="Listbox" '
        f'itemHeight="{scale_y(48)}" scrollbarMode="showOnDemand" '
        f'foregroundColor="{TEXT}" foregroundColorSelected="{GOLD}" '
        f'backgroundColor="{CARD}" backgroundColorSelected="{SELECT_BG}" '
        f'transparent="1" zPosition="2" />'
    )

    # Picon (Senderlogo des markierten Senders)
    if picon:
        teile.append(
            f'<widget name="picon" position="{scale(48)},{scale_y(596)}" '
            f'size="{scale(84)},{scale_y(84)}" alphatest="blend" '
            f'transparent="1" zPosition="2" />'
        )

    # EPG-Zeile unter der Liste
    if epg:
        epg_x = 146 if picon else 48
        teile.append(_widget("epg", epg_x, 604, 1086, 52, 17, TEXT))

    # Statuszeile
    teile.append(_widget("status", 48, karte_y + list_h + 34, 1184, 26, 15, MUTED, halign="center"))

    # Tastenleiste (neu) oder alter Footer-Text
    if tasten:
        teile.append(tastenleiste(tasten))
    elif footer:
        teile.append(_text(48, 678, 1184, 30, footer, 15, MUTED))

    if extra_widgets:
        teile.append(extra_widgets)

    return (
        f'<screen name="{name}" position="0,0" size="{w},{h}" '
        f'backgroundColor="{BG}" flags="wfNoBorder">'
        + "".join(teile) +
        '</screen>'
    )
