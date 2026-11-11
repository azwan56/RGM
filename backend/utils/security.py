import hashlib
import hmac
import io
import ipaddress
import os
import secrets
import socket
import urllib.parse
import xml.etree.ElementTree as ET
import zlib
from typing import Optional
from fastapi import HTTPException

PBKDF2_ITERATIONS = 210_000
MAX_IMAGE_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_DECOMPRESSED_WORKOUT_BYTES = 25 * 1024 * 1024  # 25 MB

_CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")


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
