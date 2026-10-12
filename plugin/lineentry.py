# -*- coding: utf-8 -*-
"""Smartys IPTV — Lokale Line-Eingabe + Entsperren-Screen.

Zwei Screens:
  - LineEntryScreen: Line LOKAL eingeben (Server/User/Passwort) + eigenes
    Sicherheits-Passwort. Wird AES-256-GCM-verschlüsselt auf der Box
    gespeichert und NIE an einen Server übertragen.
  - UnlockScreen: Sicherheits-Passwort eingeben, um die verschlüsselte
    Line im RAM zu entsperren (Klartext existiert nur im RAM).

Beide nutzen Enigma2-ConfigListScreen (ConfigPassword-Felder), damit die
Passwörter beim Tippen verdeckt bleiben und nirgends im Klartext liegen,
außer im flüchtigen ConfigText-Objekt.
"""
import urllib.parse
import urllib.request

from Screens.Screen import Screen
from Components.ActionMap import ActionMap
from Components.Label import Label
from Components.ConfigList import ConfigListScreen
from Components.Pixmap import Pixmap
from Components.config import ConfigText, ConfigPassword, getConfigListEntry
from Tools.LoadPixmap import LoadPixmap
from enigma import eTimer

from .config import Config
from . import theme
from . import crypto as sec
from . import unlock_web


def _skin(name, footer, qr=False):
    """Vollbild-Skin mit 'config'-Widget (ConfigList) statt 'list'.
    qr: zusätzlich ein QR-Pixmap-Widget (Handy-Scan zur Passwort-Eingabe)."""
    w, h = theme.osd_size()
    if qr:
        qr_widget = (
            '<widget name="qr" position="%d,%d" size="%d,%d" scale="1" '
            'zPosition="3" transparent="1" alphatest="blend" />'
            % (theme.scale(48), theme.scale_y(400), theme.scale(160), theme.scale_y(160))
        )
        config_h = 60
    else:
        qr_widget = ""
        config_h = 300
    return ("""
        <screen name="%s" position="0,0" size="%d,%d" backgroundColor="%s" flags="wfNoBorder">
            <ePixmap pixmap="%s/images/background.png" position="0,0" size="%d,%d" alphatest="off" zPosition="-1" />
            <eLabel text="Smartys IPTV" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" backgroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            <widget name="header" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            <widget name="subtitle" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
            <eLabel position="%d,%d" size="%d,%d" backgroundColor="%s" zPosition="2" />
            <widget name="explain" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="left" valign="top" transparent="1" zPosition="2" />
            <widget name="config" position="%d,%d" size="%d,%d" itemHeight="%d" scrollbarMode="showOnDemand" enableWrapAround="1" zPosition="2" />
            %s
            <widget name="status" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" halign="center" valign="center" transparent="1" zPosition="2" />
            <eLabel text="%s" position="%d,%d" size="%d,%d" font="Regular;%d" foregroundColor="%s" backgroundColor="%s" halign="left" valign="center" transparent="1" zPosition="2" />
        </screen>
    """ % (
        name, w, h, theme.BG,
        theme._images_dir(), w, h,
        theme.scale(150), theme.scale_y(40), theme.scale(500), theme.scale_y(56),
        theme.font(28), theme.GOLD, theme.BG,
        theme.scale(48), theme.scale_y(96), theme.scale(1100), theme.scale_y(34),
        theme.font(22), theme.TEXT,
        theme.scale(48), theme.scale_y(132), theme.scale(1100), theme.scale_y(20),
        theme.font(14), theme.MUTED,
        theme.scale(48), theme.scale_y(158), theme.scale(200), theme.scale_y(3), theme.GOLD,
        theme.scale(48), theme.scale_y(176), theme.scale(1184), theme.scale_y(110),
        theme.font(18), theme.TEXT,
        theme.scale(48), theme.scale_y(300), theme.scale(1184), theme.scale_y(config_h),
        theme.scale(44),
        qr_widget,
        theme.scale(48), theme.scale_y(620), theme.scale(1184), theme.scale_y(30),
        theme.font(16), theme.MUTED,
        footer,
        theme.scale(48), theme.scale_y(678), theme.scale(1184), theme.scale_y(30),
        theme.font(15), theme.MUTED, theme.BG,
    ))


