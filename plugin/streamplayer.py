# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Player-Screen (nach XStreamity-Vorbild).

Öffnet einen eigenen Screen, der InfoBarBase erbt und das Video über
session.nav.playService abspielt. Der Screen bleibt offen und rendert
das Video im Vollbild — exakt wie XStreamity_StreamPlayer.

Servicetype 4097 = GStreamer (eingebaut), 5002 = exteplayer3 (serviceapp).
"""

from Screens.Screen import Screen
from Screens.InfoBarGenerics import InfoBarBase
from Components.ActionMap import ActionMap
from enigma import eServiceReference


class StreamPlayerScreen(Screen):
    """Vollbild-Player für einen IPTV-Stream."""

    def __init__(self, session, url, servicetype=4097, name=""):
        Screen.__init__(self, session)
        self.session = session
        self.streamurl = url
        self.servicetype = servicetype

        # InfoBarBase übernimmt das Video-Rendering + Infobar-Handling.
        InfoBarBase.__init__(self)

        self["actions"] = ActionMap(
            ["OkCancelActions", "DirectionActions"],
            {
                "cancel": self.quit,
                "stop": self.quit,
                "up": self.channel_up,
                "down": self.channel_down,
            },
        )

        self.onFirstExecBegin.append(self.play_stream)

    def play_stream(self):
        try:
            ref = eServiceReference(int(self.servicetype), 0, self.streamurl)
            ref.setName(self.streamurl)
            self.session.nav.playService(ref)
        except Exception:
            pass

    def quit(self):
        try:
            self.session.nav.stopService()
        except Exception:
            pass
        self.close()

    def channel_up(self):
        self.quit()

    def channel_down(self):
        self.quit()
