# -*- coding: utf-8 -*-
"""Smartys IPTV — Stream-Player-Screen (nach XStreamity-Vorbild).

Das Video wird über den Hardware-Decoder gerendert (session.nav.playService).
Dieser Screen legt nur ein transparentes OSD darüber (Infobar), damit das
Video durchscheint — exakt wie XStreamity_StreamPlayer. Kein eigenes
Video-Decoding; der Player ist exteplayer3/GStreamer (ffmpeg, OpenSource).
"""

from Screens.Screen import Screen
from Components.ServiceEventTracker import InfoBarBase
from Components.ActionMap import ActionMap
from enigma import eServiceReference

from . import theme


class StreamPlayerScreen(InfoBarBase, Screen):
    """Vollbild-Player für einen IPTV-Stream."""

    def __init__(self, session, url, servicetype=4097, name=""):
        Screen.__init__(self, session)
        self.session = session
        self.streamurl = url
        self.servicetype = servicetype

        # Transparenter Vollbild-Skin: Video (Decoder) scheint durch.
        w, h = theme.osd_size()
        self.skin = (
            '<screen name="SmartysStreamPlayer" position="0,0" '
            'size="%d,%d" backgroundColor="transparent" flags="wfNoBorder">'
            '<widget name="actions" position="0,0" size="1,1" '
            'transparent="1" zPosition="0"/>'
            "</screen>" % (w, h)
        )

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
