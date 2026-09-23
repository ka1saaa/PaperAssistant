/* 小鱼 —— 鲸鱼娘 GIF 状态机桌宠（素材：dsh-whale-pet 同人动画，见 tools/）
 * 左键点击 = 互动（戳一戳）· 右键点击 = 打开对话面板
 * 拖拽换位（位置记忆）· 对话联动（等待/成功/失败）· 偶发小剧场
 * 配置（左侧导航栏可调，localStorage 持久化）：尺寸/透明度/安静模式/减少动态/显示隐藏
 */
"use strict";

(function () {
  const STATES = ["idle", "waving", "waiting", "running", "jumping", "failed"];
  const POKE_WORDS = [
    "嘿嘿，戳我干嘛～", "小鱼在的！", "要一起读论文吗？",
    "右键我可以打开聊天哦！", "拖不动？我才不重！", "鲸鱼娘今天也在努力～",
  ];
  const IDLE_WORDS = [
    "论文翻译好了叫我～", "右键图谱里的论文有惊喜哦！", "困了…zzz",
    "划词就能让我解释术语！", "记得导出你的批注笔记～",
  ];

  class GifPet {
    constructor(host) {
      this.host = host;
      this.img = document.createElement("img");
      this.img.alt = "小鱼";
      this.img.draggable = false;
      host.prepend(this.img);

      this.state = "idle";
      this.setState("idle", true);

      this.drag = { on: false, moved: 0 };

      // 用户配置
      this.cfg = { scale: 1, opacity: 1, quiet: false, calm: false };
      try { Object.assign(this.cfg, JSON.parse(localStorage.getItem("pet-cfg") || "{}")); } catch { }
      this._applyCfg();

      this._bind();
      this._restore();

      // 隐藏状态恢复
      try {
        if (localStorage.getItem("pet-hidden") === "1") this.host.style.display = "none";
      } catch { }

      // 偶发小剧场（安静/减少动态时关闭）
      const theater = () => {
        if (this.cfg.calm || this.cfg.quiet) return;
        if (this.state === "idle" && Math.random() < 0.6) {
          this.setState(Math.random() < 0.5 ? "running" : "waving");
          this.say(IDLE_WORDS[Math.floor(Math.random() * IDLE_WORDS.length)]);
          this._backToIdle(3800);
        }
        setTimeout(theater, 18000 + Math.random() * 17000);
      };
      setTimeout(theater, 15000);
    }

    /* ---- 配置 ---- */
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
    }

    /* ---- 显示 / 隐藏 / 位置 ---- */
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
    }

    /* ---- 状态 ---- */
    setState(name, force) {
      if (!STATES.includes(name)) return;
      if (this.state === name && !force) return;
      this.state = name;
      this.img.src = `/static/img/pet/${name}.gif`;
      this.img.dataset.state = name;
      clearTimeout(this._idleTimer);
    }
    _backToIdle(ms) {
      clearTimeout(this._idleTimer);
      this._idleTimer = setTimeout(() => this.setState("idle"), ms || 3000);
    }

    say(text) {
      if (this.cfg.quiet) return;
      const b = document.getElementById("pet-bubble");
      if (!b) return;
      b.textContent = text;
      b.classList.add("show");
      clearTimeout(this._bubbleTimer);
      this._bubbleTimer = setTimeout(() => b.classList.remove("show"), 4200);
    }

    /* ---- 对外联动 API ---- */
    thinking(on) {
      if (on) this.setState("waiting");
      else if (this.state === "waiting") this.happy();
    }
    happy() { this.setState("jumping"); this._backToIdle(2600); }
    fail() { this.setState("failed"); this._backToIdle(4000); }

    /* ---- 交互绑定 ---- */
    _bind() {
      const el = this.host;
      el.style.touchAction = "none";
      el.addEventListener("pointerdown", (e) => {
        el.setPointerCapture(e.pointerId);
        this.drag.on = true; this.drag.moved = 0;
        this.drag.sx = e.clientX; this.drag.sy = e.clientY;
        const r = el.getBoundingClientRect();
        this.drag.ox = r.left; this.drag.oy = r.top;
      });
      el.addEventListener("pointermove", (e) => {
        if (!this.drag.on) return;
        const dx = e.clientX - this.drag.sx, dy = e.clientY - this.drag.sy;
        this.drag.moved = Math.abs(dx) + Math.abs(dy);
        this._place(this.drag.ox + dx, this.drag.oy + dy);
        if (this.drag.moved > 6 && this.state === "idle") this.setState("running");
      });
      el.addEventListener("pointerup", (e) => {
        this.drag.on = false;
        if (this.drag.moved < 6) {
          this._interact();                                 // 左键点击 = 互动
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
      });
    }

    _interact() {
      this.setState("jumping");
      if (!this.cfg.quiet) {
        this.say(POKE_WORDS[Math.floor(Math.random() * POKE_WORDS.length)]);
      }
      this._backToIdle(2400);
    }

    _place(x, y) {
      const w = this.host.offsetWidth || 120, h = this.host.offsetHeight || 130;
      x = Math.max(2, Math.min(innerWidth - w - 2, x));
      y = Math.max(2, Math.min(innerHeight - h - 2, y));
      this.host.style.left = x + "px";
      this.host.style.top = y + "px";
      this.host.style.right = "auto";
      this.host.style.bottom = "auto";
    }
    _save() {
      try {
        const r = this.host.getBoundingClientRect();
        localStorage.setItem("pet-pos", JSON.stringify({ x: r.left, y: r.top }));
      } catch { /* 隐私模式 */ }
    }
    _restore() {
      try {
        const p = JSON.parse(localStorage.getItem("pet-pos") || "null");
        if (p && p.x > 0) this._place(p.x, p.y);
      } catch { /* 忽略 */ }
    }
  }

  function init() {
    const host = document.getElementById("ai-pet");
    if (!host || host.dataset.petInit) return;
    host.dataset.petInit = "1";
    window.petAPI = new GifPet(host);
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else init();
})();
