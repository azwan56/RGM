import hashlib
import hmac
import io
import ipaddress
import json
import os
import secrets
import socket
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, Request

PBKDF2_ITERATIONS = 210_000
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DECOMPRESSED_WORKOUT_BYTES = 25 * 1024 * 1024  # 25 MB

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")

_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: Dict[str, List[float]] = {}

_APPLE_JWKS_LOCK = threading.Lock()
_APPLE_JWKS_CACHE: Dict[str, Any] = {"keys": [], "fetched_at": 0.0}


def is_strict_auth_mode() -> bool:
    """Returns True in production or when RGM_STRICT_AUTH=1 is explicitly enabled."""
    from config import settings
    return settings.ENVIRONMENT.lower() == "production" or os.getenv("RGM_STRICT_AUTH") == "1"


def get_client_ip(request: Optional[Request]) -> str:
    """Extracts the caller IP honoring Nginx X-Real-IP / X-Forwarded-For."""
    if not request:
        return "unknown"
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri:
        return xri
    return getattr(getattr(request, "client", None), "host", None) or "unknown"


def enforce_rate_limit(
    bucket: str,
    key: str,
    max_calls: int,
    window_seconds: int,
    detail: str = "操作过于频繁，请稍后再试",
) -> None:
    """Thread-safe sliding-window rate limiter; raises HTTP 429 on excess."""
    now = time.monotonic()
    composite = f"{bucket}:{key or 'anon'}"
    cutoff = now - max(1, int(window_seconds))
    with _RATE_LIMIT_LOCK:
        # Opportunistic pruning if map grows large
        if len(_RATE_LIMIT_BUCKETS) > 10000:
            stale = [k for k, arr in _RATE_LIMIT_BUCKETS.items() if not arr or arr[-1] < cutoff]
            for k in stale[:5000]:
                _RATE_LIMIT_BUCKETS.pop(k, None)
        arr = _RATE_LIMIT_BUCKETS.get(composite)
        if arr:
            arr = [ts for ts in arr if ts >= cutoff]
        else:
            arr = []
        if len(arr) >= max_calls:
            _RATE_LIMIT_BUCKETS[composite] = arr
            raise HTTPException(status_code=429, detail=detail)
        arr.append(now)
        _RATE_LIMIT_BUCKETS[composite] = arr


def reset_rate_limits(bucket: Optional[str] = None) -> None:
    """Clears rate limit buckets (primarily for test isolation)."""
    with _RATE_LIMIT_LOCK:
        if not bucket:
            _RATE_LIMIT_BUCKETS.clear()
        else:
            prefix = f"{bucket}:"
            for k in [k for k in _RATE_LIMIT_BUCKETS if k.startswith(prefix)]:
                _RATE_LIMIT_BUCKETS.pop(k, None)


def safe_fetch_external_bytes(
    url: str,
    max_bytes: int = MAX_IMAGE_UPLOAD_BYTES,
    timeout: float = 5.0,
) -> Optional[bytes]:
    """
    SSRF-safe external HTTP fetch: validates target host/IP before each hop (max 2 redirects)
    with allow_redirects=False and streams up to max_bytes.
    """
    import requests as _requests

    cur_url = (url or "").strip()
    for _ in range(3):
        if not is_safe_external_url(cur_url):
            return None
        try:
            resp = _requests.get(cur_url, timeout=timeout, allow_redirects=False, stream=True)
        except Exception:
            return None
        if resp.status_code in (301, 302, 303, 307, 308):
            loc = resp.headers.get("Location") or resp.headers.get("location") or ""
            try:
                resp.close()
            except Exception:
                pass
            if not loc:
                return None
            cur_url = urllib.parse.urljoin(cur_url, loc)
            continue
        if resp.status_code != 200:
            try:
                resp.close()
            except Exception:
                pass
            return None
        buf = io.BytesIO()
        total = 0
        try:
            for chunk in resp.iter_content(chunk_size=65536):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    return None
                buf.write(chunk)
            return buf.getvalue()
        except Exception:
            return None
        finally:
            try:
                resp.close()
            except Exception:
                pass
    return None


def _get_apple_jwks_keys() -> List[Dict[str, Any]]:
    import requests as _requests

    now = time.time()
    with _APPLE_JWKS_LOCK:
        if _APPLE_JWKS_CACHE["keys"] and now - _APPLE_JWKS_CACHE["fetched_at"] < 3600:
            return _APPLE_JWKS_CACHE["keys"]
    resp = _requests.get("https://appleid.apple.com/auth/keys", timeout=8)
    resp.raise_for_status()
    keys = (resp.json() or {}).get("keys") or []
    if keys:
        with _APPLE_JWKS_LOCK:
            _APPLE_JWKS_CACHE["keys"] = keys
            _APPLE_JWKS_CACHE["fetched_at"] = now
    return keys


