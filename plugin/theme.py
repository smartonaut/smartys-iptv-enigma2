# -*- coding: utf-8 -*-
"""Smartys IPTV — Farben, Auflösungs-Erkennung und Skin-Builder.

Die Box unterstützt mehrere OSD-Auflösungen (720p / 1080p / 4K). Statt
fester Pixelwerte skalieren wir alle Layouts proportional zur aktuellen
Skin-Auflösung (Referenz: 1280x720).

Farbschema identisch zum Web-Panel (panel.smartys.tech).
"""

# Smartys-Branding
BG = "#0b0e14"        # sehr dunkler Hintergrund
PANEL = "#11172a"     # Panel/Karte
CARD = "#141a2a"      # Listenelement
BORDER = "#232c42"    # Rahmen
TEXT = "#e8eefc"      # Haupttext
MUTED = "#6b7a99"     # gedämpfter Text
GOLD = "#ffc94d"      # Akzent/Gold
GREEN = "#6fcf9f"     # ok/aktiv
RED = "#ff9b9b"       # Fehler
SELECT_BG = "#2a3550" # Auswahl-Hintergrund (Liste)

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


def build_skin(name, logo=True, list_h=None, extra_widgets="", preview=False,
               footer="", epg=False):
    """Baut einen vollständigen Vollbild-Skin mit Logo, Header, Liste, Status.

    Alle Koordinaten in Referenz-Einheiten (1280x720) und werden skaliert.
    list_h: Hoehe der Liste in Referenz-Einheiten (Standard 400).
    preview: Pig-Fenster (Live-Vorschau) oben rechts einblenden.
    footer: Tasten-Hinweise unten (z.B. "ROT = Aufnahme").
    epg: EPG-Label (Jetzt/Danach) für den markierten Sender.
    """
    if list_h is None:
        list_h = 400
    w, h = osd_size()
    logo_widget = ""
    if logo:
        logo_widget = (
            '<ePixmap pixmap="%s/images/logo.png" position="%d,%d" '
            'size="%d,%d" alphatest="blend" transparent="1" zPosition="2" />'
            % (_images_dir(), scale(48), scale_y(42), scale(72), scale_y(72))
        )
    header_x = scale(150) if logo else scale(48)

    # Gold-Akzentlinie über der Liste (unter Subtitle)
    accent = (
        '<eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" '
        'zPosition="2" />'
        % (scale(48), scale_y(158), scale(200), scale_y(3), GOLD)
    )

    # Bei Vorschau: Liste links schmaler, Pig rechts
    if preview:
        list_x = scale(48)
        list_w = scale(760)
        pig_widget = (
            '<widget source="session.VideoPicture" render="Pig" '
            'position="%d,%d" size="%d,%d" backgroundColor="#000000" '
            'transparent="1" zPosition="3" />'
            % (scale(824), scale_y(162), scale(408), scale_y(230))
        )
    else:
        list_x = scale(48)
        list_w = scale(1184)
        pig_widget = ""

    # Footer mit Tasten-Hinweisen
    footer_widget = ""
    if footer:
        footer_widget = (
            '<eLabel text="%s" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" backgroundColor="%s" '
            'halign="left" valign="center" transparent="1" zPosition="2" />'
            % (footer, scale(48), scale_y(678), scale(1184), scale_y(30),
               font(15), MUTED, BG)
        )

    # EPG-Label (Jetzt/Danach) unter der Liste
    epg_widget = ""
    if epg:
        epg_widget = (
            '<widget name="epg" position="%d,%d" size="%d,%d" '
            'font="Regular;%d" foregroundColor="%s" backgroundColor="%s" '
            'halign="left" valign="center" transparent="1" zPosition="2" />'
            % (scale(48), scale_y(610), scale(1184), scale_y(52), font(18),
               TEXT, BG)
        )

    item_h = scale(38)  # Abstand zwischen Listeneinträgen

    return ("""
        <screen name="%s" position="0,0" size="%d,%d" backgroundColor="%s" flags="wfNoBorder">
            <ePixmap pixmap="%s/images/background.png" position="0,0" size="%d,%d" alphatest="off" zPosition="-1" />
            %s
            <eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" backgroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            <widget name="header" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            <widget name="subtitle" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            %s
            %s
            <widget name="list" position="%d,%d" size="%d,%d" itemHeight="%d" scrollbarMode="showOnDemand" foregroundColor="%s" foregroundColorSelected="%s" backgroundColor="%s" backgroundColorSelected="%s" transparent="1" zPosition="2" />
            <widget name="status" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="center" valign="center" transparent="1" zPosition="2" />
            %s
            %s
            %s
        </screen>
    """ % (
        name, w, h, BG,
        _images_dir(), w, h,
        logo_widget,
        header_x, scale_y(40), scale(500), scale_y(56), font(28), GOLD, BG,
        scale(48), scale_y(96), scale(1100), scale_y(34), font(22), TEXT,
        scale(48), scale_y(132), scale(1100), scale_y(20), font(14), MUTED,
        accent,
        pig_widget,
        list_x, scale_y(162), list_w, scale_y(list_h), item_h,
        TEXT, GOLD, PANEL, SELECT_BG,
        scale(48), scale_y(162 + list_h + 12), scale(1184), scale_y(30),
        font(15), MUTED,
        epg_widget,
        footer_widget,
        extra_widgets,
    ))


def _images_dir():
    """Absoluter Pfad zum images-Verzeichnis (neben den Plugin-Modulen)."""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
