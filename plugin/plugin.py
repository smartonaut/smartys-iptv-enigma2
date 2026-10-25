# -*- coding: utf-8 -*-
"""Smartys IPTV — Enigma2-Plugin (Einstiegspunkt).

Enigma2 sucht den Einstiegspunkt als `plugin.py` (nicht `__init__.py`).
"""

from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor
# WICHTIG: Dieser Import stellt sicher, dass der PluginComponent bereits
# initialisiert ist, bevor dieses Plugin registriert wird. Ohne ihn wird
# das Plugin in openATV 7.6 stillschweigend nicht in die Menüs aufgenommen.
from Components.PluginComponent import plugins  # noqa: F401


def _session_finden(args, kwargs):
    s = kwargs.get("session")
    if s is not None and hasattr(s, "open"):
        return s
    for a in args:
        if hasattr(a, "open") and hasattr(a, "nav"):
            return a
    return None


def main(*args, **kwargs):
    """Klick-Handler (WHERE_PLUGINMENU / Erweiterungen)."""
    session = _session_finden(args, kwargs)
    if session is None:
        return
    from .mainmenu import MainMenuScreen
    session.open(MainMenuScreen)


def _menu_container(menuid="", **kwargs):
    """Container fuer WHERE_MENU.

    Enigma2 ruft diese Funktion schon beim AUFBAU des Hauptmenues auf und
    iteriert ueber die Rueckgabe. Erwartet werden Tupel
    (Text, Funktion, Key) — NICHT PluginDescriptor-Objekte, die sind nicht
    subscriptable und werfen "'PluginDescriptor' object is not subscriptable".
    Die Funktion im Tupel wird beim Klick mit der Session aufgerufen; ein
    direktes session.open() hier drin reisst das ganze Hauptmenue mit.
    """
    if menuid and menuid != "mainmenu":
        return []
    return [("Smartys IPTV", main, "smartys_iptv", False)]


def sessionstart(reason=0, session=None, **kwargs):
    """Beim Start Timer-Scheduler und EPG-Cache initialisieren.

    Der EPG-Cache wurde bisher erst beim Oeffnen eines EPG-Screens gebaut —
    nach einem Loeschen blieb er leer, und die EPG-Uebersicht hatte nichts
    anzuzeigen. Er wird jetzt im Hintergrund-Thread beim Start gefuellt
    (dauert etwa eine Minute, blockiert aber nichts).
    """
    if reason == 0:
        try:
            from . import recorder
            recorder.get_scheduler()
        except Exception:
            pass
        try:
            from . import epgbackup
            epgbackup.ensure_loaded()
        except Exception:
            pass
        # Eigenes EPG exportieren, damit der Server es an die anderen Boxen
        # verteilen kann. Nur auf Boxen mit Tuner sinnvoll — ohne Anschluss
        # ist die Datei leer und der Upload schlaegt still fehl.
        try:
            from . import epgexport
            epgexport.exportiere_thread()
        except Exception:
            pass


def Plugins(**kwargs):
    import os
    icon_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "images", "logo.png")
    # Einstellung "Im Hauptmenü anzeigen": direkt im Hauptmenü (WHERE_MENU)
    # statt unter Erweiterungen/Plugins (WHERE_PLUGINMENU).
    try:
        from .config import Config
        _show_in_menu = bool(Config().load().get("show_in_main_menu", False))
    except Exception:
        _show_in_menu = False
    _menu_where = (PluginDescriptor.WHERE_MENU if _show_in_menu
                   else PluginDescriptor.WHERE_PLUGINMENU)
    _menu_fnc = _menu_container if _show_in_menu else main
    return [
        # Plugin-Menü (Hauptmenü, direkt oder unter Erweiterungen/Plugins)
        PluginDescriptor(
            name="Smartys IPTV",
            description="IPTV-Player für Smartys (Live-TV, Filme, Serien)",
            where=_menu_where,
            icon=icon_file,
            fnc=_menu_fnc,
        ),
        # Erweiterungs-Browser (grüne Taste)
        PluginDescriptor(
            name="Smartys IPTV",
            description="IPTV-Player für Smartys (Live-TV, Filme, Serien)",
            where=PluginDescriptor.WHERE_EXTENSIONSMENU,
            icon=icon_file,
            fnc=main,
        ),
        # Autostart + Sessionstart: Timer-Scheduler initialisieren und die
        # Session merken (WHERE_MENU bekommt keine eigene Session).
        PluginDescriptor(
            name="Smartys IPTV (Autostart)",
            where=[PluginDescriptor.WHERE_AUTOSTART,
                   PluginDescriptor.WHERE_SESSIONSTART],
            fnc=sessionstart,
        ),
    ]