class UnlockScreen(ConfigListScreen, Screen):
    """Sicherheits-Passwort eingeben, um die verschlüsselte Line zu entsperren.

    payload (optional): Panel-Payload (verschlüsselt). Wird bei korrektem
    Passwort direkt lokal gespeichert + entsperrt (Pairing-Flow).
    target (optional): "live"|"vod"|"series" — nach Erfolg direkt öffnen.
    """

    def __init__(self, session, payload=None, target=None):
        self.skin = _skin("SmartysUnlock", "GRÜN = Entsperren   ·   EXIT = Zurück", qr=True)
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()
        self.payload = payload
        self.target = target
        self.skiptarget = False

        self.pw = ConfigPassword(default="", fixed_size=False)
        self._unlock_running = False
        self.pw.addNotifier(self._on_pw_change, initial_call=False)
        self._entries = [
            getConfigListEntry(_("Sicherheits-Passwort"), self.pw),
        ]
        # ConfigListScreen erzeugt self["config"] (echte ConfigList) und
        # bindet die Einträge — KEIN eigenes .list/.l.setList nötig.
        ConfigListScreen.__init__(self, self._entries, session=session)

        self["header"] = Label(_("Entsperren"))
        self["subtitle"] = Label(_("Sicherheits-Passwort"))
        self["qr"] = Pixmap()
        self["status"] = Label(_(""))

        # Handy-Eingabe: lokalen Web-Server starten + QR für die URL laden.
        self._web_url = None
        self._web_pw = None
        self._web_timer = eTimer()
        try:
            self._web_timer.callback.append(self._web_poll)
        except Exception:
            self._web_timer.timeout.connect(self._web_poll)
        self._web_timer.start(500, False)
        try:
            port = unlock_web.start(self._web_receive)
            self._web_url = "http://%s:%d" % (unlock_web.lan_ip(), port)
            self._load_unlock_qr()
        except Exception:
            self._web_url = None
        self.onClose.append(self._web_close)

        hint = (_("Passwort übers Handy eingeben (gleiches WLAN):\n%s")
                % (self._web_url or _("— nicht verfügbar")))
        self["explain"] = Label(_(
            "Deine Line ist AES-256-verschlüsselt gespeichert.\n"
            "Gib dein Sicherheits-Passwort ein, um sie zu entsperren.\n"
            "Ohne dieses Passwort ist deine Line nicht wiederherstellbar.\n"
            "\n") + hint)

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "cancel": self.close,
                "green": self.unlock_now,
                "red": self.close,
            },
        )

    def _on_pw_change(self, element):
        if element.value and not self._unlock_running:
            self.unlock_now()

    def unlock_now(self):
        if self._unlock_running:
            return
        self._unlock_running = True
        if not sec.crypto_available():
            self["status"].setText(_(
                "python3-cryptography fehlt — bitte per opkg installieren"))
            self._unlock_running = False
            return
        pw = self.pw.value or ""
        if not pw:
            self["status"].setText(_("Bitte Passwort eingeben"))
            self._unlock_running = False
            return
        # PBKDF2 auf schwachen Boxen: kurz blockieren, aber sichtbar melden.
        self["status"].setText(_("Prüfe Passwort…"))
        try:
            if self.payload is not None:
                ok = self.cfg.store_panel_payload(self.payload, pw)
            else:
                ok = self.cfg.unlock(pw)
        except Exception:
            ok = False
        if not ok:
            self["status"].setText(_("Passwort falsch — Line bleibt verschlüsselt"))
            self._unlock_running = False
            return
        self["status"].setText(_("Entsperrt ✓"))
        if self.target and not self.skiptarget:
            self.skiptarget = True
            try:
                from .mainmenu import MainMenuScreen
                menu = MainMenuScreen(self.session)
                getattr(menu, "open_" + self.target)()
            except Exception:
                pass
        self.close()

    def _load_unlock_qr(self):
        """Lädt den QR (Handy-Scan-URL) vom Panel und zeigt ihn an."""
        if not self._web_url:
            return
        qr_path = "/tmp/smartys_unlock_qr.png"
        try:
            qr_url = ("https://panel.smartys.tech/qrdata?url="
                      + urllib.parse.quote(self._web_url, safe=""))
            urllib.request.urlretrieve(qr_url, qr_path)
            pix = LoadPixmap(qr_path)
            if pix:
                self["qr"].instance.setPixmap(pix)
        except Exception:
            pass

    def _web_receive(self, pw):
        """Vom Web-Server-Thread aufgerufen: Passwort nur atomar ablegen."""
        self._web_pw = pw
        return True

    def _web_poll(self):
        pw, self._web_pw = self._web_pw, None
        if pw:
            self.pw.value = pw  # löst _on_pw_change -> unlock_now aus

    def _web_close(self):
        unlock_web.stop()


