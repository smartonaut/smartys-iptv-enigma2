# -*- coding: utf-8 -*-
"""Smartys IPTV — EPG-Ansicht eines Senders + Timer-Aufnahme.

Zeigt die heutigen Sendungen des markierten Senders (short_epg).
REC-Taste plant eine Timer-Aufnahme für die markierte Sendung.
"""

import base64

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList
from enigma import eTimer

from . import theme
from . import recorder


def _b64(s):
    try:
        return base64.b64decode(s).decode("utf-8", "replace")
    except Exception:
        return s or ""


def _fmt_time(s):
    if not s:
        return ""
    s = s.strip()
    if len(s) >= 16:
        try:
            return s[11:16]
        except Exception:
            pass
    return s


class EpgScreen(Screen):
    """Zeigt das EPG eines Senders und erlaubt Timer-Aufnahmen."""

    def __init__(self, session, api, stream_id, channel_name):
        self.skin = theme.build_skin(
            "SmartysEpg", logo=False,
            footer="REC = Timer-Aufnahme   ·   OK = sofort aufnehmen   ·   EXIT = Zurück")
        Screen.__init__(self, session)
        self.session = session
        self.api = api
        self.stream_id = stream_id
        self.channel_name = channel_name

        self["header"] = Label(_(channel_name))
        self["subtitle"] = Label(_("Heutige Sendungen"))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self.on_ok,
                "cancel": self.close,
                "red": self.on_rec,
            },
        )
        self.onLayoutFinish.append(self._load)

    def _load(self):
        try:
            data = self.api.short_epg(self.stream_id, limit=20)
            listings = data.get("epg_listings", []) or []
        except Exception:
            listings = []

        entries = []
        self._listings = listings
        for ep in listings:
            title = _b64(ep.get("title", ""))
            start = _fmt_time(ep.get("start", ""))
            end = _fmt_time(ep.get("end", ""))
            entries.append(("%s–%s   %s" % (start, end, title), ep))

        if not entries:
            entries = [(_("Keine EPG-Daten"), None)]
        self["list"].setList(entries)
        self["status"].setText(_("%d Sendungen") % len(listings))

    def _current(self):
        sel = self["list"].getCurrent()
        if not sel or not sel[1]:
            return None
        return sel[1]

    def on_rec(self):
        """REC = Timer-Aufnahme für die markierte Sendung planen."""
        ep = self._current()
        if not ep:
            return
        title = _b64(ep.get("title", ""))
        try:
            start_ts = int(ep.get("start_timestamp", "0"))
            end_ts = int(ep.get("stop_timestamp", "0"))
        except Exception:
            start_ts = end_ts = 0
        if not start_ts or not end_ts:
            self.session.open(
                MessageBox, _("Keine gültige Zeitangabe."),
                MessageBox.TYPE_ERROR, timeout=5)
            return
        url = self.api.creds.stream_url(self.stream_id, "ts")
        name = "%s — %s" % (self.channel_name, title)
        sched = recorder.get_scheduler()
        sched.schedule(url, name, start_ts, end_ts)
        self.session.open(
            MessageBox,
            _("Timer-Aufnahme geplant:\n%s\n%s") % (
                name, _fmt_time(ep.get("start", "")),
            ),
            MessageBox.TYPE_INFO, timeout=6)

    def on_ok(self):
        """OK = sofortige Aufnahme des markierten Senders starten/stoppen."""
        rec = recorder.get_recorder()
        if rec.recording:
            path = rec.stop()
            self.session.open(
                MessageBox, _("Aufnahme beendet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
        else:
            url = self.api.creds.stream_url(self.stream_id, "ts")
            try:
                path = rec.start(url, self.channel_name)
            except Exception as e:
                self.session.open(
                    MessageBox, _("Aufnahme fehlgeschlagen: %s") % str(e),
                    MessageBox.TYPE_ERROR, timeout=5)
                return
            self.session.open(
                MessageBox, _("Aufnahme gestartet:\n%s") % path,
                MessageBox.TYPE_INFO, timeout=5)
