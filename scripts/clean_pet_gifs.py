# -*- coding: utf-8 -*-
"""清理桌宠 GIF 边缘黑线：腐蚀 alpha 切掉脏边 → 平滑 → 转 WebP 动图（完整 alpha）。"""
from pathlib import Path
from PIL import Image, ImageFilter

PET_DIR = Path(__file__).resolve().parent.parent / "app" / "static" / "img" / "pet"
STATES = ["idle", "waving", "waiting", "running", "jumping", "failed"]


def clean_frame(frame_rgba, erode=7):
    """腐蚀 alpha 去除边缘脏线，再轻微模糊让边缘平滑。"""
    r, g, b, a = frame_rgba.split()
    a = a.filter(ImageFilter.MinFilter(erode))          # 收缩 alpha，切掉脏边缘
    a = a.filter(ImageFilter.GaussianBlur(1.1))         # 边缘平滑过渡
    # 半透明区域残留的暗色像素：把低 alpha 像素的颜色提亮去污
    frame_rgba.putalpha(a)
    return frame_rgba


for name in STATES:
    src = PET_DIR / f"{name}.gif"
    im = Image.open(src)
    n = getattr(im, "n_frames", 1)
    durations, frames = [], []
    for i in range(n):
        im.seek(i)
        durations.append(im.info.get("duration", 100))
        frame = im.convert("RGBA")
        frames.append(clean_frame(frame))

    out = PET_DIR / f"{name}.webp"
    frames[0].save(
        out, save_all=True, append_images=frames[1:],
        duration=durations, loop=0, method=4, quality=90,
    )
    kb = out.stat().st_size // 1024
    print(f"{name:9} {n}帧 -> {out.name} ({kb}KB)")

print("全部完成")