class LineEntryScreen(ConfigListScreen, Screen):
    """Line LOKAL eingeben — wird nur verschlüsselt auf der Box gespeichert."""

    def __init__(self, session):
        self.skin = _skin("SmartysLineEntry", "GRÜN = Speichern   ·   EXIT = Zurück")
        Screen.__init__(self, session)
        self.session = session
        self.cfg = Config().load()

        self.server = ConfigText(default="http://", fixed_size=False)
        self.user = ConfigText(default="", fixed_size=False)
        self.linepw = ConfigPassword(default="", fixed_size=False)
        self.secpw = ConfigPassword(default="", fixed_size=False)
        self.secpw2 = ConfigPassword(default="", fixed_size=False)
        self._entries = [
            getConfigListEntry(_("Server-URL (z.B. http://host:port)"), self.server),
            getConfigListEntry(_("Benutzername"), self.user),
            getConfigListEntry(_("Line-Passwort"), self.linepw),
            getConfigListEntry(_("Sicherheits-Passwort (mind. 8 Zeichen)"), self.secpw),
            getConfigListEntry(_("Sicherheits-Passwort wiederholen"), self.secpw2),
        ]
        # ConfigListScreen erzeugt self["config"] (echte ConfigList) und
        # bindet die Einträge — KEIN eigenes .list/.l.setList nötig.
        ConfigListScreen.__init__(self, self._entries, session=session)

        self["header"] = Label(_("Line lokal eingeben"))
        self["subtitle"] = Label(_("Verschlüsselt auf dieser Box"))
        self["explain"] = Label(_(
            "Deine Line wird AES-256-verschlüsselt auf dieser Box gespeichert.\n"
            "Sie wird NIE an einen Server übertragen — auch nicht an uns.\n"
            "Ohne dein Sicherheits-Passwort ist sie nicht entschlüsselbar."))
        self["status"] = Label(_(""))

        self["actions"] = ActionMap(
            ["OkCancelActions", "ColorActions"],
            {
                "cancel": self.close,
                "green": self.save_line,
                "red": self.close,
            },
        )

    def save_line(self):
        if not sec.crypto_available():
            self["status"].setText(_(
                "python3-cryptography fehlt — bitte per opkg installieren"))
            return
        server = (self.server.value or "").strip()
        user = (self.user.value or "").strip()
        linepw = self.linepw.value or ""
        secpw = self.secpw.value or ""
        secpw2 = self.secpw2.value or ""
        if not (server.startswith("http://") or server.startswith("https://")):
            self["status"].setText(_("Server-URL muss mit http:// oder https:// beginnen"))
            return
        if not user:
            self["status"].setText(_("Benutzername fehlt"))
            return
        if not linepw:
            self["status"].setText(_("Line-Passwort fehlt"))
            return
        if len(secpw) < 8:
            self["status"].setText(_("Sicherheits-Passwort: mindestens 8 Zeichen"))
            return
        if secpw != secpw2:
            self["status"].setText(_("Sicherheits-Passwörter stimmen nicht überein"))
            return
        self["status"].setText(_("Verschlüssele & speichere…"))
        try:
            self.cfg.store_local_line(server, user, linepw, secpw,
                                      label=_("Lokale Line"))
        except Exception as exc:
            self["status"].setText(_("Speichern fehlgeschlagen: %s") % exc)
            return
        self["status"].setText(_("✓ Verschlüsselt gespeichert — kein Server-Kontakt"))
