# -*- coding: utf-8 -*-
"""Smartys IPTV — Enigma2-Plugin (Einstiegspunkt).

Enigma2 sucht den Einstiegspunkt als `plugin.py` (nicht `__init__.py`).
"""

from __future__ import absolute_import

from Plugins.Plugin import PluginDescriptor


def main(session, **kwargs):
    from .mainmenu import MainMenuScreen
    session.open(MainMenuScreen)


def sessionstart(reason, session=None, **kwargs):
    """Beim Sessionstart den Timer-Scheduler initialisieren.

    Lädt persistierte Timer-Aufnahmen und startet den 30s-Poll — so laufen
    geplante Aufnahmen auch, wenn der Player nicht geöffnet ist.
    """
    if reason == 0:
        try:
            from . import recorder
            recorder.get_scheduler()
        except Exception:
            pass


def Plugins(**kwargs):
    import os
    _icon = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "images", "logo.png")
    return [
        PluginDescriptor(
            name="Smartys IPTV",
            description="IPTV-Player für Smartys (Live-TV, Filme, Serien)",
            where=[
                PluginDescriptor.WHERE_PLUGINMENU,
                PluginDescriptor.WHERE_EXTENSIONSMENU,
            ],
            fnc=main,
            icon=_icon,
        ),
        # Autostart: Timer-Scheduler beim Enigma2-Start initialisieren.
        PluginDescriptor(
            name="Smartys IPTV (Autostart)",
            where=[PluginDescriptor.WHERE_AUTOSTART],
            fnc=sessionstart,
        ),
    ]
