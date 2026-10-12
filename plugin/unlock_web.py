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
    <input type="__FIELD_TYPE__" name="text" autocomplete="off" autofocus
           placeholder="__PLACEHOLDER__" autocapitalize="off">
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
}

_server = None
_thread = None
_callback = None


class _Handler(BaseHTTPRequestHandler):
    def _page(self, status):
        html = _PAGE
        for key, val in _params.items():
            html = html.replace("__%s__" % key.upper(), val)
        return html.replace("__STATUS__", status)

    def do_GET(self):
        self._respond(self._page(""))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        params = urllib.parse.parse_qs(body)
        text = (params.get("text") or [""])[0]
        ok = False
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
          placeholder=None, button=None):
    """Startet den Server in einem Daemon-Thread. Rückgabe: Port."""
    global _server, _thread, _callback
    stop()
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
    global _server, _thread, _callback
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
    """Ermittelt die LAN-IP der Box (für die Anzeige-URL im Screen)."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
