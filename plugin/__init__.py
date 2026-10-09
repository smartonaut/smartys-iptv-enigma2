# -*- coding: utf-8 -*-
"""Smartys IPTV — Enigma2-Plugin (Einstiegspunkt)."""

from __future__ import absolute_import

from Components.PluginComponent import plugins
from Plugins.Plugin import PluginDescriptor


def main(session, **kwargs):
    from .mainmenu import MainMenuScreen
    session.open(MainMenuScreen)


def Plugins(**kwargs):
    return [
        PluginDescriptor(
            name="Smartys IPTV",
            description="IPTV-Player für Smartys (Live-TV, Filme, Serien)",
            where=[
                PluginDescriptor.WHERE_PLUGINMENU,
                PluginDescriptor.WHERE_EXTENSIONSMENU,
            ],
            fnc=main,
        )
    ]
