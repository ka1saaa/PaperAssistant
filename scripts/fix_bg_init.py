# -*- coding: utf-8 -*-
"""在 app.js 文件末尾补回背景初始化调用。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

if "applyBg();\nbindBgControls();" in s and "背景初始化" in s:
    print("已存在，跳过")
else:
    s = s.rstrip("\n") + "\n\n// 背景初始化（置于文件末尾：bgCfg/applyBg 均已就绪）\napplyBg();\nbindBgControls();\n"
    p.write_text(s, encoding="utf-8")
    print("已补回末尾调用")
