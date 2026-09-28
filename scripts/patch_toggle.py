# -*- coding: utf-8 -*-
"""pc-hide 改为 pc-toggle 切换式（显示/隐藏自适应）。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

old = '''$("#pc-hide").addEventListener("click", () => {
  window.petAPI?.hide();
  toast("小鱼已隐藏（在「翻译论文」右下角点 👁 唤回）", "info");
});'''
new = '''$("#pc-toggle").addEventListener("click", () => {
  const petEl = document.getElementById("ai-pet");
  const isHidden = petEl && petEl.style.display === "none";
  if (isHidden) {
    window.petAPI?.show();
    toast("小鱼回来啦～", "ok");
  } else {
    window.petAPI?.hide();
    toast("小鱼已隐藏（在左侧「桌宠设置」点「显示小鱼」唤回）", "info");
  }
  syncPetSettingsUI();
});'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("OK")
