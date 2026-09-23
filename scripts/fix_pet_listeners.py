# -*- coding: utf-8 -*-
"""移除桌宠左键打开聊天的两处监听；欢迎语改挂到右键触发的 pet:chat 事件。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
lines = p.read_text(encoding="utf-8").split("\n")

# ---- 删除块 A：点击即切换聊天（6 行） ----
idx_a = next(i for i, l in enumerate(lines)
             if '$("#ai-pet").addEventListener("click"' in l
             and "setEmotion" in lines[i + 2])
del lines[idx_a:idx_a + 6]

# ---- 替换块 B：旧欢迎监听 → pet:chat 触发 ----
s = "\n".join(lines)
start = s.index("// 首次打开时的欢迎语")
end = s.index("});", s.index('"嗨～我是小鱼')) + 3
old_block = s[start:end]
assert "petWelcomed" in old_block and "addEventListener" in old_block

new_block = '''// 首次打开对话面板时的欢迎语（右键桌宠触发）
let petWelcomed = false;
document.addEventListener("pet:chat", () => {
  if (!petWelcomed && !aiChat.classList.contains("hidden")) {
    petWelcomed = true;
    setTimeout(() => addMsg("bot",
      "嗨～我是小鱼 🐳 论文助手的首席问答官！\\n\\n可以问我：\\n- 这个工具怎么用（翻译/批注/图谱…）\\n- 论文里的概念、方法\\n- 或者任何学习上的问题"), 350);
  }
});'''
s = s[:start] + new_block + s[end:]

p.write_text(s, encoding="utf-8")
print("两处监听已处理")
