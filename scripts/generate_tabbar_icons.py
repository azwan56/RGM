from PIL import Image, ImageDraw
import os

ICON_SIZE = 81
INACTIVE_COLOR = (161, 161, 170, 255)  # #a1a1aa (Zinc-400)
ACTIVE_COLOR = (252, 76, 2, 255)       # #fc4c02 (RGM Orange)
# 明亮主题（Volt / Trail）图标：与 styles/theme.css 的文字三级色一致
LIGHT_INACTIVE = (75, 86, 103, 255)    # #4B5667  --rgm-text-3
LIGHT_ACTIVE_VOLT = (17, 19, 23, 255)  # #111317  --rgm-text（荧光绿不能作前景色，用深炭灰）
LIGHT_ACTIVE_TRAIL = (255, 85, 0, 255) # #FF5500  Trail 品牌色

def create_canvas():
    return Image.new("RGBA", (ICON_SIZE, ICON_SIZE), (0, 0, 0, 0))

# 1. Home / Dashboard (Gauge / Speedometer / Home shape)
def draw_home(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # Draw roof
    draw.polygon([(40, 16), (18, 38), (26, 38), (26, 64), (54, 64), (54, 38), (62, 38)], outline=color, width=4)
    # Draw door
    draw.rectangle([(34, 46), (46, 64)], outline=color, width=4)
    return img

# 2. Coach / Canova AI (Chat bubble with lightning/sparkle)
def draw_coach(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # Chat rounded rect
    draw.rounded_rectangle([(16, 18), (64, 52)], radius=12, outline=color, width=4)
    # Little tail
    draw.polygon([(26, 52), (26, 64), (38, 52)], fill=color)
    # Star / Sparkle in center
    draw.line([(40, 26), (40, 44)], fill=color, width=3)
    draw.line([(31, 35), (49, 35)], fill=color, width=3)
    return img

# 3. Analysis / Physiological Metrics (Bar chart + Trend)
def draw_analysis(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # 3 bars of increasing heights
    draw.rounded_rectangle([(18, 44), (28, 64)], radius=3, fill=color)
    draw.rounded_rectangle([(35, 30), (45, 64)], radius=3, fill=color)
    draw.rounded_rectangle([(52, 18), (62, 64)], radius=3, fill=color)
    return img

# 4. Team / Running Club (Trophy / Flag)
def draw_team(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # Trophy cup
    draw.rounded_rectangle([(24, 18), (56, 42)], radius=8, outline=color, width=4)
    # Handles
    draw.arc([(14, 22), (28, 38)], 90, 270, fill=color, width=4)
    draw.arc([(52, 22), (66, 38)], 270, 90, fill=color, width=4)
    # Stem & base
    draw.line([(40, 42), (40, 56)], fill=color, width=4)
    draw.rounded_rectangle([(26, 56), (54, 62)], radius=2, fill=color)
    return img

# 5. Profile / Runner (User circle + body)
def draw_profile(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # Head
    draw.ellipse([(30, 16), (50, 36)], outline=color, width=4)
    # Body arc
    draw.arc([(18, 40), (62, 78)], 180, 0, fill=color, width=4)
    draw.line([(18, 59), (18, 64)], fill=color, width=4)
    draw.line([(62, 59), (62, 64)], fill=color, width=4)
    return img

# 6. Training (训练 = 课表 + 诊断 + 数据分析): bar chart + rising trend arrow
def draw_train(color):
    img = create_canvas()
    draw = ImageDraw.Draw(img)
    # Baseline
    draw.line([(14, 66), (66, 66)], fill=color, width=4)
    # 3 hollow bars
    draw.rounded_rectangle([(18, 48), (28, 64)], radius=3, outline=color, width=4)
    draw.rounded_rectangle([(35, 38), (45, 64)], radius=3, outline=color, width=4)
    draw.rounded_rectangle([(52, 30), (62, 64)], radius=3, outline=color, width=4)
    # Rising trend line with arrow head
    draw.line([(16, 36), (32, 24), (44, 28), (62, 12)], fill=color, width=4, joint="curve")
    draw.polygon([(66, 8), (54, 11), (63, 20)], fill=color)
    return img

# ──────────────────────────────────────────────────────────────
# iOS App 同款风格图标（与 ios/RGM/Views/MainTabView.swift 的 Tab 图标造型一致）
# SF Symbols 授权不允许在非 Apple 平台使用，这里按相同造型自行绘制。
# 以 4 倍尺寸绘制后缩小，获得平滑抗锯齿边缘。
# ──────────────────────────────────────────────────────────────
SS = 4
BIG = ICON_SIZE * SS  # 324
CLEAR = (0, 0, 0, 0)


def _finish(img):
    return img.resize((ICON_SIZE, ICON_SIZE), Image.LANCZOS)


def _half_ellipse(draw, box, fill):
    """上半个椭圆（肩膀轮廓）"""
    draw.pieslice(box, 180, 360, fill=fill)


# 首页：仪表盘（gauge.with.dots.needle.bottom.50percent）
def draw_ios_home(color):
    img = Image.new("RGBA", (BIG, BIG), CLEAR)
    d = ImageDraw.Draw(img)
    cx, cy, r = 162, 166, 128
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=24)
    # 刻度点（上半圈）
    import math
    for ang in (160, 195, 230, 270, 310, 345, 20):
        rad = math.radians(ang)
        px, py = cx + 84 * math.cos(rad), cy + 84 * math.sin(rad)
        d.ellipse([px - 11, py - 11, px + 11, py + 11], fill=color)
    # 指针：从底部中心指向正上方（50%）
    d.polygon([(cx - 15, cy + 70), (cx + 15, cy + 70), (cx + 5, cy - 40), (cx - 5, cy - 40)], fill=color)
    d.ellipse([cx - 24, cy + 52, cx + 24, cy + 100], fill=color)
    return _finish(img)


# 训练：大脑侧脸（brain.head.profile）
def draw_ios_train(color):
    img = Image.new("RGBA", (BIG, BIG), CLEAR)
    d = ImageDraw.Draw(img)
    # 头颅
    d.ellipse([70, 28, 290, 238], fill=color)
    # 脸部轮廓（朝左）+ 脖子
    d.polygon([
        (96, 92), (78, 140), (46, 196), (74, 206), (66, 226), (78, 238),
        (74, 256), (100, 268), (140, 266), (146, 304), (262, 304), (266, 230),
    ], fill=color)
    # 镂空大脑：多个圆的并集做成「云朵」轮廓线，再加中间脑沟
    lobes = [(150, 108, 34), (196, 92, 38), (240, 116, 32), (236, 160, 30), (190, 170, 34), (146, 154, 32)]
    stroke = 13
    for x, y, rr in lobes:
        d.ellipse([x - rr - stroke, y - rr - stroke, x + rr + stroke, y + rr + stroke], fill=CLEAR)
    for x, y, rr in lobes:
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=color)
    # 中间一道 S 形脑沟（左右半球分界）
    d.arc([168, 70, 216, 132], 270, 90, fill=CLEAR, width=12)
    d.arc([164, 128, 212, 192], 90, 270, fill=CLEAR, width=12)
    return _finish(img)


# 跑团：三人（person.3.sequence）
def draw_ios_team(color):
    img = Image.new("RGBA", (BIG, BIG), CLEAR)
    d = ImageDraw.Draw(img)
    # 后排两人
    for cx in (78, 246):
        d.ellipse([cx - 40, 82, cx + 40, 162], fill=color)
        _half_ellipse(d, [cx - 66, 184, cx + 66, 352], color)
    # 前排中间人：先挖出一圈间隙，再填充
    gap = 16
    d.ellipse([162 - 54 - gap, 60 - gap, 162 + 54 + gap, 168 + gap], fill=CLEAR)
    _half_ellipse(d, [162 - 92 - gap, 186 - gap, 162 + 92 + gap, 394 + gap], CLEAR)
    d.ellipse([162 - 54, 60, 162 + 54, 168], fill=color)
    _half_ellipse(d, [162 - 92, 186, 162 + 92, 394], color)
    # 底部统一切平
    d.rectangle([0, 292, BIG, BIG], fill=CLEAR)
    return _finish(img)


# 我的：圆形头像（person.crop.circle.fill）
def draw_ios_profile(color):
    img = Image.new("RGBA", (BIG, BIG), CLEAR)
    d = ImageDraw.Draw(img)
    c, r = 162, 136
    d.ellipse([c - r, c - r, c + r, c + r], fill=color)
    # 镂空人像
    d.ellipse([c - 52, 70, c + 52, 174], fill=CLEAR)
    _half_ellipse(d, [c - 100, 200, c + 100, 400], CLEAR)
    # 补回外圈细边
    d.ellipse([c - r, c - r, c + r, c + r], outline=color, width=20)
    return _finish(img)


out_dir = os.path.join(os.path.dirname(__file__), "..", "miniapp", "src", "static", "tabbar")
os.makedirs(out_dir, exist_ok=True)

icons = {
    # 当前 4 个 Tab 使用 iOS 同款造型
    "home": draw_ios_home,
    "train": draw_ios_train,
    "team": draw_ios_team,
    "profile": draw_ios_profile,
    # 旧版图标（已不在 Tab 使用，保留以便回退）
    "coach": draw_coach,
    "analysis": draw_analysis,
}

# 用法: python3 generate_tabbar_icons.py [name ...]   不带参数则生成全部
import sys
selected = sys.argv[1:] or list(icons.keys())

for name in selected:
    drawer = icons[name]
    img_inactive = drawer(INACTIVE_COLOR)
    img_inactive.save(os.path.join(out_dir, f"{name}.png"), "PNG")
    
    img_active = drawer(ACTIVE_COLOR)
    img_active.save(os.path.join(out_dir, f"{name}-active.png"), "PNG")

    light_dir = os.path.join(out_dir, "light")
    os.makedirs(light_dir, exist_ok=True)
    drawer(LIGHT_INACTIVE).save(os.path.join(light_dir, f"{name}.png"), "PNG")
    drawer(LIGHT_ACTIVE_VOLT).save(os.path.join(light_dir, f"{name}-active-volt.png"), "PNG")
    drawer(LIGHT_ACTIVE_TRAIL).save(os.path.join(light_dir, f"{name}-active-trail.png"), "PNG")

print("Generated tab bar icons successfully in:", out_dir, selected)
