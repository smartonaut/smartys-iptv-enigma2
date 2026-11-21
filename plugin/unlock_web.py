# -*- coding: utf-8 -*-
"""Smartys IPTV — Handy-Texteingabe (lokaler Web-Server).

Wenn ein Eingabe-Screen offen ist, läuft hier ein winziger HTTP-Server
(nur Python-Stdlib) auf Port 8080. Der Nutzer öffnet im Handy-Browser
(gleiches WLAN) http://<Box-IP>:8080, tippt dort Text (Passwort, Suchbegriff
…) und die Box verarbeitet ihn sofort. Kein Fernbedienungs-Gefummel mehr.

Sicherheit: Der Server existiert NUR solange der aufrufende Screen offen ist
und wird beim Schließen sofort beendet. Übertragung im LAN (HTTP, kurzlebig).
"""

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
body { font-family: -apple-system, sans-serif; background: #0b0e14; color: #e8eefc;
       display: flex; justify-content: center; padding: 24px; margin: 0; }
.card { background: #11172a; border: 1px solid #232c42; border-radius: 12px;
        padding: 24px; max-width: 420px; width: 100%; }
h1 { font-size: 20px; color: #ffc94d; margin: 0 0 8px; }
p { color: #6b7a99; font-size: 14px; line-height: 1.4; }
input { width: 100%; box-sizing: border-box; padding: 12px;
        font-size: 16px; background: #0b0e14; color: #e8eefc;
        border: 1px solid #232c42; border-radius: 8px; margin: 12px 0; }
button { width: 100%; padding: 12px; font-size: 16px; background: #ffc94d;
        color: #0b0e14; border: none; border-radius: 8px; font-weight: 600; }
.ok { color: #6fcf9f; font-weight: 600; }
.err { color: #ff9b9b; font-weight: 600; }
</style></head><body>
<div class="card">
  <h1>__TITLE__</h1>
  <p>__HINT__</p>
  <form method="post">
    __FORM__
    <button type="submit">__BUTTON__</button>
  </form>
  __STATUS__
</div></body></html>"""

# Standard-Werte (Passwort-Eingabe); werden pro start() überschrieben.
_params = {
    "title": "Smartys IPTV",
    "hint": "Gib dein Sicherheits-Passwort ein, um die Line zu entsperren.",
    "field_type": "password",
    "placeholder": "Passwort",
    "button": "Entsperren",
    "form": "",
}

# Felder fuer Mehrfach-Eingabe: [(name, label, typ, placeholder), ...]
# Ist fields gesetzt, liefert der Callback ein dict statt eines str.
_fields = None

_server = None
_thread = None
_callback = None


def _form_html():
    """HTML fuer das Formular: ein Feld (klassisch) oder mehrere."""
    if not _fields:
        return ('<input type="%s" name="text" autocomplete="off" autofocus\n'
                '           placeholder="%s" autocapitalize="off">'
                % (_params["field_type"], _params["placeholder"]))
    teile = []
    for i, (name, label, typ, platzhalter) in enumerate(_fields):
        teile.append(
            '<label for="f_%s">%s</label>'
            '<input id="f_%s" type="%s" name="%s" autocomplete="off"%s '
            'placeholder="%s" autocapitalize="off" spellcheck="false">'
            % (name, label, name, typ, name,
               " autofocus" if i == 0 else "", platzhalter))
    return "".join(teile)


class _Handler(BaseHTTPRequestHandler):
    def _page(self, status):
        html = _PAGE
        werte = dict(_params)
        werte["form"] = _form_html()
        for key, val in werte.items():
            html = html.replace("__%s__" % key.upper(), val)
        return html.replace("__STATUS__", status)

    def do_GET(self):
        self._respond(self._page(""))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        params = urllib.parse.parse_qs(body)
        ok = False
        if _fields:
            daten = {}
            for name, _label, _typ, _pl in _fields:
                daten[name] = (params.get(name) or [""])[0].strip()
            if any(daten.values()) and _callback:
                ok = _callback(daten)
        else:
            text = (params.get("text") or [""])[0]
            if text and _callback:
                ok = _callback(text)
        if ok:
            status = '<p class="ok">&check; Übernommen &mdash; du kannst das Handy weglegen.</p>'
        else:
            status = '<p class="err">Fehler &mdash; versuche es erneut.</p>'
        self._respond(self._page(status))

    def _respond(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # keine Log-Ausgabe auf der Box


def start(callback, title=None, hint=None, field_type=None,
          placeholder=None, button=None, fields=None):
    """Startet den Server in einem Daemon-Thread. Rückgabe: Port.

    fields: optionale Liste [(name, label, typ, placeholder), ...] fuer ein
    Formular mit mehreren Feldern. Der Callback bekommt dann ein dict
    {name: wert} statt eines einzelnen Strings.
    """
    global _server, _thread, _callback, _fields
    stop()
    _fields = list(fields) if fields else None
    if title is not None:
        _params["title"] = title
    if hint is not None:
        _params["hint"] = hint
    if field_type is not None:
        _params["field_type"] = field_type
    if placeholder is not None:
        _params["placeholder"] = placeholder
    if button is not None:
        _params["button"] = button
    _callback = callback
    _server = HTTPServer(("0.0.0.0", PORT), _Handler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    return PORT


def stop():
    global _server, _thread, _callback, _fields
    _callback = None
    _fields = None
    if _server is not None:
        try:
            _server.shutdown()
        except Exception:
            pass
        try:
            _server.server_close()
        except Exception:
            pass
    _server = None
    _thread = None
    _callback = None


def lan_ip():
    """Ermittelt die LAN-IP der Box fuer die Handy-URL.

    NICHT ueber eine Route zu 8.8.8.8 raten: geht der Verkehr ueber einen
    VPN-Tunnel (tun0), liefert das die Tunnel-Adresse (10.x) - die ist im
    WLAN nicht erreichbar und der QR-Code zeigt ins Leere.
    Stattdessen das echte LAN-Interface (eth0/wlan0) nehmen.
    """
    ips = accessible_ips()
    return ips[0][1] if ips else "127.0.0.1"


def accessible_ips():
    """Alle Adressen, unter denen die Handy-Seite erreichbar sein kann.

    Reihenfolge: LAN zuerst (gleiches WLAN), dann VPN (Handy mit Tunnel).
    Rueckgabe: [(label, ip), ...] mit label "LAN" bzw. "VPN".
    """
    import re
    import subprocess
    skip_prefix = ("lo", "docker", "br-", "veth")
    vpn_prefix = ("tun", "tap", "wg")
    lan, vpn = [], []
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5).stdout.decode("utf-8", "replace")
        for line in out.splitlines():
            m = re.search(r"^\d+:\s+(\S+)\s+inet\s+(\d+\.\d+\.\d+\.\d+)", line)
            if not m:
                continue
            iface, ip = m.group(1), m.group(2)
            if iface.startswith(skip_prefix):
                continue
            if ip.startswith("169.254.") or ip.startswith("127."):
                continue
            entry = ("VPN" if iface.startswith(vpn_prefix) else "LAN", ip)
            (vpn if entry[0] == "VPN" else lan).append(entry)
    except Exception:
        pass

    if not lan and not vpn:
        # Fallback: alte Methode (nur wenn 'ip' fehlt)
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))
            lan = [("LAN", s.getsockname()[0])]
        except Exception:
            pass
        finally:
            s.close()
    return lan + vpn


def urls(port=None):
    """Fertige Handy-URLs inkl. Port, LAN zuerst."""
    if port is None:
        port = PORT
    return [(label, "http://%s:%d" % (ip, port)) for label, ip in accessible_ips()]
