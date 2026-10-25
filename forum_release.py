# -*- coding: utf-8 -*-
"""Versionsbeitrag im Flarum anlegen.

Aufruf auf dem VPS:  VERSION=0.4.0 python3 forum_release.py

Liest den Text aus der Datei /tmp/forum_text.md (dort legt release.sh bzw.
der Aufrufer den Beitrag ab) oder aus der Umgebungsvariable FORUM_TEXT.
Schreibt nur, wenn die Version noch nicht im Thread steht.
"""
import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.request

BASIS = "https://forum.smartys.tech"
CRED = "/home/smarty/docker-host/flarum/CREDENTIALS.txt"
DISCUSSION = 13


def passwort():
    with open(CRED, encoding="utf-8", errors="replace") as f:
        zeilen = [z.strip() for z in f if z.strip()]
    for z in zeilen:
        if "admin" in z.lower() or "flarum" in z.lower():
            return z.split(":", 1)[-1].strip() if ":" in z else z
    return zeilen[2].split(":", 1)[-1].strip() if ":" in zeilen[2] else zeilen[2]


def main():
    version = os.environ.get("VERSION", "").strip()
    if not version:
        print("VERSION fehlt")
        return 2

    text = os.environ.get("FORUM_TEXT", "")
    if not text and os.path.exists("/tmp/forum_text.md"):
        with open("/tmp/forum_text.md", encoding="utf-8") as f:
            text = f.read()
    if not text.strip():
        print("Kein Beitragstext (FORUM_TEXT oder /tmp/forum_text.md)")
        return 2

    pw = passwort()
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]

    def hole(url):
        with op.open(url, timeout=30) as r:
            return r.read().decode("utf-8", "replace")

    def sende(url, daten, kopf=None):
        h = {"Content-Type": "application/json"}
        if kopf:
            h.update(kopf)
        req = urllib.request.Request(url, data=json.dumps(daten).encode(),
                                     headers=h, method="POST")
        with op.open(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")

    seite = hole(BASIS + "/")
    m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', seite)
    if not m:
        print("Kein CSRF-Token")
        return 1
    csrf = m.group(1)

    try:
        status, _ = sende(BASIS + "/login", {"identification": "admin",
                                             "password": pw,
                                             "csrfToken": csrf,
                                             "remember": True})
        if status != 200:
            print("Login:", status)
            return 1
    except urllib.error.HTTPError as e:
        print("Login-Fehler:", e.code)
        return 1

    # Schon drin?
    try:
        daten = json.loads(hole(BASIS + "/api/discussions/%d" % DISCUSSION))
        for p in daten.get("included", []):
            if p.get("type") != "posts":
                continue
            inhalt = json.loads(hole(BASIS + "/api/posts/%s" % p["id"]))
            if ("v" + version) in inhalt["data"]["attributes"]["content"]:
                print("v%s steht schon drin — nichts zu tun" % version)
                return 0
    except Exception as e:
        print("Beitraege nicht lesbar:", e)

    seite = hole(BASIS + "/")
    m = re.search(r'"csrfToken"\s*:\s*"([^"]+)"', seite)
    csrf = m.group(1) if m else csrf

    try:
        status, antwort = sende(
            BASIS + "/api/posts",
            {"data": {"type": "posts",
                      "attributes": {"content": text},
                      "relationships": {"discussion": {
                          "data": {"type": "discussions",
                                   "id": str(DISCUSSION)}}}}},
            {"X-CSRF-Token": csrf, "Referer": BASIS + "/d/%d" % DISCUSSION})
        if status != 201:
            print("Fehler:", status, antwort[:200])
            return 1
        print("Beitrag fuer v%s angelegt" % version)
    except urllib.error.HTTPError as e:
        print("Fehler beim Schreiben:", e.code, e.read()[:200])
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
