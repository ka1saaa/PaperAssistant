# -*- coding: utf-8 -*-
"""pet.js 改版：
- 左键点击 = 互动（戳一戳）
- 右键点击 = 打开对话面板
- 支持配置：尺寸缩放 / 不透明度 / 安静模式 / 减少动态 / 显示隐藏
- 配置持久化 localStorage("pet-cfg")，对外暴露 window.petAPI.applyConfig(cfg)
"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "pet.js"
s = p.read_text(encoding="utf-8")

# 1) 构造函数加载配置
old = '''    constructor(host) {
      this.host = host;
      this.img = document.createElement("img");
      this.img.alt = "小鱼";
      this.img.draggable = false;
      host.prepend(this.img);

      this.state = "idle";
      this.setState("idle", true);

      this.drag = { on: false, moved: 0 };
      this._bind();
      this._restore();'''
new = '''    constructor(host) {
      this.host = host;
      this.img = document.createElement("img");
      this.img.alt = "小鱼";
      this.img.draggable = false;
      host.prepend(this.img);

      this.state = "idle";
      this.setState("idle", true);

      this.drag = { on: false, moved: 0 };
      this._bind();
      this._restore();

      // 用户配置：scale 尺寸 / opacity 透明度 / quiet 安静模式 / calm 减少动态
      this.cfg = { scale: 1, opacity: 1, quiet: false, calm: false };
      try { Object.assign(this.cfg, JSON.parse(localStorage.getItem("pet-cfg") || "{}")); } catch { }
      this._applyCfg();
      // 隐藏状态恢复
      try {
        const hid = localStorage.getItem("pet-hidden") === "1";
        this.host.style.display = hid ? "none" : "";
      } catch { }
    }

    applyConfig(cfg) {
      Object.assign(this.cfg, cfg || {});
      try { localStorage.setItem("pet-cfg", JSON.stringify(this.cfg)); } catch { }
      this._applyCfg();
    }

    _applyCfg() {
      const c = this.cfg;
      this.host.style.transform = `scale(${c.scale})`;
      this.host.style.transformOrigin = "bottom right";
      this.host.style.opacity = c.opacity;
      this.host.classList.toggle("pet-calm", !!c.calm);
    }

    show() {
      this.host.style.display = "";
      try { localStorage.setItem("pet-hidden", "0"); } catch { }
    }
    hide() {
      this.host.style.display = "none";
      try { localStorage.setItem("pet-hidden", "1"); } catch { }
    }
    resetPos() {
      this.host.style.left = "";
      this.host.style.top = "";
      this.host.style.right = "30px";
      this.host.style.bottom = "8px";
      this._save();
    }'''
assert old in s
s = s.replace(old, new, 1)

# 2) 互动与安静模式：pointerup 点击分支
old2 = '''      el.addEventListener("pointerup", () => {
        this.drag.on = false;
        if (this.drag.moved < 6) {                       // 戳一戳
          this.setState("jumping");
          this.say(POKE_WORDS[Math.floor(Math.random() * POKE_WORDS.length)]);
          this._backToIdle(2400);
        } else {
          this._save();
          this._backToIdle(1500);
        }
      });'''
new2 = '''      el.addEventListener("pointerup", (e) => {
        this.drag.on = false;
        if (this.drag.moved < 6) {                       // 左键点击 = 互动
          this.setState("jumping");
          if (!this.cfg.quiet) {
            this.say(POKE_WORDS[Math.floor(Math.random() * POKE_WORDS.length)]);
          }
          this._backToIdle(2400);
        } else {
          this._save();
          this._backToIdle(1500);
        }
      });
      // 右键 = 打开对话面板
      el.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();
        document.dispatchEvent(new CustomEvent("pet:chat"));
      });'''
assert old2 in s
s = s.replace(old2, new2, 1)

# 3) 安静模式：say 静默；减少动态：小剧场关闭 + 动画幅度减小
old3 = '''    say(text) {
      const b = document.getElementById("pet-bubble");
      if (!b) return;'''
new3 = '''    say(text) {
      if (this.cfg.quiet) return;
      const b = document.getElementById("pet-bubble");
      if (!b) return;'''
assert old3 in s
s = s.replace(old3, new3, 1)

old4 = '''      // 偶发小剧场：idle 时每 18-35s 随机 running/waving + 台词
      const theater = () => {
        if (this.state === "idle" && Math.random() < 0.6) {'''
new4 = '''      // 偶发小剧场：idle 时每 18-35s 随机 running/waving + 台词（安静/减少动态时关闭）
      const theater = () => {
        if (this.cfg.calm || this.cfg.quiet) return;
        if (this.state === "idle" && Math.random() < 0.6) {'''
assert old4 in s
s = s.replace(old4, new4, 1)

open(p, 'w', encoding='utf-8').write(s)
print('pet.js OK')
