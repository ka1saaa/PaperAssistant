# -*- coding: utf-8 -*-
"""workerSrc 指向本地 vendor。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")
old = '"https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";'
new = '"/static/vendor/pdf.worker.min.js";'
assert old in s, "未找到 CDN worker 地址"
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("worker 本地化完成")
