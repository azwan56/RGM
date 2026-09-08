import os
import base64
import hashlib
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from config import settings

def _get_key() -> bytes:
    # Derives a consistent 32-byte key from settings.SECRET_KEY
    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()

def encrypt_string(plaintext: str) -> str:
    """Encrypts a string using AES-256-GCM and returns a base64 encoded string with nonce."""
    if not plaintext:
        return ""
    key = _get_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # Pack nonce + ciphertext
    payload = nonce + ciphertext
    return base64.b64encode(payload).decode("utf-8")

def decrypt_string(encrypted_b64: str) -> str:
    """Decrypts a base64 encoded AES-256-GCM string."""
    if not encrypted_b64:
        return ""
    try:
        payload = base64.b64decode(encrypted_b64.encode("utf-8"))
        if len(payload) < 12:
            return ""
        nonce = payload[:12]
        ciphertext = payload[12:]

        candidate_keys = [
            settings.SECRET_KEY,
            "rgm-cn-secret-encryption-key-for-garmin-pwd-32!",
            "rgm-cn-secret-encryption-key-must-be-32-chars-long!!",
            "rgm-cn-secret-encryption-key-32ch!",
        ]
        for candidate in candidate_keys:
            if not candidate:
                continue
            try:
                key = hashlib.sha256(candidate.encode()).digest()
                aesgcm = AESGCM(key)
                decrypted = aesgcm.decrypt(nonce, ciphertext, None)
                return decrypted.decode("utf-8")
            except Exception:
                continue
        return ""
    except Exception as e:
        return ""
