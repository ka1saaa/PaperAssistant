# -*- coding: utf-8 -*-
"""清理误删监听后残留的孤儿行。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

orphan = '''    $("#pet-bubble").classList.remove("show");
  }
});
$("#ai-close")'''
fix = '''$("#ai-close")'''
assert orphan in s, "孤儿代码段未找到"
s = s.replace(orphan, fix, 1)
p.write_text(s, encoding="utf-8")
print("孤儿行已清理")
