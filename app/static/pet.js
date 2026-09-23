/* 小鱼 —— 鲸鱼娘 GIF 状态机桌宠（素材：dsh-whale-pet 同人动画，见 tools/）
 * 状态：idle 待机 / waving 挥手 / waiting 等待 / running 奔跑 / jumping 跳跃 / failed 失败
 * 交互：点击戳一戳（跳跃+随机语）· 拖拽（位置记忆+边界）· 对话联动（等待/成功/失败）
 */
"use strict";

(function () {
  const STATES = ["idle", "waving", "waiting", "running", "jumping", "failed"];
  const POKE_WORDS = [
    "嘿嘿，戳我干嘛～", "小鱼在的！", "要一起读论文吗？",
    "点击我的头像可以打开聊天哦！", "拖不动？我才不重！", "鲸鱼娘今天也在努力～",
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
      this._bind();
      this._restore();

      // 偶发小剧场：idle 时每 18-35s 随机 running/waving + 台词
      const theater = () => {
        if (this.state === "idle" && Math.random() < 0.6) {
          this.setState(Math.random() < 0.5 ? "running" : "waving");
          this.say(IDLE_WORDS[Math.floor(Math.random() * IDLE_WORDS.length)]);
          this._backToIdle(3800);
        }
        setTimeout(theater, 18000 + Math.random() * 17000);
      };
      setTimeout(theater, 15000);
    }

    setState(name, force) {
      if (!STATES.includes(name)) return;
      if (this.state === name && !force) return;
      this.state = name;
      this.img.src = `/static/img/pet/${name}.gif?v=${name === this.state ? "" : ""}` + Date.now().toString(36).slice(-4);
      clearTimeout(this._idleTimer);
    }
    _backToIdle(ms) {
      clearTimeout(this._idleTimer);
      this._idleTimer = setTimeout(() => this.setState("idle"), ms || 3000);
    }

    say(text) {
      const b = document.getElementById("pet-bubble");
      if (!b) return;
      b.textContent = text;
      b.classList.add("show");
      clearTimeout(this._bubbleTimer);
      this._bubbleTimer = setTimeout(() => b.classList.remove("show"), 4200);
    }

    /* 对话联动 API */
    thinking(on) {
      if (on) this.setState("waiting");
      else if (this.state === "waiting") this.setState("jumping"), this._backToIdle(2600);
    }
    happy() { this.setState("jumping"); this._backToIdle(2600); }
    fail() { this.setState("failed"); this._backToIdle(4000); }

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
      el.addEventListener("pointerup", () => {
        this.drag.on = false;
        if (this.drag.moved < 6) {                       // 戳一戳
          this.setState("jumping");
          this.say(POKE_WORDS[Math.floor(Math.random() * POKE_WORDS.length)]);
          this._backToIdle(2400);
        } else {
          this._save();
          this._backToIdle(1500);
        }
      });
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
