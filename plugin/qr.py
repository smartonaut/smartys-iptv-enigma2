# -*- coding: utf-8 -*-
"""Smartys IPTV — lokaler QR-Code-Generator (kein Panel nötig).

Nutzt den reinen-Python-Encoder qrgen.py (Project Nayuki, MIT-Lizenz) +
Pillow (auf der Box installiert) zum Schreiben des PNG. Damit entfällt die
/qrdata-Route des Panels komplett — die Box erzeugt QR-Codes selbst.
"""

from .qrgen import QrCode


def make_png(text, path, scale=8, border=4):
    """Erzeugt aus `text` ein PNG unter `path`. Rückgabe True/False."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        qr = QrCode.encode_text(text, QrCode.Ecc.MEDIUM)
    except Exception:
        return False
    size = qr.get_size()
    total = size + border * 2
    img = Image.new("RGB", (total * scale, total * scale), (255, 255, 255))
    px = img.load()
    for y in range(size):
        for x in range(size):
            if qr.get_module(x, y):
                for dy in range(scale):
                    for dx in range(scale):
                        px[(x + border) * scale + dx,
                           (y + border) * scale + dy] = (0, 0, 0)
    img.save(path, "PNG")
    return True
