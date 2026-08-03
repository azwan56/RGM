"""
Credential Encryption Utility
Encrypts and decrypts sensitive user tokens/passwords (e.g., Garmin credentials)
using AES-CBC via pycryptodome with a server-side secret key fallback.
"""

import os
import base64
import hashlib
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

def _get_key() -> bytes:
    secret = os.getenv("ENCRYPTION_KEY") or os.getenv("ADMIN_SECRET") or "rgm_default_secret_key_change_me_in_prod"
    return hashlib.sha256(secret.encode("utf-8")).digest()

def encrypt_string(plaintext: str) -> str:
    """Encrypts a plaintext string into a base64 encoded string with IV."""
    if not plaintext:
        return ""
    key = _get_key()
    cipher = AES.new(key, AES.MODE_CBC)
    ciphertext = cipher.encrypt(pad(plaintext.encode("utf-8"), AES.block_size))
    # Combine IV + Ciphertext
    combined = cipher.iv + ciphertext
    return base64.b64encode(combined).decode("utf-8")

def decrypt_string(encrypted_str: str) -> str:
    """Decrypts a base64 encoded IV+ciphertext string back to plaintext."""
    if not encrypted_str:
        return ""
    try:
        data = base64.b64decode(encrypted_str.encode("utf-8"))
        if len(data) < AES.block_size:
            return ""
        key = _get_key()
        iv = data[:AES.block_size]
        ciphertext = data[AES.block_size:]
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_plaintext = cipher.decrypt(ciphertext)
        return unpad(padded_plaintext, AES.block_size).decode("utf-8")
    except Exception as e:
        print(f"[encryption] Decryption error: {e}")
        return ""
