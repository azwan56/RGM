"""
Share Card Generator — creates a phone-portrait PNG image using Pillow.

Usage:
    from utils.share_card import generate_share_card
    png_bytes = generate_share_card(display_name="阿朱碗", period_name="月", report={...})
"""

import io
import os
import hashlib
import math
from typing import Optional

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    raise ImportError("Pillow is required: pip install Pillow")


# ── Card dimensions (phone portrait, good for social sharing) ────────────
CARD_W = 1080
CARD_H = 1920

# ── Font handling ─────────────────────────────────────────────────────────
_FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")
_FONT_PATH = os.path.join(_FONT_DIR, "NotoSansSC-Bold.ttf")
_FONT_REGULAR_PATH = os.path.join(_FONT_DIR, "NotoSansSC-Regular.ttf")

# Google Fonts static CDN URLs (variable font, reliable)
_FONT_URLS = [
    "https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/Variable/OTF/NotoSansCJKsc-VF.otf",
    "https://github.com/googlefonts/noto-cjk/releases/download/Sans2.004/03_NotoSansSC.zip",
]

# System font fallback paths (order matters)
_SYSTEM_FONT_PATHS = [
    # macOS
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/PingFang.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
    # Linux (Render, Ubuntu, etc.)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
]


def _find_system_font() -> str:
    """Find a system-installed Chinese font."""
    for path in _SYSTEM_FONT_PATHS:
        if os.path.isfile(path):
            return path
    return ""


def _ensure_font(path: str) -> str:
    """Find or download a Chinese font. Returns path to the font file."""
    # 1. Already cached locally
    if os.path.isfile(path) and os.path.getsize(path) > 100_000:
        return path

    # 2. Try system fonts first (instant, no download)
    sys_font = _find_system_font()
    if sys_font:
        print(f"[share_card] Using system font: {sys_font}")
        return sys_font

    # 3. Download from CDN
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import urllib.request
    url = _FONT_URLS[0]
    print(f"[share_card] Downloading font from {url} ...")
    try:
        urllib.request.urlretrieve(url, path)
        print(f"[share_card] Font downloaded: {os.path.getsize(path)} bytes")
        return path
    except Exception as e:
        print(f"[share_card] Font download failed: {e}")
        raise


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    """Load a Chinese-capable font at the given size."""
    try:
        # Use bold path as the primary cache location
        path = _ensure_font(_FONT_PATH)
        return ImageFont.truetype(path, size)
    except Exception as e:
        print(f"[share_card] Font load error, using default: {e}")
        return ImageFont.load_default()


def _draw_rounded_rect(draw: ImageDraw.Draw, xy, radius: int, fill=None, outline=None, width: int = 1):
    """Draw a rounded rectangle (works on older Pillow versions too)."""
    x1, y1, x2, y2 = xy
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except AttributeError:
        # Fallback for Pillow < 8.2
        draw.rectangle(xy, fill=fill, outline=outline, width=width)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list:
    """Word-wrap text to fit within max_width pixels."""
    lines = []
    current_line = ""
    for char in text:
        test = current_line + char
        bbox = font.getbbox(test)
        w = bbox[2] - bbox[0]
        if w > max_width and current_line:
            lines.append(current_line)
            current_line = char
        else:
            current_line = test
    if current_line:
        lines.append(current_line)
    return lines


