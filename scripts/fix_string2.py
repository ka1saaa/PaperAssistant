# -*- coding: utf-8 -*-
"""重写 petWelcomed 的 setTimeout 语句（含正确的 \\n 转义）。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
lines = p.read_text(encoding="utf-8").split("\n")

NL = chr(92) + "n"          # 反斜杠 n 两个字符
start = next(i for i, l in enumerate(lines) if 'setTimeout(() => addMsg("bot"' in l)
end = next(i for i in range(start, len(lines)) if "350);" in lines[i])

js = (
    'setTimeout(() => addMsg("bot", "嗨～我是小深 🐳 论文助手的首席问答官！'
    + NL + NL + '可以问我：' + NL
    + '- 这个工具怎么用（翻译/批注/图谱…）' + NL
    + '- 论文里的概念、方法' + NL
    + '- 或者任何学习上的问题"), 350);'
)
lines[start:end + 1] = [js]
p.write_text("\n".join(lines), encoding="utf-8")
print("重写完成")
