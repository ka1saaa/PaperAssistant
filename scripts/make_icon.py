"""生成应用图标 icon.ico：蓝紫渐变圆角方块 + 白色「译」字。"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# 圆角方块 + 对角渐变（手绘横向渐变近似）
r = 52
for y in range(SIZE):
    t = y / SIZE
    color = (int(91 + (143 - 91) * t), int(124 + (107 - 124) * t), int(250 + (255 - 250) * t), 255)
    draw.line([(0, y), (SIZE, y)], fill=color)

# 用遮罩把渐变裁成圆角
mask = Image.new("L", (SIZE, SIZE), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, SIZE - 1, SIZE - 1], radius=r, fill=255)
img.putalpha(mask)

# 白色「译」字
font_path = Path(r"C:\Windows\Fonts\msyh.ttc")
font = ImageFont.truetype(str(font_path), 148)
bbox = draw.textbbox((0, 0), "译", font=font)
w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
draw.text(((SIZE - w) / 2 - bbox[0], (SIZE - h) / 2 - bbox[1]), "译",
          font=font, fill=(255, 255, 255, 255))

img.save("icon.ico", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
img.save("icon.png")
print("icon.ico / icon.png 生成完成")
