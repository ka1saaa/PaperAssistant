# -*- coding: utf-8 -*-
"""在 app.js 顶层每 40 行插入 window.__markN 标记，定位顶层抛错位置。"""
import re
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
lines = p.read_text(encoding="utf-8").split("\n")

out = []
mark = 0
for i, line in enumerate(lines):
    stripped = line.strip()
    # 不在字符串/模板内的近似判断：仅对顶层（无缩进）行插标记
    if re.match(r"^(var|const|let|function) ", line) and mark == 0 or True:
        pass
    out.append(line)

# 简化：直接按行号每 60 行插一条（避开缩进非零的行）
out = []
n = 0
for i, line in enumerate(lines):
    out.append(f"window.__mark{n} = {i};")
    n += 1
    out.append(line)
print("标记数:", n)
p.with_name("app_marked.js").write_text("\n".join(out), encoding="utf-8")