def generate_share_card(
    display_name: str,
    period_name: str,
    report: dict,
    encouragement_override: Optional[str] = None,
) -> bytes:
    """
    Generate a phone-portrait PNG share card (1080x1920).
    Returns raw PNG bytes.
    """
    # ── Extract data ──────────────────────────────────────────────────
    week_stats = report.get("week_stats", {})
    km = week_stats.get("total_km", 0)
    runs = week_stats.get("total_runs", 0)
    score = report.get("weekly_score", "-")
    summary = report.get("summary", "")
    encouragement = encouragement_override or report.get("encouragement", "")
    achievements = report.get("achievements", [])
    
    year = report.get("month_year", None) or report.get("week_year", None)
    if not year:
        from datetime import datetime
        year = datetime.now().year

    # ── Create image with dark gradient background ────────────────────
    img = Image.new("RGB", (CARD_W, CARD_H), "#0a0a0a")
    draw = ImageDraw.Draw(img)

    # Draw a subtle gradient overlay (top-to-bottom)
    for y in range(CARD_H):
        r = int(10 + (y / CARD_H) * 12)
        g = int(10 + (y / CARD_H) * 14)
        b = int(15 + (y / CARD_H) * 20)
        draw.line([(0, y), (CARD_W, y)], fill=(r, g, b))

    # ── Accent stripe at top ──────────────────────────────────────────
    for y in range(6):
        ratio = y / 6
        r = int(59 + ratio * (29 - 59))
        g = int(130 + ratio * (78 - 130))
        b = int(246 + ratio * (216 - 246))
        draw.line([(0, y), (CARD_W, y)], fill=(r, g, b))

    # ── Load fonts ────────────────────────────────────────────────────
    font_title = _load_font(42, bold=True)
    font_name = _load_font(72, bold=True)
    font_stat_num = _load_font(84, bold=True)
    font_stat_unit = _load_font(28, bold=False)
    font_stat_label = _load_font(24, bold=False)
    font_body = _load_font(32, bold=False)
    font_section = _load_font(34, bold=True)
    font_small = _load_font(26, bold=False)
    font_brand = _load_font(36, bold=True)
    font_tagline = _load_font(22, bold=False)
    font_badge = _load_font(26, bold=True)

    # ── Colors ────────────────────────────────────────────────────────
    WHITE = (255, 255, 255)
    BLUE = (59, 130, 246)
    LIGHT_BLUE = (147, 197, 253)
    GOLD = (252, 211, 77)
    GREEN = (74, 222, 128)
    GRAY = (161, 161, 170)
    DIM = (113, 113, 122)
    CARD_BG = (20, 20, 20)

    y_cursor = 50

    # ── Header: RGM branding + year badge ────────────────────────────
    draw.text((72, y_cursor), "RGM 跑团", font=font_title, fill=LIGHT_BLUE)
    
    # Year badge
    year_text = str(year)
    year_bbox = font_badge.getbbox(year_text)
    year_w = year_bbox[2] - year_bbox[0] + 24
    year_h = year_bbox[3] - year_bbox[1] + 16
    badge_x = CARD_W - 72 - year_w
    _draw_rounded_rect(draw, (badge_x, y_cursor, badge_x + year_w, y_cursor + year_h + 8),
                        radius=12, fill=(30, 58, 138))
    draw.text((badge_x + 12, y_cursor + 4), year_text, font=font_badge, fill=(96, 165, 250))

    y_cursor += 56
    draw.text((72, y_cursor), f"{period_name}度训练总结", font=font_small, fill=GRAY)

    y_cursor += 70

    # ── Runner name ───────────────────────────────────────────────────
    draw.text((72, y_cursor), display_name, font=font_name, fill=WHITE)
    y_cursor += 120

    # ── Decorative line ───────────────────────────────────────────────
    draw.line([(72, y_cursor), (CARD_W - 72, y_cursor)], fill=(40, 40, 50), width=2)
    y_cursor += 40

    # ── Stats row (3 columns) ─────────────────────────────────────────
    stats_bg_y = y_cursor
    _draw_rounded_rect(draw, (52, stats_bg_y, CARD_W - 52, stats_bg_y + 200),
                        radius=24, fill=(18, 18, 24))

    col_w = (CARD_W - 104) // 3
    stats = [
        (str(round(km, 1) if isinstance(km, float) else km), "km", "跑量", WHITE),
        (str(runs), "次", "次数", WHITE),
        (str(score), "/10", "AI评分", GOLD),
    ]
    for i, (val, unit, label, color) in enumerate(stats):
        cx = 52 + col_w * i + col_w // 2

        # Value
        val_bbox = font_stat_num.getbbox(val)
        val_w = val_bbox[2] - val_bbox[0]
        unit_bbox = font_stat_unit.getbbox(unit)
        unit_w = unit_bbox[2] - unit_bbox[0]
        total_w = val_w + unit_w + 4

        val_x = cx - total_w // 2
        draw.text((val_x, stats_bg_y + 50), val, font=font_stat_num, fill=color)
        draw.text((val_x + val_w + 4, stats_bg_y + 80), unit, font=font_stat_unit, fill=DIM)

        # Label
        label_bbox = font_stat_label.getbbox(label)
        label_w = label_bbox[2] - label_bbox[0]
        draw.text((cx - label_w // 2, stats_bg_y + 24), label, font=font_stat_label, fill=GRAY)

        # Divider between columns
        if i < 2:
            div_x = 52 + col_w * (i + 1)
            draw.line([(div_x, stats_bg_y + 30), (div_x, stats_bg_y + 170)],
                      fill=(40, 40, 50), width=1)

    y_cursor = stats_bg_y + 230

    # ── Summary section ───────────────────────────────────────────────
    draw.text((72, y_cursor), "📝", font=font_section, fill=WHITE)
    draw.text((120, y_cursor), " 总体评价", font=font_section, fill=WHITE)
    # Blue accent bar
    draw.rectangle([(72, y_cursor + 52), (76, y_cursor + 52 + 4)], fill=BLUE)
    y_cursor += 64

    if summary:
        wrapped = _wrap_text(summary, font_body, CARD_W - 144)
        for i, line in enumerate(wrapped[:6]):  # Limit to 6 lines
            draw.text((72, y_cursor), line, font=font_body, fill=(212, 212, 216))
            y_cursor += 46
        if len(wrapped) > 6:
            draw.text((72, y_cursor), "……", font=font_body, fill=DIM)
            y_cursor += 46

    y_cursor += 20

    # ── Achievements section ──────────────────────────────────────────
    if achievements:
        draw.text((72, y_cursor), "✨", font=font_section, fill=GREEN)
        draw.text((120, y_cursor), " 本期亮点", font=font_section, fill=WHITE)
        y_cursor += 60
        for item in achievements[:3]:
            # Bullet point
            draw.ellipse([(88, y_cursor + 14), (98, y_cursor + 24)], fill=GREEN)
            wrapped = _wrap_text(item, font_body, CARD_W - 180)
            for j, line in enumerate(wrapped[:2]):
                draw.text((112, y_cursor), line, font=font_body, fill=(212, 212, 216))
                y_cursor += 46
            y_cursor += 6
        y_cursor += 10

    # ── Encouragement ─────────────────────────────────────────────────
    if encouragement:
        y_cursor += 10
        _draw_rounded_rect(draw, (52, y_cursor, CARD_W - 52, y_cursor + 120),
                            radius=16, fill=(20, 30, 50))
        enc_wrapped = _wrap_text('"' + encouragement + '"', font_body, CARD_W - 164)
        enc_y = y_cursor + 20
        for line in enc_wrapped[:2]:
            line_bbox = font_body.getbbox(line)
            line_w = line_bbox[2] - line_bbox[0]
            draw.text(((CARD_W - line_w) // 2, enc_y), line, font=font_body, fill=(56, 189, 248))
            enc_y += 46
        y_cursor += 140

    # ── Bottom branding ───────────────────────────────────────────────
    # Pin to bottom
    brand_y = CARD_H - 160

    # Subtle divider
    draw.line([(200, brand_y), (CARD_W - 200, brand_y)], fill=(40, 40, 50), width=1)
    brand_y += 30

    brand_text = "RGM.vanpower.live"
    brand_bbox = font_brand.getbbox(brand_text)
    brand_w = brand_bbox[2] - brand_bbox[0]
    draw.text(((CARD_W - brand_w) // 2, brand_y), brand_text, font=font_brand, fill=BLUE)

    brand_y += 50
    tagline = "智能跑团管理 · AI 教练分析"
    tag_bbox = font_tagline.getbbox(tagline)
    tag_w = tag_bbox[2] - tag_bbox[0]
    draw.text(((CARD_W - tag_w) // 2, brand_y), tagline, font=font_tagline, fill=DIM)

    # ── Export to PNG bytes ────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    print(f"[share_card] Generated card: {len(buf.getvalue())} bytes, {CARD_W}x{CARD_H}")
    return buf.getvalue()
