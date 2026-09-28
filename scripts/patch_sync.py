# -*- coding: utf-8 -*-
"""syncPetSettingsUI 补充：同步显示/隐藏切换按钮的文字与图标。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

old = '''  $("#pc-quiet").checked = !!c.quiet;
  $("#pc-calm").checked = !!c.calm;
}'''
new = '''  $("#pc-quiet").checked = !!c.quiet;
  $("#pc-calm").checked = !!c.calm;
  const petEl = document.getElementById("ai-pet");
  const isHidden = petEl && petEl.style.display === "none";
  const toggleText = document.getElementById("pc-toggle-text");
  const toggleIcon = $("#pc-toggle").querySelector("i");
  if (toggleText) toggleText.textContent = isHidden ? "显示小鱼" : "隐藏小鱼";
  if (toggleIcon) toggleIcon.className = isHidden ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
}'''
assert old in s, "sync 块未找到"
# 只替换 syncPetSettingsUI 内的那一处（pc-calm 行 + 闭括号组合唯一性由上下文保证）
idx = s.index("function syncPetSettingsUI")
seg = s[idx:]
seg2 = seg.replace(old.strip("  \n"), new.strip(), 1)
# old/new 含缩进，直接在 seg 中替换第一个出现
assert new.strip()[4:] in seg or True
s = s[:idx] + seg2 + s[idx + len(old.strip("  \n")):] if False else s
# 上一行防御性代码不使用；执行精确替换
s = p.read_text(encoding="utf-8")
seg_start = s.index("function syncPetSettingsUI")
tail = s[seg_start:]
assert old in tail, "sync 块仍未找到"
tail = tail.replace(old, new, 1)
s = s[:seg_start] + tail
p.write_text(s, encoding="utf-8")
print("OK")
