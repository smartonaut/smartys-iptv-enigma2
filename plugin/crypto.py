# -*- coding: utf-8 -*-
"""Smartys IPTV — Nutzer-Passwort-Krypto (Enigma2-Plugin).

PBKDF2-HMAC-SHA256 (310k Iterationen) + AES-256-GCM — exakt kompatibel zum
Backend (backend/crypto.py): gleiche AAD-Form, gleiches KDF-Format, gleiche
Token-Darstellung base64(nonce||ciphertext).

WICHTIG: 'cryptography' ist auf openATV ARM+MIPS via opkg verfügbar
(python3-cryptography, im Feed verifiziert; auf der Testbox bereits
installiert). Das IPK deklariert es als Dependency.
"""
import base64
import json
import os

KDF_ITERATIONS = 310_000

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False


def crypto_available():
    return _CRYPTO_OK


def _aad(player_id):
    """AAD bindet den Ciphertext an genau EINEN Player (identisch Backend)."""
    return b"smartys-iptv-sec:" + (player_id or "").encode("utf-8")


def new_salt():
    return base64.b64encode(os.urandom(16)).decode("ascii")


def derive_key(password, salt_b64):
    if not _CRYPTO_OK:
        raise RuntimeError("python3-cryptography fehlt")
    salt = base64.b64decode(salt_b64)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(), length=32, salt=salt,
        iterations=KDF_ITERATIONS, backend=default_backend())
    return kdf.derive(password.encode("utf-8"))


def encrypt_text(key, plaintext, player_id):
    """Verschlüsselt einen String; Ausgabe base64(nonce||ciphertext)."""
    if plaintext is None:
        return ""
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), _aad(player_id))
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_text(key, token, player_id):
    """Entschlüsselt encrypt_text()-Ausgabe; bei Defekt leerer String."""
    if not token:
        return ""
    try:
        raw = base64.b64decode(token)
        return AESGCM(key).decrypt(raw[:12], raw[12:], _aad(player_id)).decode("utf-8")
    except Exception:
        return ""


def encrypt_provider(key, prov, player_id):
    """Verschlüsselt {server_url, username, password, epg_url} zu JSON."""
    return encrypt_text(key, json.dumps(prov), player_id)


def decrypt_provider(key, cipher, player_id):
    """Entschlüsselt encrypt_provider()-Ausgabe; liefert dict oder None."""
    raw = decrypt_text(key, cipher, player_id)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None
