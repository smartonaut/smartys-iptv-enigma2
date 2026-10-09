# -*- coding: utf-8 -*-
"""Smartys IPTV — Senderlogo (Picon) Downloader mit Cache.

Lädt stream_icon-Logos asynchron in ein Cache-Verzeichnis. Die Liste zeigt
die Logos an, sobald sie da sind (Refresh-Timer prüft den Cache).
"""

import os
import ssl
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


def _ensure_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
    except Exception:
        pass


def logo_path(stream_id):
    return os.path.join(CACHE_DIR, "%s.png" % stream_id)


def has_logo(stream_id):
    return os.path.exists(logo_path(stream_id))


def _download(icon_url, stream_id):
    """Lädt ein Logo synchron (mit Cache)."""
    path = logo_path(stream_id)
    if os.path.exists(path):
        return path
    _ensure_cache()
    try:
        req = urllib.request.Request(icon_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=8, context=_SSL_CTX) as r:
            data = r.read()
        if data:
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, path)
        return path
    except Exception:
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
        _queue.append((icon_url, stream_id))
    if _worker is None:
        _worker = threading.Thread(target=_worker_loop, daemon=True)
        _worker.start()
