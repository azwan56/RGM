import os
import base64
import hashlib
from typing import Optional
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

PII_PREFIX = "enc:v1:"

def encrypt_pii(plaintext: Optional[str]) -> Optional[str]:
    """Encrypts a sensitive PII string (name, DOB, ID card, phone) with AES-256-GCM and enc:v1: prefix."""
    if plaintext is None:
        return None
    s = str(plaintext).strip()
    if not s:
        return ""
    if s.startswith(PII_PREFIX):
        return s  # already encrypted
    enc = encrypt_string(s)
    return f"{PII_PREFIX}{enc}" if enc else s

def decrypt_pii(val: Optional[str]) -> Optional[str]:
    """Decrypts a sensitive PII string if prefixed with enc:v1:, otherwise returns original string for backward compatibility."""
    if val is None:
        return None
    s = str(val).strip()
    if s.startswith(PII_PREFIX):
        raw = s[len(PII_PREFIX):]
        dec = decrypt_string(raw)
        return dec if dec else s
    return s

def mask_name(name: Optional[str]) -> str:
    """Masks real name for privacy (e.g. 陈晓韵 -> 陈*韵, 张三 -> 张*, Alex -> A**x)."""
    if not name:
        return "跑者"
    val = decrypt_pii(str(name).strip()) or ""
    n = len(val)
    if n <= 1:
        return val
    elif n == 2:
        return val[0] + "*"
    elif n == 3:
        return val[0] + "*" + val[-1]
    else:
        return val[0] + "*" * (n - 2) + val[-1]

def mask_id_card(id_card: Optional[str]) -> str:
    """Masks national ID card number (e.g. 310101199001011234 -> 310101********1234)."""
    if not id_card:
        return ""
    val = decrypt_pii(str(id_card).strip()) or ""
    n = len(val)
    if n <= 8:
        return "*" * n
    return val[:6] + "*" * (n - 10 if n >= 10 else n - 6) + val[-4:]

def mask_phone(phone: Optional[str]) -> str:
    """Masks mobile phone number (e.g. 13812345678 -> 138****5678)."""
    if not phone:
        return ""
    val = decrypt_pii(str(phone).strip()) or ""
    if len(val) == 11 and val.isdigit():
        return val[:3] + "****" + val[7:]
    elif len(val) > 4:
        return val[:2] + "****" + val[-2:]
    return val

def compute_age_group(dob: Optional[str]) -> str:
    """Computes age group based on birth year.
    >= 50: 大师组 (Masters)
    40-49: 壮年组
    30-39: 中坚组
    < 30: 青年组
    """
    if not dob:
        return "未填"
    val = decrypt_pii(str(dob).strip())
    if not val:
        return "未填"
    try:
        from datetime import datetime
        year_str = val[:4]
        if len(year_str) == 4 and year_str.isdigit():
            birth_year = int(year_str)
            cur_year = datetime.utcnow().year
            age = cur_year - birth_year
            if age >= 50:
                return "大师组"
            elif age >= 40:
                return "壮年组"
            elif age >= 30:
                return "中坚组"
            else:
                return "青年组"
    except Exception:
        pass
    return "未知"