def verify_apple_identity_token(identity_token: str, expected_sub: str) -> Dict[str, Any]:
    """
    Cryptographically verifies an Apple Sign-In identity_token against Apple's JWKS
    (RS256 signature, iss=https://appleid.apple.com, exp, and sub == expected_sub).
    """
    import jwt

    token = (identity_token or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="缺少 Apple identity_token 身份校验凭据")

    try:
        header = jwt.get_unverified_header(token)
    except Exception:
        raise HTTPException(status_code=401, detail="无效的 Apple identity_token 格式")

    kid = header.get("kid")
    alg = header.get("alg") or "RS256"
    if not kid or alg != "RS256":
        raise HTTPException(status_code=401, detail="Apple identity_token 签名算法无效")

    try:
        keys = _get_apple_jwks_keys()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Apple 登录密钥校验服务暂时不可用: {exc}")

    matched_jwk = next((k for k in keys if k.get("kid") == kid), None)
    if not matched_jwk:
        with _APPLE_JWKS_LOCK:
            _APPLE_JWKS_CACHE["fetched_at"] = 0.0
        try:
            keys = _get_apple_jwks_keys()
            matched_jwk = next((k for k in keys if k.get("kid") == kid), None)
        except Exception:
            matched_jwk = None
    if not matched_jwk:
        raise HTTPException(status_code=401, detail="无法匹配 Apple 公钥，请重新授权登录")

    try:
        pub_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matched_jwk))
        allowed_audiences = [
            x.strip()
            for x in (os.getenv("APPLE_CLIENT_IDS", "com.vanpower.rgm").split(","))
            if x.strip()
        ]
        claims = jwt.decode(
            token,
            pub_key,
            algorithms=["RS256"],
            issuer="https://appleid.apple.com",
            options={"verify_aud": False},
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Apple 登录凭证已过期，请重新授权")
    except Exception:
        raise HTTPException(status_code=401, detail="Apple identity_token 验签失败")

    aud = claims.get("aud")
    if allowed_audiences and aud and aud not in allowed_audiences:
        # Allow bundle id prefixes or configured service IDs if customized; fail closed if explicitly mismatched
        if not str(aud).startswith("com.vanpower."):
            raise HTTPException(status_code=401, detail="Apple identity_token 应用标识不匹配")

    sub = str(claims.get("sub") or "").strip()
    if not sub or (expected_sub and sub != expected_sub.strip()):
        raise HTTPException(status_code=401, detail="Apple identity_token 用户标识与请求不一致")
    return claims


def hash_password(password: str) -> str:
    """Hashes a plaintext password with PBKDF2-HMAC-SHA256 and random 128-bit salt."""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("ascii"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    """Verifies a plaintext password against a stored PBKDF2 hash in constant time."""
    if not password or not stored_hash:
        return False
    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        salt = parts[2]
        expected_hex = parts[3]
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("ascii"),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


def is_safe_external_url(url: str) -> bool:
    """
    SSRF guard: allows only public http/https hosts and rejects loopback, RFC1918 private,
    link-local (AWS/GCP metadata 169.254.169.254), and CGNAT/Aliyun ECS metadata (100.100.100.200).
    """
    if not url:
        return False
    try:
        parsed = urllib.parse.urlparse(url.strip())
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").strip().lower()
    if not hostname or hostname in ("localhost", "localhost.localdomain"):
        return False

    try:
        addr_infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except Exception:
        return False

    if not addr_infos:
        return False

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip_obj = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip_obj.is_loopback
            or ip_obj.is_private
            or ip_obj.is_link_local
            or ip_obj.is_multicast
            or ip_obj.is_reserved
            or ip_obj.is_unspecified
            or (isinstance(ip_obj, ipaddress.IPv4Address) and ip_obj in _CGNAT_NET)
        ):
            return False
    return True


def validate_uploaded_image_bytes(
    contents: bytes,
    filename: str = "",
    max_bytes: int = MAX_IMAGE_UPLOAD_BYTES,
) -> str:
    """
    Validates uploaded image size, rejects dangerous extensions (.svg, .html, .xml),
    verifies image magic bytes (JPEG, PNG, GIF, WebP), and returns a safe file extension.
    """
    if not contents:
        raise HTTPException(status_code=400, detail="上传的图片文件为空")
    if len(contents) > max_bytes:
        raise HTTPException(status_code=413, detail=f"图片文件过大，最大支持 {max_bytes // (1024 * 1024)}MB")

    raw_ext = os.path.splitext(filename or "")[1].lower()
    if raw_ext in (".svg", ".svgz", ".html", ".htm", ".xml", ".xhtml", ".js"):
        raise HTTPException(status_code=400, detail="安全拦截：不支持上传 SVG 或脚本格式文件，请上传 JPG/PNG/WebP 图片")

    if contents.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if contents.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if contents.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(contents) >= 12 and contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        return ".webp"

    raise HTTPException(status_code=400, detail="仅支持有效的 JPG、PNG、WebP 或 GIF 图片格式")


def safe_decompress_gzip(raw: bytes, max_bytes: int = MAX_DECOMPRESSED_WORKOUT_BYTES) -> bytes:
    """Streams gzip decompression with a strict byte ceiling to prevent Zip/Gzip memory bombs."""
    decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
    out = io.BytesIO()
    chunk_size = 65536
    offset = 0
    total_out = 0
    while offset < len(raw):
        chunk = raw[offset : offset + chunk_size]
        offset += chunk_size
        remaining = max_bytes - total_out + 1
        data = decompressor.decompress(chunk, remaining)
        total_out += len(data)
        if total_out > max_bytes or decompressor.unconsumed_tail:
            raise HTTPException(
                status_code=413,
                detail=f"运动文件解压后体积超过安全上限 ({max_bytes // (1024 * 1024)}MB)",
            )
        out.write(data)
    tail = decompressor.flush()
    total_out += len(tail)
    if total_out > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"运动文件解压后体积超过安全上限 ({max_bytes // (1024 * 1024)}MB)",
        )
    out.write(tail)
    return out.getvalue()


def safe_parse_xml_text(text: str) -> ET.Element:
    """Rejects XML DTD / ENTITY declarations (Billion Laughs / XXE) before ElementTree parsing."""
    head_upper = text[:4096].upper()
    if "<!DOCTYPE" in head_upper or "<!ENTITY" in head_upper:
        raise HTTPException(status_code=400, detail="安全拦截：XML 运动文件包含禁止的 DOCTYPE/ENTITY 声明")
    return ET.fromstring(text)
