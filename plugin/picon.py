# -*- coding: utf-8 -*-
"""Smartys IPTV — Senderlogo/Cover Downloader mit Cache.

Lädt stream_icon/Cover und speichert sie IMMER als PNG. VOD-Cover sind
meist JPEG (tmdb.org); LoadPixmap rendert aber nur PNG zuverlässig,
deshalb werden JPEGs per ffmpeg nach PNG konvertiert.
"""

import os
import ssl
import subprocess
import threading
import urllib.request

CACHE_DIR = "/tmp/smartys_picons"

_SSL_CTX = ssl.create_default_context()
_SSL_CTX.check_hostname = False
_SSL_CTX.verify_mode = ssl.CERT_NONE

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/145.0.0.0 Safari/537.36")

_queue = []
_lock = threading.Lock()
_worker = None
# URLs, deren Download einmal fehlgeschlagen ist — nicht bei jedem
# Selection-Change erneut (8s Timeout) versuchen.
_failed = set()


def _ensure_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        pass


def logo_path(stream_id):
    return os.path.join(CACHE_DIR, "%s.png" % stream_id)


def has_logo(stream_id):
    return os.path.exists(logo_path(stream_id))


def _ffmpeg_to_png(data, base, size=None):
    """Konvertiert JPEG-Bytes nach PNG via ffmpeg (subprocess.Popen),
    optional auf die Zielgröße skaliert (scale=W:H)."""
    jpg = base + ".tmp.jpg"
    png = base + ".tmp.png"
    try:
        with open(jpg, "wb") as f:
            f.write(data)
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", jpg]
        if size:
            cmd += ["-vf", "scale=%d:%d" % (int(size[0]), int(size[1]))]
        cmd += [png]
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        proc.wait(timeout=20)
        if os.path.exists(png):
            with open(png, "rb") as f:
                out = f.read()
            if out[:2] == b"\x89P":  # PNG magic
                return out
    except Exception:
        pass
    finally:
        for tmp in (jpg, png):
            try:
                os.remove(tmp)
            except Exception:
                pass
    return data  # Fallback: rohe Bytes


def _download(icon_url, stream_id, size=None):
    """Lädt ein Bild synchron (mit Cache), speichert immer als PNG."""
    path = logo_path(stream_id)
    if os.path.exists(path):
        return path
    _ensure_cache()
    try:
        with _lock:
            if icon_url in _failed:
                return None
    except Exception:
        pass
    try:
        req = urllib.request.Request(icon_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            data = r.read()
        if not data:
            return None
        if data[:2] == b"\xff\xd8":
            data = _ffmpeg_to_png(data, os.path.join(CACHE_DIR, str(stream_id)),
                                   size)
        tmp = path + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
        return path
    except Exception:
        try:
            with _lock:
                _failed.add(icon_url)
        except Exception:
            pass
        return None


def _worker_loop():
    while True:
        with _lock:
            if not _queue:
                item = None
            else:
                item = _queue.pop(0)
        if item is None:
            import time
            time.sleep(0.2)
            continue
        icon_url, stream_id = item
        try:
            _download(icon_url, stream_id)
        except Exception:
            pass


def request(icon_url, stream_id):
    """Fordert das Laden eines Logos an (asynchron, nicht blockierend)."""
    global _worker
    if not icon_url or not stream_id or has_logo(stream_id):
        return
    with _lock:
        # Keine Duplikate in die Queue legen (sonst lädt der Worker dieselbe
        # fehlgeschlagene URL bei jedem Selection-Change erneut und immer wieder).
        if (icon_url, stream_id) not in _queue:
            _queue.append((icon_url, stream_id))
    if _worker is None:
        _worker = threading.Thread(target=_worker_loop, daemon=True)
        _worker.start()
