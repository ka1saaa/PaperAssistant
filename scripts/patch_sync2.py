# -*- coding: utf-8 -*-
"""syncPetSettingsUI 补充：同步显示/隐藏切换按钮的文字与图标。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
lines = p.read_text(encoding="utf-8").split("\n")

# 定位 syncPetSettingsUI 内 "$("#pc-calm").checked" 行，在其后插入同步逻辑
idx = next(i for i, l in enumerate(lines) if '"#pc-calm").checked' in l)
insert = [
    '  const petEl = document.getElementById("ai-pet");',
    '  const isHidden = petEl && petEl.style.display === "none";',
    '  const toggleText = document.getElementById("pc-toggle-text");',
    '  const toggleIcon = document.getElementById("pc-toggle");',
    '  if (toggleText) toggleText.textContent = isHidden ? "显示小鱼" : "隐藏小鱼";',
    '  if (toggleIcon) {',
    '    const ic = toggleIcon.querySelector("i");',
    '    ic.className = isHidden ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";',
    '  }',
]
lines[idx + 1:idx + 1] = insert
p.write_text("\n".join(lines), encoding="utf-8")
print("OK")
