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


def main(*args, **kwargs):
    from .mainmenu import MainMenuScreen

    # WICHTIG: Bei WHERE_MENU ruft Enigma2 diesen Einstiegspunkt bereits beim
    # AUFBAU des Hauptmenues auf, um die Beschreibung abzufragen — dann kommt
    # nur ein menuid-String, keine Session. Wer hier blind einen Screen
    # oeffnet, crasht mit "Modal open are allowed only from a screen which is
    # modal". Beim echten Klick uebergibt Enigma2 dagegen die Session.
    session = kwargs.get("session")
    if session is None or not hasattr(session, "open"):
        session = None
        for a in args:
            if hasattr(a, "open") and hasattr(a, "nav"):
                session = a
                break

    if session is None:
        return "IPTV-Player fuer Smartys (Live-TV, Filme, Serien)"

    session.open(MainMenuScreen)


def sessionstart(reason=0, session=None, **kwargs):
    """Beim Start den Timer-Scheduler initialisieren (persistierte Timer laden)."""
    if reason == 0:
        try:
            from . import recorder
            recorder.get_scheduler()
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
    return [
        # Plugin-Menü (Hauptmenü, direkt oder unter Erweiterungen/Plugins)
        PluginDescriptor(
            name="Smartys IPTV",
            description="IPTV-Player für Smartys (Live-TV, Filme, Serien)",
            where=_menu_where,
            icon=icon_file,
            fnc=main,
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
