# -*- coding: utf-8 -*-
"""修复 app.js 中被真实换行破坏的 JS 字符串。"""
import re
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")
print("出现次数:", s.count("嗨～我是小深"))

fixed = (
    '"嗨～我是小深 🐳 论文助手的首席问答官！\\n\\n'
    '可以问我：\\n- 这个工具怎么用（翻译/批注/图谱…）\\n'
    '- 论文里的概念、方法\\n- 或者任何学习上的问题"'
)
pattern = re.compile(r'"嗨～我是小深[^"]*?"', re.DOTALL)
s2, n = pattern.subn(lambda m: fixed, s)
print("替换块数:", n)
p.write_text(s2, encoding="utf-8")
