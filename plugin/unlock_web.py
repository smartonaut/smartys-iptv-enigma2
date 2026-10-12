# -*- coding: utf-8 -*-
"""Smartys IPTV — Handy-Passworteingabe (lokaler Web-Server).

Wenn der Entsperren-Screen offen ist, läuft hier ein winziger HTTP-Server
(nur Python-Stdlib) auf Port 8080. Der Nutzer öffnet im Handy-Browser
(gleiches WLAN) http://<Box-IP>:8080, tippt dort sein Sicherheits-Passwort
und die Box entsperrt sofort. Kein Fernbedienungs-Gefummel mehr.

Sicherheit: Der Server existiert NUR solange der UnlockScreen offen ist und
wird beim Schließen sofort beendet. Übertragung im LAN (HTTP, kurzlebig).
"""

import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8080

_PAGE = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smartys IPTV &mdash; Entsperren</title>
<style>
body { font-family: -apple-system, sans-serif; background: #0b0e14; color: #e8eefc;
       display: flex; justify-content: center; padding: 24px; margin: 0; }
.card { background: #11172a; border: 1px solid #232c42; border-radius: 12px;
        padding: 24px; max-width: 420px; width: 100%; }
h1 { font-size: 20px; color: #ffc94d; margin: 0 0 8px; }
p { color: #6b7a99; font-size: 14px; line-height: 1.4; }
input[type=password] { width: 100%; box-sizing: border-box; padding: 12px;
        font-size: 16px; background: #0b0e14; color: #e8eefc;
        border: 1px solid #232c42; border-radius: 8px; margin: 12px 0; }
button { width: 100%; padding: 12px; font-size: 16px; background: #ffc94d;
        color: #0b0e14; border: none; border-radius: 8px; font-weight: 600; }
.ok { color: #6fcf9f; font-weight: 600; }
.err { color: #ff9b9b; font-weight: 600; }
</style></head><body>
<div class="card">
  <h1>Smartys IPTV</h1>
  <p>Gib dein Sicherheits-Passwort ein, um die Line auf der Box zu entsperren.</p>
  <form method="post">
    <input type="password" name="pw" autocomplete="off" autofocus
           placeholder="Passwort" autocapitalize="off">
    <button type="submit">Entsperren</button>
  </form>
  __STATUS__
</div></body></html>"""

_server = None
_thread = None
_callback = None


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self._respond(_PAGE.replace("__STATUS__", ""))

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        params = urllib.parse.parse_qs(body)
        pw = (params.get("pw") or [""])[0]
        ok = False
        if pw and _callback:
            ok = _callback(pw)
        if ok:
            status = '<p class="ok">&check; Entsperrt &mdash; du kannst das Handy weglegen.</p>'
        else:
            status = '<p class="err">Passwort falsch &mdash; versuche es erneut.</p>'
        self._respond(_PAGE.replace("__STATUS__", status))

    def _respond(self, html):
        data = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # keine Log-Ausgabe auf der Box


def start(callback):
    """Startet den Server in einem Daemon-Thread. Rückgabe: Port."""
    global _server, _thread, _callback
    stop()
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
