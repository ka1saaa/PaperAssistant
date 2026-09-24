# -*- coding: utf-8 -*-
"""应用图标 v2：品牌渐变圆角方块 + 2D 鲸鱼女仆圆形头像徽章 + 星光。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024
R = 210
SRC = Path(__file__).resolve().parent.parent / "app" / "static" / "img" / "deepseek-mascot.jpg"


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---- 渐变圆角底 ----
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
base = Image.new("RGBA", (S, S))
bd = ImageDraw.Draw(base)
c1, c2 = (72, 101, 242), (150, 108, 255)
for y in range(S):
    t = min(1, max(0, (y + S * 0.35) / (S * 1.7)))
    bd.line([(0, y), (S, y)], fill=lerp(c1, c2, t))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=R, fill=255)
img.paste(base, (0, 0), mask)

# ---- 星光（画在头像下层，之后头像会盖住中间） ----
def sparkle(cx4, cy4, r, alpha):
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    pts = [(0, -r), (r * 0.28, -r * 0.28), (r, 0), (r * 0.28, r * 0.28),
           (0, r), (-r * 0.28, r * 0.28), (-r, 0), (-r * 0.28, -r * 0.28)]
    ImageDraw.Draw(layer).polygon([(cx4 + x, cy4 + y) for x, y in pts],
                                  fill=(255, 255, 255, alpha))
    img.alpha_composite(layer)

sparkle(180, 210, 30, 220)
sparkle(850, 330, 38, 240)
sparkle(820, 760, 26, 190)
sparkle(190, 720, 22, 170)

# ---- 中央圆形头像徽章（2D 鲸鱼女仆） ----
BADGE = 660                       # 头像直径
bx = (S - BADGE) // 2
by = 150
mascot = Image.open(SRC).convert("RGB")

# 头像源裁剪：取人物头部与上半身（源 575×575，人物主体在中上部）
mw, mh = mascot.size
ch = int(mh * 0.62)               # 裁剪高度
crop = mascot.crop((0, int(mh * 0.03), mw, int(mh * 0.03) + ch))
crop = crop.resize((BADGE, BADGE), Image.LANCZOS)

# 圆形遮罩
circle = Image.new("L", (BADGE, BADGE), 0)
ImageDraw.Draw(circle).ellipse([0, 0, BADGE - 1, BADGE - 1], fill=255)
circle = circle.filter(ImageFilter.GaussianBlur(1))

# 白色描边环（比头像大一点）
ring_w = 22
ring = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(ring).ellipse(
    [bx - ring_w, by - ring_w, bx + BADGE + ring_w, by + BADGE + ring_w],
    fill=(255, 255, 255, 255))
img.paste(ring, (0, 0), ring)

# 头像外圈白色描边
stroke_w = 14
stroke = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(stroke).ellipse(
    [bx - stroke_w, by - stroke_w, bx + BADGE + stroke_w, by + BADGE + stroke_w],
    outline=(255, 255, 255, 255), width=stroke_w)
img.alpha_composite(stroke)

img.paste(crop, (bx, by), circle)

# 头像底部渐变融入背景（让徽章有悬浮感）
fade = Image.new("RGBA", (S, S), (0, 0, 0, 0))
fd = ImageDraw.Draw(fade)
for i in range(50):
    t = i / 50
    fd.line([(bx, by + BADGE - 50 + i, ), (bx + BADGE, by + BADGE - 50 + i)],
            fill=(72, 101, 242, int(120 * t)))
img.alpha_composite(fade)

# ---- 圆角裁切输出 ----
final_mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(final_mask).rounded_rectangle([0, 0, S - 1, S - 1], radius=R, fill=255)
r_, g_, b_, a_ = img.split()
img = Image.composite(img, Image.new("RGBA", (S, S), (0, 0, 0, 0)), final_mask)

out = Path(__file__).resolve().parent.parent
img.save(out / "icon.png")
img.save(out / "icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
prev = Image.new("RGBA", (S + 60, S + 60), (240, 240, 244, 255))
prev.alpha_composite(img, (30, 30))
prev.convert("RGB").save(out / "testdata" / "icon_preview2.png")
print("icon v2 生成完成")
