# -*- coding: utf-8 -*-
"""Smartys IPTV — Timer-Aufnahmen (geplante Aufnahmen anzeigen + abbrechen)."""

import time

from Screens.MessageBox import MessageBox
from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.MenuList import MenuList

from . import theme
from . import recorder


class TimerListScreen(Screen):
    """Listet geplante (Timer-)Aufnahmen und bricht sie auf OK ab."""

    def __init__(self, session):
        self.skin = theme.build_skin(
            "SmartysTimers",
            tasten=[(theme.TASTE_OK, "OK", "Abbrechen"),
                    (theme.TASTE_GELB, "GELB", "EPG-Übersicht"),
                    (None, "EXIT", "Zurück")])
        Screen.__init__(self, session)
        self.session = session

        self["header"] = Label(_("Timer-Aufnahmen"))
        self["subtitle"] = Label(_("Geplante Aufnahmen"))
        self["list"] = MenuList([])
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "ok": self._cancel,
                "cancel": self.close,
                "red": self._cancel,
                "yellow": self._epg_uebersicht,
            },
        )
        self.onLayoutFinish.append(self._refresh)

    def _epg_uebersicht(self):
        """GELB: EPG aller Sender als Liste — dort direkt vormerken."""
        from .config import Config
        from .api import Credentials, XtreamApi
        from .epgoverview import EpgOverviewScreen

        cfg = Config().load()
        prov = cfg.providers()
        if not prov:
            self.session.open(
                MessageBox, _("Keine Line eingerichtet."),
                MessageBox.TYPE_INFO, timeout=4)
            return
        p = prov[0]
        api = XtreamApi(Credentials(p["server_url"], p["username"],
                                    p["password"]))
        # Nach dem Schliessen der Uebersicht die Timer-Liste auffrischen —
        # dort koennen neue Eintraege dazugekommen sein.
        self.session.openWithCallback(lambda _x: self._refresh(),
                                       EpgOverviewScreen, api, cfg)

    def _refresh(self):
        pending = recorder.get_scheduler().pending()
        if not pending:
            self["list"].setList([])
            self["status"].setText(_("Keine geplanten Aufnahmen."))
            return
        entries = []
        for t in pending:
            name = t.get("name", "?")
            start = self._fmt(t.get("start"))
            end = self._fmt(t.get("end"))
            entries.append(("%s   (%s – %s)" % (name, start, end), t))
        self["list"].setList(entries)
        self["status"].setText(
            _("%d geplante Aufnahme(n) — OK zum Abbrechen") % len(entries))

    @staticmethod
    def _fmt(ts):
        try:
            return time.strftime("%d.%m %H:%M", time.localtime(int(ts)))
        except Exception:
            return "?"

    def _cancel(self):
        sel = self["list"].getCurrent()
        if not sel:
            return
        entry = sel[1]
        name = entry.get("name", "?")

        def _done(answer):
            if answer:
                recorder.get_scheduler().cancel(entry)
                self._refresh()

        self.session.openWithCallback(
            _done, MessageBox,
            _("Aufnahme '%s' wirklich abbrechen?") % name,
            MessageBox.TYPE_YESNO)
