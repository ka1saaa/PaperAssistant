/* AutoTranslate 前端：搜索/上传/任务轮询/AI 概括弹窗/视图切换。 */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];
let searchResults = [];
let currentSummary = null;   // 弹窗当前数据
let currentTaskTitle = "";

if (typeof marked !== "undefined") {
  marked.setOptions({ breaks: true, gfm: true });
}
const md = (text) => {
  const s = String(text ?? "");
  if (typeof marked === "undefined") {
    return "<p>" + escapeHtml(s).replace(/\n{2,}/g, "</p><p>").replace(/\n/g, "<br>") + "</p>";
  }
  return marked.parse(s);
};

let authLocked = false;

async function api(path, options) {
  const resp = await fetch(path, options);
  if (resp.status === 401 && !path.startsWith("/api/auth")) {
    if (!authLocked) { authLocked = true; $("#auth-mask").classList.remove("hidden"); }
    throw new Error("需要访问密码");
  }
  const data = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new Error(data.detail || `请求失败 (${resp.status})`);
  return data;
}

async function unlockAccess() {
  const pwd = $("#auth-password").value;
  if (!pwd) return;
  try {
    await fetch("/api/auth", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password: pwd }),
    }).then((r) => { if (!r.ok) throw new Error("密码错误"); });
    authLocked = false;
    $("#auth-mask").classList.add("hidden");
    $("#auth-error").textContent = "";
    $("#auth-password").value = "";
    loadConfig(); refreshTasks(); refreshGlossaryCount();
  } catch (e) {
    $("#auth-error").textContent = "密码错误，请重试";
  }
}
$("#auth-submit").addEventListener("click", unlockAccess);
$("#auth-password").addEventListener("keydown", (e) => { if (e.key === "Enter") unlockAccess(); });

/* ---------- toast ---------- */
function toast(msg, type = "info") {
  const icons = { ok: "fa-circle-check", err: "fa-circle-xmark", info: "fa-circle-info" };
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.innerHTML = `<i class="fa-solid ${icons[type] || icons.info}"></i><span>${escapeHtml(msg)}</span>`;
  $("#toast-box").appendChild(el);
  setTimeout(() => el.classList.add("show"), 20);
  setTimeout(() => { el.classList.remove("show"); setTimeout(() => el.remove(), 350); }, 4200);
}

/* ---------- 视图切换 ---------- */
$$(".nav-item").forEach((btn) => btn.addEventListener("click", () => {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b === btn));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${btn.dataset.view}`));
}));

/* ---------- 来源切换 ---------- */
$$(".seg").forEach((btn) => btn.addEventListener("click", () => {
  $$(".seg").forEach((b) => b.classList.toggle("active", b === btn));
  $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `src-${btn.dataset.src}`));
}));

/* ---------- 配置状态 ---------- */
const PROVIDERS = {
  zhipu:     { name: "智谱 GLM",    base: "https://open.bigmodel.cn/api/paas/v4", models: ["glm-4.5-flash", "glm-4.5-air", "glm-4.5", "glm-4-flash"] },
  deepseek:  { name: "DeepSeek",   base: "https://api.deepseek.com",              models: ["deepseek-chat", "deepseek-reasoner"] },
  openai:    { name: "OpenAI",     base: "https://api.openai.com/v1",             models: ["gpt-4o-mini", "gpt-4o"] },
  moonshot:  { name: "月之暗面 Kimi", base: "https://api.moonshot.cn/v1",           models: ["moonshot-v1-8k", "moonshot-v1-32k"] },
  custom:    { name: "自定义",      base: "",                                      models: [] },
};

let currentService = "openai";

async function loadConfig() {
  try {
    const cfg = await api("/api/config");
    const chip = $("#engine-chip");
    const ok = cfg.llm_configured;
    chip.classList.toggle("off", !ok);
    chip.innerHTML = ok
      ? `<span class="dot on"></span>${cfg.service === "siliconflowfree" ? "免费试用服务" : escapeHtml(cfg.model)}`
      : `<span class="dot"></span>未配置模型`;
    if (!ok) {
      $("#warn-banner").classList.remove("hidden");
      $("#warn-banner span").textContent =
        "尚未配置大模型：翻译与 AI 功能不可用。点击左侧底部状态栏打开「模型设置」。";
    } else {
      $("#warn-banner").classList.add("hidden");
    }
    $("#dual-checkbox").checked = !!cfg.enable_dual;
  } catch {
    $("#engine-chip").innerHTML = '<span class="dot"></span>服务异常';
    $("#engine-chip").classList.add("off");
  }
}

/* ---------- 深色模式 ---------- */
const THEME_KEY = "at-theme";
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = $("#theme-btn");
  btn.innerHTML = theme === "dark"
    ? '<i class="fa-solid fa-sun"></i><span>浅色模式</span>'
    : '<i class="fa-solid fa-moon"></i><span>深色模式</span>';
}
(function initTheme() {
  let theme = null;
  try { theme = localStorage.getItem(THEME_KEY); } catch { /* 隐私模式 */ }
  if (!theme) {
    theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark" : "light";
  }
  applyTheme(theme);
})();
$("#theme-btn").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  applyTheme(next);
  try { localStorage.setItem(THEME_KEY, next); } catch { /* 隐私模式 */ }
});

/* ---------- 模型设置弹窗 ---------- */
const CUSTOM_OPT = "__custom__";
let lastRealModel = "";   // 最近一次选中的真实模型（用于手动输入/返回切换时恢复）

function fillModelOptions(models, current) {
  const sel = $("#cfg-model");
  const opts = [...new Set([...(models || []), ...(current ? [current] : [])])];
  sel.innerHTML = opts
    .map((m) => `<option value="${escapeHtml(m)}" ${m === current ? "selected" : ""}>${escapeHtml(m)}</option>`)
    .join("") + `<option value="${CUSTOM_OPT}">✎ 手动输入…</option>`;
  if (current && !opts.includes(current)) {
    sel.value = CUSTOM_OPT;
  }
  if (sel.value !== CUSTOM_OPT) lastRealModel = sel.value;
}

function showModelSelect() {
  const sel = $("#cfg-model");
  if (sel.value === CUSTOM_OPT && lastRealModel
      && [...sel.options].some((o) => o.value === lastRealModel)) {
    sel.value = lastRealModel;
  }
  sel.classList.remove("hidden");
  $("#cfg-model-text").classList.add("hidden");
  $("#cfg-model-back").classList.add("hidden");
}

function showModelText(value) {
  $("#cfg-model").classList.add("hidden");
  $("#cfg-model-text").classList.remove("hidden");
  $("#cfg-model-back").classList.remove("hidden");
  $("#cfg-model-text").value = value || "";
  $("#cfg-model-text").focus();
}

function getModelValue() {
  if (!$("#cfg-model-text").classList.contains("hidden")) {
    return $("#cfg-model-text").value.trim();
  }
  const v = $("#cfg-model").value;
  return v === CUSTOM_OPT ? "" : v;
}

$("#cfg-model").addEventListener("change", () => {
  const sel = $("#cfg-model");
  if (sel.value === CUSTOM_OPT) {
    // 带上刚才选的值，方便在输入框里微调
    showModelText(lastRealModel);
  } else {
    lastRealModel = sel.value;
  }
});
$("#cfg-model-back").addEventListener("click", showModelSelect);

function guessProvider(base) {
  for (const [key, p] of Object.entries(PROVIDERS)) {
    if (key !== "custom" && base && base.includes(new URL(p.base).hostname)) return key;
  }
  return "custom";
}

async function openSettings() {
  $("#settings-modal").classList.remove("hidden");
  $("#cfg-status").textContent = "";
  $("#cfg-apikey").value = "";
  $("#cfg-apikey").placeholder = "不修改请留空";

  const prov = $("#cfg-provider");
  prov.innerHTML = Object.entries(PROVIDERS)
    .map(([k, p]) => `<option value="${k}">${escapeHtml(p.name)}</option>`).join("");

  try {
    const cfg = await api("/api/config");
    currentService = cfg.service;
    $$(".pill").forEach((b) => b.classList.toggle("active", b.dataset.service === cfg.service));
    $("#custom-model-fields").style.display = cfg.service === "openai" ? "" : "none";
    $("#cfg-baseurl").value = cfg.base_url || "";
    $("#cfg-qps").value = cfg.qps || 4;
    $("#cfg-langout").value = cfg.lang_out || "zh";
    $("#cfg-password").placeholder = cfg.access_password_set
      ? "已开启（不修改请留空，输入 none 可关闭）" : "未开启，输入即启用";
    prov.value = guessProvider(cfg.base_url);
    fillModelOptions(PROVIDERS[prov.value]?.models || [], cfg.model);
    showModelSelect();
    if (cfg.has_api_key) {
      $("#cfg-apikey").placeholder = `已配置 ${cfg.api_key_masked}，不修改请留空`;
    }
  } catch (e) {
    $("#cfg-status").textContent = "读取配置失败：" + e.message;
  }
}

$$(".pill").forEach((btn) => btn.addEventListener("click", () => {
  $$(".pill").forEach((b) => b.classList.toggle("active", b === btn));
  currentService = btn.dataset.service;
  $("#custom-model-fields").style.display = currentService === "openai" ? "" : "none";
}));

$("#cfg-provider").addEventListener("change", () => {
  const p = PROVIDERS[$("#cfg-provider").value];
  if (p.base) $("#cfg-baseurl").value = p.base;
  showModelSelect();
  fillModelOptions(p.models, getModelValue());
});

$("#fetch-models-btn").addEventListener("click", async () => {
  const btn = $("#fetch-models-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>';
  try {
    const r = await api("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        base_url: $("#cfg-baseurl").value.trim(),
        api_key: $("#cfg-apikey").value.trim(),
      }),
    });
    if (r.models?.length) {
      fillModelOptions(r.models, getModelValue());
      showModelSelect();
      $("#cfg-status").textContent = `获取到 ${r.models.length} 个模型，下拉选择即可`;
    } else {
      $("#cfg-status").textContent = r.detail || "未获取到模型列表，可手动输入";
    }
  } catch (e) {
    $("#cfg-status").textContent = "获取失败：" + e.message;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-rotate"></i> 列表';
  }
});

$("#test-model-btn").addEventListener("click", async () => {
  const btn = $("#test-model-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span> 测试中…';
  $("#cfg-status").textContent = "";
  try {
    const r = await api("/api/config/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        service: currentService,
        base_url: $("#cfg-baseurl").value.trim(),
        api_key: $("#cfg-apikey").value.trim(),
        model: getModelValue(),
      }),
    });
    $("#cfg-status").textContent = r.detail;
    toast(r.detail, r.ok ? "ok" : "err");
  } catch (e) {
    $("#cfg-status").textContent = "测试失败：" + e.message;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="fa-solid fa-plug-circle-check"></i> 测试连接';
  }
});

$("#save-cfg-btn").addEventListener("click", async () => {
  const newPwd = $("#cfg-password").value.trim();
  const body = {
    service: currentService,
    base_url: $("#cfg-baseurl").value.trim(),
    api_key: $("#cfg-apikey").value.trim(),   // 空串 = 后端保留原值
    model: getModelValue(),
    qps: parseInt($("#cfg-qps").value, 10) || 4,
    lang_out: $("#cfg-langout").value,
    enable_dual: $("#dual-checkbox").checked,
    access_password: newPwd === "" ? null
      : (newPwd.toLowerCase() === "none" ? "" : newPwd),  // none=关闭；null=保留
  };
  try {
    const r = await api("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (newPwd !== "" && newPwd.toLowerCase() !== "none") {
      // 设置了新密码：立刻换取 cookie，避免本页下次请求被锁
      await fetch("/api/auth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: newPwd }),
      });
    }
    toast(r.ready ? "设置已保存，即时生效" : `已保存（${r.detail}）`, r.ready ? "ok" : "info");
    if (r.ready) $("#settings-modal").classList.add("hidden");
    $("#warn-banner").classList.add("hidden");
    loadConfig();
  } catch (e) {
    toast("保存失败：" + e.message, "err");
  }
});

$("#engine-chip").addEventListener("click", openSettings);
$("#settings-close").addEventListener("click", () => $("#settings-modal").classList.add("hidden"));
$("#settings-modal .modal-mask").addEventListener("click", () => $("#settings-modal").classList.add("hidden"));

/* ---------- 论文搜索 ---------- */
function renderResults() {
  const ul = $("#search-results");
  ul.innerHTML = "";
  if (!searchResults.length) {
    ul.innerHTML = `<li class="no-result">没有找到相关论文，建议换英文关键词再试</li>`;
    return;
  }
  searchResults.forEach((p, i) => {
    const li = document.createElement("li");
    const canDownload = !!p.download_url;
    const venue = p.venue && p.venue !== "arXiv" ? escapeHtml(p.venue) : "arXiv";
    li.innerHTML = `
      <div class="paper-meta">
        <p class="paper-title">${escapeHtml(p.title)}</p>
        <p class="paper-sub">${escapeHtml((p.authors || []).slice(0, 3).join(", "))}
          ${p.year ? `· ${p.year}` : ""} · ${venue}
          ${canDownload ? "" : ' · <span class="no-pdf">无开放获取 PDF</span>'}</p>
      </div>
      <button class="btn small paper-btn" data-i="${i}" ${canDownload ? "" : "disabled"}>
        <i class="fa-solid fa-language"></i> 翻译</button>`;
    ul.appendChild(li);
  });
  ul.querySelectorAll(".paper-btn").forEach((btn) =>
    btn.addEventListener("click", () => translatePaper(searchResults[btn.dataset.i], btn)));
}

async function doSearch() {
  const q = $("#search-input").value.trim();
  if (!q) return;
  const status = $("#search-status");
  $("#search-btn").disabled = true;
  $("#search-btn").innerHTML = '<span class="spin"></span>';
  status.innerHTML = '<span class="spin"></span> 正在检索 arXiv 与 Semantic Scholar…';
  $("#search-results").innerHTML = "";
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(q)}&limit=10`);
    searchResults = data.results;
    status.textContent = `找到 ${searchResults.length} 篇论文`;
    renderResults();
  } catch (e) {
    status.textContent = "";
    toast("搜索失败：" + e.message, "err");
  } finally {
    $("#search-btn").disabled = false;
    $("#search-btn").innerHTML = "<span>搜索</span>";
  }
}

async function translatePaper(paper, btn) {
  btn.disabled = true;
  try {
    await api("/api/tasks/paper", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paper, dual: $("#dual-checkbox").checked }),
    });
    toast("已加入翻译任务", "ok");
    switchView("tasks");
    refreshTasks();
  } catch (e) {
    btn.disabled = false;
    toast("创建任务失败：" + e.message, "err");
  }
}

/* ---------- 上传 / 链接 ---------- */
async function uploadFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) { toast("请选择 PDF 文件", "err"); return; }
  const dz = $("#dropzone");
  const orig = dz.innerHTML;
  dz.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i><p>上传中…</p>';
  const fd = new FormData();
  fd.append("file", file);
  fd.append("dual", $("#dual-checkbox").checked);
  try {
    await api("/api/tasks/upload", { method: "POST", body: fd });
    dz.innerHTML = '<i class="fa-solid fa-circle-check ok"></i><p>已创建翻译任务</p>';
    toast("上传成功，已开始翻译", "ok");
    setTimeout(() => { dz.innerHTML = orig; bindDropzone(); }, 1800);
    switchView("tasks");
    refreshTasks();
  } catch (e) {
    dz.innerHTML = orig;
    bindDropzone();
    toast("上传失败：" + e.message, "err");
  }
}

function bindDropzone() {
  const dz = $("#dropzone");
  const fi = $("#file-input");
  dz.onclick = () => fi.click();
  dz.ondragover = (e) => { e.preventDefault(); dz.classList.add("drag"); };
  dz.ondragleave = () => dz.classList.remove("drag");
  dz.ondrop = (e) => {
    e.preventDefault();
    dz.classList.remove("drag");
    uploadFile(e.dataTransfer.files[0]);
  };
  fi.onchange = () => { uploadFile(fi.files[0]); fi.value = ""; };
}

async function translateFromInput() {
  const input = $("#url-input").value.trim();
  if (!input) return;
  const btn = $("#url-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spin"></span>';
  try {
    await api("/api/tasks/input", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input, dual: $("#dual-checkbox").checked }),
    });
    $("#url-input").value = "";
    toast("已加入翻译任务", "ok");
    switchView("tasks");
    refreshTasks();
  } catch (e) {
    toast("创建任务失败：" + e.message, "err");
  } finally {
    btn.disabled = false;
    btn.innerHTML = "<span>获取并翻译</span>";
  }
}

/* ---------- 任务列表 ---------- */
const STATUS_TEXT = {
  queued: "排队中", downloading: "下载中", translating: "翻译中",
  done: "完成", failed: "失败", canceled: "已取消",
};
const RUNNING = ["queued", "downloading", "translating"];

function taskHtml(t) {
  const chip = `<span class="status-chip status-${t.status}">${STATUS_TEXT[t.status] || t.status}</span>`;
  const running = RUNNING.includes(t.status);
  let bar = "";
  if (running) {
    const det = t.progress != null;
    bar = `<div class="bar ${det ? "" : "indeterminate"}">
             <div style="width:${det ? t.progress : 30}%"></div></div>`;
  }
  const actions = [];
  const readable = !running && (t.has_source || t.has_mono || t.has_dual);
  if (!running) actions.push(
    `<button class="act graph" data-graph="${t.id}" title="引用辐射图">
       <i class="fa-solid fa-circle-nodes"></i> 图谱</button>`);
  if (readable) actions.push(
    `<button class="act read" data-read="${t.id}"
       data-kinds="${t.has_source ? "source" : ""},${t.has_mono ? "mono" : ""},${t.has_dual ? "dual" : ""}">
       <i class="fa-solid fa-book-open"></i> 阅读</button>`);
  if (!running) actions.push(
    `<button class="act ai" data-summary="${t.id}" ${t.has_source ? "" : "disabled"}>
       <i class="fa-solid fa-wand-magic-sparkles"></i> AI 概括</button>`);
  if (t.has_mono) actions.push(`<a class="act dl" href="/api/tasks/${t.id}/file/mono">译文</a>`);
  if (t.has_dual) actions.push(`<a class="act dl" href="/api/tasks/${t.id}/file/dual">双语对照</a>`);
  if (t.has_source) actions.push(`<a class="act dl" href="/api/tasks/${t.id}/file/source">原文</a>`);
  if (running) actions.push(`<button class="act cancel" data-cancel="${t.id}">取消</button>`);
  if (!running) actions.push(`<button class="act del" data-del="${t.id}" title="删除">
      <i class="fa-solid fa-trash-can"></i></button>`);

  const meta = [];
  if (t.stage && running) meta.push(escapeHtml(t.stage));
  if (t.status === "translating" && t.progress != null) meta.push(`${Math.round(t.progress)}%`);
  if (t.status === "done" && t.finished_at)
    meta.push("完成于 " + escapeHtml(t.finished_at.slice(5, 16).replace("T", " ")));
  if (t.status === "queued") meta.push("等待空闲翻译槽…");

  return `<li>
    <div class="task-row">
      <div class="task-info">
        <div class="task-title">${escapeHtml(t.title)}${chip}
          <span class="task-src">· ${sourceText(t.source)}</span></div>
        <div class="task-meta">${meta.join(" · ") || "&nbsp;"}</div>
      </div>
      <div class="task-actions">${actions.join("")}</div>
    </div>
    ${bar}
    ${t.error ? `<div class="task-error"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(t.error)}</div>` : ""}
  </li>`;
}

function sourceText(s) {
  return { upload: "本地上传", search: "联网搜索", input: "链接/ID" }[s] || s;
}

async function refreshTasks() {
  try {
    const data = await api("/api/tasks?limit=50");
    const ul = $("#task-list");
    ul.innerHTML = data.tasks.map(taskHtml).join("");
    $("#tasks-empty").style.display = data.tasks.length ? "none" : "flex";

    const runningCount = data.tasks.filter((t) => RUNNING.includes(t.status)).length;
    const badge = $("#nav-task-badge");
    badge.classList.toggle("hidden", runningCount === 0);
    badge.textContent = runningCount;

    ul.querySelectorAll("[data-cancel]").forEach((b) =>
      b.addEventListener("click", async () => {
        try { await api(`/api/tasks/${b.dataset.cancel}/cancel`, { method: "POST" }); refreshTasks(); }
        catch (e) { toast("取消失败：" + e.message, "err"); }
      }));
    ul.querySelectorAll("[data-del]").forEach((b) =>
      b.addEventListener("click", async () => {
        if (!confirm("确定删除这条记录吗？其原文与译文文件将一并删除。")) return;
        try { await api(`/api/tasks/${b.dataset.del}`, { method: "DELETE" }); refreshTasks(); toast("已删除", "ok"); }
        catch (e) { toast("删除失败：" + e.message, "err"); }
      }));
    ul.querySelectorAll("[data-summary]").forEach((b) =>
      b.addEventListener("click", () => openSummary(b.dataset.summary)));
    ul.querySelectorAll("[data-read]").forEach((b) =>
      b.addEventListener("click", () => openViewer(b.dataset.read, b.dataset.kinds)));
    ul.querySelectorAll("[data-graph]").forEach((b) =>
      b.addEventListener("click", () => openGraph(b.dataset.graph)));
  } catch { /* 服务未就绪时静默 */ }
}

/* ---------- AI 概括弹窗 ---------- */
function switchView(name) {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === name));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === `view-${name}`));
}

function renderMindmap(mdText) {
  // 解析 "## 一级节点" / "- 子节点" 为两列思维导图
  const lines = (mdText || "").split("\n").map((l) => l.trim()).filter(Boolean);
  let title = "论文结构";
  const branches = [];
  let cur = null;
  for (const line of lines) {
    if (/^#\s+/.test(line)) { title = line.replace(/^#\s+/, ""); continue; }
    if (/^#{2,3}\s+/.test(line)) {
      cur = { label: line.replace(/^#{2,3}\s+/, ""), leaves: [] };
      branches.push(cur);
    } else if (/^[-*]\s+/.test(line)) {
      const leaf = line.replace(/^[-*]\s+/, "").replace(/\*\*/g, "");
      if (!cur) { cur = { label: "要点", leaves: [] }; branches.push(cur); }
      cur.leaves.push(leaf);
    }
  }
  if (!branches.length) return `<div class="md">${md(mdText)}</div>`;

  const colors = ["c1", "c2", "c3", "c4", "c5", "c6"];
  const root = `<div class="mm-root"><i class="fa-solid fa-file-lines"></i>${escapeHtml(title)}</div>`;
  const cols = branches.map((b, i) => `
    <div class="mm-branch ${colors[i % colors.length]}">
      <div class="mm-node">${escapeHtml(b.label)}</div>
      ${b.leaves.map((l) => `<div class="mm-leaf">${escapeHtml(l)}</div>`).join("")}
    </div>`).join("");
  return `<div class="mindmap">${root}<div class="mm-branches">${cols}</div></div>`;
}

function renderSummary(data) {
  const tabs = `
    <div class="sum-tabs">
      <button class="sum-tab active" data-tab="summary"><i class="fa-solid fa-align-left"></i> 内容概括</button>
      <button class="sum-tab" data-tab="mindmap"><i class="fa-solid fa-diagram-project"></i> 思维导图</button>
      <button class="sum-tab" data-tab="keywords"><i class="fa-solid fa-tags"></i> 关键词</button>
    </div>
    <div id="sum-summary" class="sum-pane active md">${md(data.summary)}</div>
    <div id="sum-mindmap" class="sum-pane">${renderMindmap(data.mindmap)}</div>
    <div id="sum-keywords" class="sum-pane">
      <div class="kw-grid">
        ${(data.keywords || []).map((k) => `<button class="kw-chip" data-kw="${escapeHtml(k)}">${escapeHtml(k)}</button>`).join("")
          || '<p class="muted">未提取到关键词</p>'}
      </div>
      <div id="kw-detail" class="kw-detail hidden"></div>
    </div>`;

  $("#modal-body").innerHTML = tabs;
  $$(".sum-tab").forEach((t) => t.addEventListener("click", () => {
    $$(".sum-tab").forEach((x) => x.classList.toggle("active", x === t));
    $$(".sum-pane").forEach((p) => p.classList.toggle("active", p.id === `sum-${t.dataset.tab}`));
  }));
  $$(".kw-chip").forEach((c) => c.addEventListener("click", () => explainKeyword(c.dataset.kw)));
}

async function openSummary(taskId) {
  $("#summary-modal").classList.remove("hidden");
  $("#modal-task-title").textContent = currentTaskTitle;
  $("#modal-body").innerHTML =
    `<div class="sum-loading"><span class="spin big"></span><p>AI 正在阅读论文并生成概括…</p>
     <p class="muted small">通常需要 10-60 秒，取决于论文长度与模型速度</p></div>`;

  try {
    let data;
    try {
      data = await api(`/api/tasks/${taskId}/summary`);   // 有缓存直接用
    } catch {
      data = await api(`/api/tasks/${taskId}/summarize`, { method: "POST" });
    }
    currentSummary = data;
    renderSummary(data);
  } catch (e) {
    $("#modal-body").innerHTML =
      `<div class="sum-error"><i class="fa-solid fa-circle-xmark"></i>
       <p>${escapeHtml(e.message)}</p></div>`;
  }
}

async function explainKeyword(kw) {
  const box = $("#kw-detail");
  $$(".sum-tab").forEach((x) => x.classList.toggle("active", x.dataset.tab === "keywords"));
  $$(".sum-pane").forEach((p) => p.classList.toggle("active", p.id === "sum-keywords"));
  box.classList.remove("hidden");
  box.innerHTML = `<div class="kw-loading"><span class="spin"></span> 正在解释「${escapeHtml(kw)}」…</div>`;
  try {
    const data = await api("/api/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: kw, context: currentSummary?.summary || "" }),
    });
    box.innerHTML = `
      <div class="kw-head"><i class="fa-solid fa-book-open"></i>
        <b>${escapeHtml(kw)}</b>
        <button class="kw-close" id="kw-close"><i class="fa-solid fa-xmark"></i></button></div>
      <div class="md">${md(data.explanation)}</div>
      ${data.related?.length ? `<div class="kw-related">相关：
        ${data.related.map((r) => `<button class="kw-chip sm" data-kw="${escapeHtml(r)}">${escapeHtml(r)}</button>`).join("")}
      </div>` : ""}`;
    $("#kw-close").addEventListener("click", () => box.classList.add("hidden"));
    box.querySelectorAll(".kw-chip").forEach((c) =>
      c.addEventListener("click", () => explainKeyword(c.dataset.kw)));
  } catch (e) {
    box.innerHTML = `<div class="kw-loading err"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(e.message)}</div>`;
  }
}

$("#modal-close").addEventListener("click", () => $("#summary-modal").classList.add("hidden"));
$(".modal-mask").addEventListener("click", () => $("#summary-modal").classList.add("hidden"));

/* ---------- 清空历史 ---------- */
$("#clear-btn").addEventListener("click", async () => {
  const hasRunning = $$("#task-list .status-chip")
    .some((c) => RUNNING.includes(c.className.replace("status-chip status-", "").trim()));
  const msg = hasRunning
    ? "将删除全部【已完成/失败/已取消】的历史记录（进行中的任务保留），确定吗？"
    : "确定清空全部历史记录吗？对应的原文与译文文件将一并删除。";
  if (!confirm(msg)) return;
  try {
    const r = await api("/api/tasks", { method: "DELETE" });
    refreshTasks();
    toast(`已删除 ${r.deleted} 条记录`, "ok");
  } catch (e) { toast("清空失败：" + e.message, "err"); }
});

/* ---------- 其他 ---------- */
$("#search-btn").addEventListener("click", doSearch);
$("#search-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });
$("#url-btn").addEventListener("click", translateFromInput);
$("#url-input").addEventListener("keydown", (e) => { if (e.key === "Enter") translateFromInput(); });
$("#refresh-btn").addEventListener("click", refreshTasks);

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

bindDropzone();
loadConfig();
refreshTasks();
refreshGlossaryCount();
setInterval(refreshTasks, 3000);

/* ---------- 术语表 ---------- */
async function refreshGlossaryCount() {
  try {
    const d = await api("/api/glossary");
    const n = d.entries.length;
    const em = $("#glossary-count");
    em.textContent = n;
    em.classList.toggle("hidden", n === 0);
  } catch { /* 忽略 */ }
}

function renderGlossaryCurrent(entries) {
  $("#glossary-cur-count").textContent = entries.length;
  $("#glossary-current-list").innerHTML = entries.length
    ? entries.map((e) =>
      `<li><code>${escapeHtml(e.src)}</code><i class="fa-solid fa-arrow-right"></i><b>${escapeHtml(e.tgt)}</b></li>`).join("")
    : '<li class="muted small">暂无术语</li>';
}

async function openGlossary() {
  $("#glossary-modal").classList.remove("hidden");
  $("#glossary-input").value = "";
  $("#glossary-status").textContent = "";
  try {
    const d = await api("/api/glossary");
    renderGlossaryCurrent(d.entries);
  } catch (e) {
    $("#glossary-status").textContent = "读取失败：" + e.message;
  }
}

$("#glossary-btn").addEventListener("click", openGlossary);
$("#glossary-close").addEventListener("click", () => $("#glossary-modal").classList.add("hidden"));
$("#glossary-modal .modal-mask").addEventListener("click", () => $("#glossary-modal").classList.add("hidden"));

$("#glossary-save-btn").addEventListener("click", async () => {
  // 解析 textarea：每行 "src,tgt"，中英文逗号都支持
  const entries = $("#glossary-input").value.split("\n").map((line) => {
    const idx = line.replace("，", ",").indexOf(",");
    if (idx <= 0) return null;
    return { src: line.slice(0, idx).trim(), tgt: line.slice(idx + 1).replace("，", "").trim() };
  }).filter(Boolean);
  // 与已有术语合并（新增优先）
  let existing = [];
  try { existing = (await api("/api/glossary")).entries; } catch { /* 空 */ }
  const merged = [...entries, ...existing];
  try {
    const r = await api("/api/glossary", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ entries: merged }),
    });
    $("#glossary-input").value = "";
    $("#glossary-status").textContent = `已保存，共 ${r.count} 条术语`;
    renderGlossaryCurrent((await api("/api/glossary")).entries);
    refreshGlossaryCount();
    toast(`术语表已保存（${r.count} 条）`, "ok");
  } catch (e) {
    $("#glossary-status").textContent = "保存失败：" + e.message;
  }
});

$("#glossary-clear-btn").addEventListener("click", async () => {
  if (!confirm("清空全部术语？")) return;
  try {
    await api("/api/glossary", { method: "DELETE" });
    renderGlossaryCurrent([]);
    refreshGlossaryCount();
    $("#glossary-status").textContent = "已清空";
  } catch (e) { toast("清空失败：" + e.message, "err"); }
});

/* ================= PDF 阅读器 ================= */
if (typeof pdfjsLib !== "undefined") {
  pdfjsLib.GlobalWorkerOptions.workerSrc =
    "/static/vendor/pdf.worker.min.js";
}

var V = { task: null, kinds: {}, kind: "source", doc: null, page: 1, scale: 1.0,
            renderSeq: 0, loadSeq: 0,
            observer: new IntersectionObserver(onSlotIntersect, { root: null, rootMargin: "600px 0px" }),
            slotW: 0, slotH: 0 };
const KIND_NAMES = { source: "原文", mono: "译文", dual: "双语对照" };

function switchSide(name) {
  $$(".side-tab").forEach((t) => t.classList.toggle("active", t.dataset.side === name));
  $$(".side-pane").forEach((p) => p.classList.toggle("active", p.id === `side-${name}`));
}
$$(".side-tab").forEach((t) => t.addEventListener("click", () => switchSide(t.dataset.side)));

async function openViewer(taskId, kindsStr) {
  try {
    V.task = await api(`/api/tasks/${taskId}`);
  } catch (e) { toast("打开失败：" + e.message, "err"); return; }
  const [hasSrc, hasMono, hasDual] = (kindsStr || "").split(",");
  V.kinds = { source: hasSrc === "source", mono: hasMono === "mono", dual: hasDual === "dual" };
  V.kind = V.kinds.source ? "source" : (V.kinds.mono ? "mono" : "dual");
  V.page = 1; V.scale = 1.0;
  $("#viewer-title").textContent = V.task.title;
  buildKindPills();
  $("#viewer-modal").classList.remove("hidden");
  switchSide("annots");
  await loadAnnotations();
  await loadDoc();
  loadToc();
}

/* ---------- 目录 ---------- */
async function loadToc() {
  $("#toc-loading").style.display = "flex";
  $("#toc-list").innerHTML = "";
  $("#toc-empty").classList.add("hidden");
  try {
    const d = await api(`/api/tasks/${V.task.id}/outline/${V.kind}`);
    const toc = d.outline || [];
    $("#toc-loading").style.display = "none";
    if (!toc.length) {
      $("#toc-empty").classList.remove("hidden");
      return;
    }
    $("#toc-list").innerHTML = toc.map(([lv, title, pg]) =>
      `<li><button class="toc-item lv${Math.min(lv, 3)}" data-pg="${pg}"
         title="${escapeHtml(title)}">${escapeHtml(title)}</button></li>`).join("");
    $("#toc-list").querySelectorAll(".toc-item").forEach((b) =>
      b.addEventListener("click", () => {
        switchSide("annots");
        gotoPage(parseInt(b.dataset.pg, 10));
      }));
  } catch {
    $("#toc-loading").style.display = "none";
    $("#toc-empty").classList.remove("hidden");
  }
}

function buildKindPills() {
  $("#viewer-kind").innerHTML = Object.entries(KIND_NAMES).map(([k, n]) =>
    `<button class="vkind ${k === V.kind ? "active" : ""}" data-vkind="${k}"
       ${V.kinds[k] ? "" : "disabled"}>${n}</button>`).join("");
  $$(".vkind:not([disabled])").forEach((b) =>
    b.addEventListener("click", async () => {
      if (b.dataset.vkind === V.kind) return;
      V.kind = b.dataset.vkind; V.page = 1;
      buildKindPills();
      await loadDoc();
      loadToc();
    }));
}

async function loadDoc() {
  const load = ++V.loadSeq;
  // 文档按 kind 缓存，切换即秒开；首次加载走网络
  V.doc = null;
  const cacheKey = `${V.task.id}:${V.kind}`;
  V.docs ||= {};
  let doc = V.docs[cacheKey];
  if (!doc) {
    $("#viewer-loading").classList.remove("hidden");
    $("#viewer-page-wrap").classList.add("hidden");
    try {
      doc = await pdfjsLib.getDocument({
        url: `/api/tasks/${V.task.id}/file/${V.kind}`,
      }).promise;
    } catch (e) {
      if (load === V.loadSeq) {
        $("#viewer-loading").innerHTML =
          `<p style="color:var(--err)">PDF 加载失败：${escapeHtml(e.message || e)}</p>`;
      }
      return;
    }
    if (load !== V.loadSeq) {   // 已被更新的加载取代：放下引用即可，
      V.docs[cacheKey] = doc;   // 千万不要 destroy——并发销毁会毒死共享 worker
      return;
    }
    V.docs[cacheKey] = doc;
    $("#viewer-loading").classList.add("hidden");
  }
  V.doc = doc;
  V.page = Math.min(Math.max(1, V.page), doc.numPages);
  $("#pg-total").textContent = doc.numPages;
  $("#viewer-page-wrap").classList.remove("hidden");
  await buildSlots();
}

/* ---------- 连续滚动：页槽 + 懒加载 ---------- */
async function buildSlots() {
  const seq = ++V.renderSeq;
  // 取第一页尺寸作为所有页槽的基准
  const p1 = await V.doc.getPage(1);
  if (seq !== V.renderSeq || !V.doc) return;
  const vp1 = p1.getViewport({ scale: V.scale });
  V.slotW = Math.floor(vp1.width);
  V.slotH = Math.floor(vp1.height);

  const wrap = $("#viewer-page-wrap");
  wrap.innerHTML = "";
  for (let n = 1; n <= V.doc.numPages; n++) {
    const slot = document.createElement("div");
    slot.className = "page-slot";
    slot.dataset.page = n;
    slot.dataset.loaded = "";
    slot.style.width = V.slotW + "px";
    slot.style.height = V.slotH + "px";
    slot.innerHTML = `<span class="slot-num">${n}</span><div class="textLayer"></div>`;
    wrap.appendChild(slot);
    V.observer.observe(slot);
  }
  $("#zoom-ind").textContent = Math.round(V.scale * 100) + "%";
  gotoPage(V.page, false);
}

function onSlotIntersect(entries) {
  for (const en of entries) {
    if (en.isIntersecting) loadSlot(en.target);
  }
}

async function loadSlot(slot) {
  if (slot.dataset.loaded === "1") return;
  slot.dataset.loaded = "1";
  const n = parseInt(slot.dataset.page, 10);
  const img = document.createElement("img");
  img.alt = "";
  img.style.width = "100%";
  img.style.height = "100%";
  img.style.display = "block";
  img.src = `/api/tasks/${V.task.id}/page/${V.kind}/${n}?zoom=${V.scale}`;
  slot.prepend(img);

  // 文字层（选中/批注/解释依赖它）
  try {
    const page = await V.doc.getPage(n);
    const vp = page.getViewport({ scale: V.scale });
    const layer = slot.querySelector(".textLayer");
    const tc = await page.getTextContent();
    for (const it of tc.items) {
      if (!it.str) continue;
      const tx = pdfjsLib.Util.transform(vp.transform, it.transform);
      const fh = Math.hypot(tx[2], tx[3]);
      const angle = Math.atan2(tx[1], tx[0]);
      const span = document.createElement("span");
      span.textContent = it.str;
      span.style.left = tx[4] + "px";
      span.style.top = (tx[5] - fh) + "px";
      span.style.fontSize = fh + "px";
      if (angle) span.style.transform = `rotate(${angle}rad)`;
      layer.appendChild(span);
    }
  } catch { /* 文字层失败不影响图片显示 */ }
}

function updatePageIndicator() {
  const slots = $("#viewer-page-wrap").children;
  if (!slots.length) return;
  const mid = $("#viewer-scroll").scrollTop + $("#viewer-scroll").clientHeight / 3;
  let cur = 1;
  for (const s of slots) {
    if (s.offsetTop <= mid) cur = parseInt(s.dataset.page, 10);
    else break;
  }
  V.page = cur;
  $("#pg-input").value = cur;
}

/* 翻页 / 缩放 */
function gotoPage(p, smooth = true) {
  if (!V.doc) return;
  p = Math.min(Math.max(1, p), V.doc.numPages);
  V.page = p;
  $("#pg-input").value = p;
  const slot = $("#viewer-page-wrap").children[p - 1];
  if (slot) {
    loadSlot(slot);   // 立即加载目标页
    slot.scrollIntoView({ behavior: smooth ? "smooth" : "auto", block: "start" });
  }
}
$("#pg-prev").addEventListener("click", () => gotoPage(V.page - 1));
$("#pg-next").addEventListener("click", () => gotoPage(V.page + 1));
$("#pg-input").addEventListener("change", (e) => gotoPage(parseInt(e.target.value, 10) || 1));
$("#zoom-in").addEventListener("click", () => { V.scale = Math.min(4, V.scale * 1.25); buildSlots(); });
$("#zoom-out").addEventListener("click", () => { V.scale = Math.max(0.5, V.scale / 1.25); buildSlots(); });
$("#viewer-scroll").addEventListener("scroll", () => updatePageIndicator(), { passive: true });
$("#viewer-close").addEventListener("click", closeViewer);
function closeViewer() {
  $("#viewer-modal").classList.add("hidden");
  $("#sel-popup").classList.add("hidden");
  if (V.observer) V.observer.disconnect();
  // 只放下引用：不 cancel 渲染、不 destroy 文档（两者都会毒死 pdf.js worker）。
  V.doc = null;
  V.docs = {};
}
document.addEventListener("keydown", (e) => {
  if ($("#viewer-modal").classList.contains("hidden")) return;
  if (e.key === "Escape") closeViewer();
});

/* ---------- 选中文字 → 弹条 ---------- */
let lastMouse = { x: 0, y: 0 };
$("#viewer-scroll").addEventListener("mousemove", (e) => { lastMouse = { x: e.clientX, y: e.clientY }; });
$("#viewer-scroll").addEventListener("mouseup", (e) => {
  setTimeout(() => {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    const inLayer = sel && sel.anchorNode &&
      !!sel.anchorNode.parentElement?.closest?.(".textLayer");
    if (text && inLayer && text.length <= 300) {
      showSelPopup(text);
    } else {
      $("#sel-popup").classList.add("hidden");
    }
  }, 10);
});

function showSelPopup(text) {
  const pop = $("#sel-popup");
  pop.dataset.text = text;
  pop.classList.remove("hidden");
  const x = Math.min(lastMouse.x + 8, window.innerWidth - 150);
  const y = Math.max(10, lastMouse.y - 44);
  pop.style.left = x + "px";
  pop.style.top = y + "px";
}

$("#sel-annot").addEventListener("click", () => {
  const text = $("#sel-popup").dataset.text;
  $("#sel-popup").classList.add("hidden");
  window.getSelection()?.removeAllRanges();
  openAnnotEditor(text);
});
$("#sel-explain").addEventListener("click", () => {
  const text = $("#sel-popup").dataset.text;
  $("#sel-popup").classList.add("hidden");
  explainSelection(text);
});

/* ---------- 批注 ---------- */
function openAnnotEditor(quote) {
  switchSide("annots");
  $("#annot-editor").classList.remove("hidden");
  $("#annot-quote").textContent = quote;
  $("#annot-note").value = "";
  $("#annot-note").focus();
}
$("#annot-cancel").addEventListener("click", () => $("#annot-editor").classList.add("hidden"));
$("#annot-save").addEventListener("click", async () => {
  const note = $("#annot-note").value.trim();
  if (!note) { toast("请写下笔记内容", "err"); return; }
  try {
    await api(`/api/tasks/${V.task.id}/annotations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kind: V.kind, page: V.page,
        quote: $("#annot-quote").textContent, note,
      }),
    });
    $("#annot-editor").classList.add("hidden");
    toast("批注已保存", "ok");
    await loadAnnotations();
  } catch (e) { toast("保存失败：" + e.message, "err"); }
});

async function loadAnnotations() {
  try {
    const d = await api(`/api/tasks/${V.task.id}/annotations`);
    const list = d.annotations || [];
    $("#annot-count").textContent = list.length;
    $("#annot-empty").style.display = list.length ? "none" : "flex";
    const exp = $("#export-annots-btn");
    exp.classList.toggle("disabled", list.length === 0);
    exp.href = `/api/tasks/${V.task.id}/annotations/export`;
    $("#annot-list").innerHTML = list.map((a) => `
      <li class="annot-item" data-aid="${a.id}">
        <div class="annot-item-head">
          <span class="annot-badge" data-jump="${a.kind}:${a.page}">${KIND_NAMES[a.kind] || a.kind} · 第${a.page}页</span>
          <span class="annot-time">${escapeHtml((a.created_at || "").slice(5, 16).replace("T", " "))}</span>
          <button class="annot-del" title="删除"><i class="fa-solid fa-trash-can"></i></button>
        </div>
        <div class="annot-q">${escapeHtml(a.quote)}</div>
        <div class="annot-n">${escapeHtml(a.note)}</div>
      </li>`).join("");
    $("#annot-list").querySelectorAll(".annot-del").forEach((b) =>
      b.addEventListener("click", async (e) => {
        e.stopPropagation();
        const aid = b.closest(".annot-item").dataset.aid;
        if (!confirm("删除这条批注？")) return;
        try {
          await api(`/api/tasks/${V.task.id}/annotations/${aid}`, { method: "DELETE" });
          loadAnnotations();
        } catch (err) { toast("删除失败：" + err.message, "err"); }
      }));
    $("#annot-list").querySelectorAll(".annot-badge").forEach((b) =>
      b.addEventListener("click", async () => {
        const [kind, page] = b.dataset.jump.split(":");
        await jumpTo(kind, parseInt(page, 10));
      }));
  } catch { /* 任务无批注文件时静默 */ }
}

async function jumpTo(kind, page) {
  if (!V.kinds[kind]) return;
  if (kind !== V.kind) {
    V.kind = kind; V.page = page;
    buildKindPills();
    await loadDoc();
  } else {
    await gotoPage(page);
  }
  $("#viewer-page-wrap").scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- 选中内容 AI 解释 ---------- */
async function explainSelection(text) {
  if (!text) return;
  switchSide("explain");
  $("#explain-result").innerHTML =
    `<div class="kw-loading"><span class="spin"></span> AI 正在解释选中的内容…</div>`;
  try {
    const d = await api("/api/explain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keyword: text, task_id: V.task.id }),
    });
    $("#explain-result").innerHTML = `
      <div class="kw-head"><i class="fa-solid fa-book-open"></i> <b>选中解释</b></div>
      <div class="annot-q">${escapeHtml(text.slice(0, 160))}</div>
      <div class="md">${md(d.explanation)}</div>
      ${d.related?.length ? `<div class="kw-related">相关：
        ${d.related.map((r) => `<button class="kw-chip sm" data-kw="${escapeHtml(r)}">${escapeHtml(r)}</button>`).join("")}
      </div>` : ""}`;
    $("#explain-result").querySelectorAll(".kw-chip").forEach((c) =>
      c.addEventListener("click", () => explainSelection(c.dataset.kw)));
  } catch (e) {
    $("#explain-result").innerHTML =
      `<div class="kw-loading err"><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(e.message)}</div>`;
  }
}

/* ================= 文献图谱（切换式中心导航） ================= */
var G = { task: null, center: null, mother: null, satellites: [], sim: null,
            svg: null, g: null, defs: null, width: 0, height: 0,
            history: [], loading: false };

/* 每篇子类论文的专属颜色（循环取用，视觉可区分） */
const SAT_PALETTE = [
  "#7a4fe0", "#0f8a8a", "#e07a2f", "#d94f7c", "#2f7de0", "#8aa30f",
  "#b5541d", "#12a5a5", "#c33d6e", "#4f8f3a", "#9a5cd0", "#d0a012",
];

const KIND_META = {
  center: { label: "中心论文", grad: "gBlue", color: "#4f6ef7", r: 30 },
  mother: { label: "母类（上一中心）", grad: "gMother", color: "#7b93f8", r: 18 },
  ref:    { label: "中心引用的", grad: "gPurple", color: "#8f6bff", r: 17 },
  cite:   { label: "引用中心的", grad: "gGreen", color: "#18a058", r: 17 },
};

// 进入桌宠设置视图时同步表单
document.addEventListener("click", (e) => {
  const btn = e.target.closest?.(".nav-item[data-view='pet']");
  if (btn) setTimeout(syncPetSettingsUI, 50);
});

function switchToGraphView() {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === "graph"));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-graph"));
}

let graphOpening = false;   // 防重复进入（上游限流环境下保持稳定）

async function openGraph(taskId) {
  if (graphOpening) return;
  graphOpening = true;
  switchToGraphView();
  $("#graph-hint").classList.add("hidden");
  $("#graph-error").classList.add("hidden");
  $("#graph-wrap").classList.add("hidden");
  $("#graph-reload").classList.remove("hidden");
  $("#graph-reload").onclick = () => openGraph(taskId);
  $("#graph-sub").innerHTML = '<span class="spin"></span> 正在解析论文与引用网络…';

  try {
    const d = await api(`/api/tasks/${taskId}/graph`);
    G.task = await api(`/api/tasks/${taskId}`);
    G.history = [];
    G.mother = null;
    G.svg = null;                       // 重新初始化画布（清掉旧 defs/sim）
    setCenter(d.node, d.references, d.citations);
    $("#graph-wrap").classList.remove("hidden");
    $("#graph-legend").classList.remove("hidden");
    $("#graph-back").classList.add("hidden");
    renderGraph(true);
  } catch (e) {
    $("#graph-sub").textContent = "图谱生成失败";
    const err = $("#graph-error");
    err.classList.remove("hidden");
    err.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(e.message)}`;
  } finally {
    graphOpening = false;
  }
}

function flipRel(rel) { return rel === "ref" ? "cite" : "ref"; }

function lighten(hex, ratio) {
  const n = parseInt(hex.slice(1), 16);
  const ch = (v) => Math.min(255, Math.round(v + (255 - v) * ratio));
  const r = ch((n >> 16) & 255), g = ch((n >> 8) & 255), b = ch(n & 255);
  return "#" + ((r << 16) | (g << 8) | b).toString(16).padStart(6, "0");
}

function setCenter(node, references, citations) {
  G.center = { ...node, rel: "center", kind: "center" };
  const sats = [];
  let pi = 0;
  for (const n of references || []) sats.push({ ...n, rel: "ref", kind: "ref", __pal: pi++ % SAT_PALETTE.length });
  for (const n of citations || []) sats.push({ ...n, rel: "cite", kind: "cite", __pal: pi++ % SAT_PALETTE.length });
  G.satellites = sats;
  $("#graph-sub").textContent = `中心论文：${G.center.title}（引用网络免费来自 OpenAlex / Semantic Scholar）`;
}

async function recenter(node) {
  if (G.loading) return;
  G.loading = true;
  const oldCenter = G.center;
  $("#graph-loading").classList.remove("hidden");
  $("#graph-loading").innerHTML =
    `<span class="spin big"></span><p>正在以《${escapeHtml(node.title.slice(0, 40))}》为中心加载相关论文…</p>`;
  try {
    const d = await api(`/api/graph/node/${node.s2_id}`);
    G.history.push({ node: oldCenter, backRel: flipRel(node.rel), nodeRel: node.rel });
    G.mother = { ...oldCenter, rel: flipRel(node.rel), kind: "mother" };
    setCenter(node, d.references, d.citations);
    $("#graph-loading").classList.add("hidden");
    $("#graph-back").classList.remove("hidden");
    renderGraph(true);
    showGraphDetail(G.center);
  } catch (e) {
    $("#graph-loading").classList.add("hidden");
    toast(e.message, "err");
  } finally {
    G.loading = false;
  }
}

async function goBackCenter() {
  if (!G.history.length || G.loading) return;
  G.loading = true;
  const entry = G.history.pop();
  const oldCenter = G.center;
  $("#graph-loading").classList.remove("hidden");
  $("#graph-loading").innerHTML = '<span class="spin big"></span>';
  try {
    const d = await api(`/api/graph/node/${entry.node.s2_id}`);
    setCenter(entry.node, d.references, d.citations);
    G.mother = { ...oldCenter, rel: entry.backRel, kind: "mother" };
    $("#graph-loading").classList.add("hidden");
    $("#graph-back").classList.toggle("hidden", G.history.length === 0);
    renderGraph(true);
    showGraphDetail(G.center);
  } catch (e) {
    G.history.push(entry);
    $("#graph-loading").classList.add("hidden");
    toast(e.message, "err");
  } finally {
    G.loading = false;
  }
}

/* 渐变与阴影定义（每次 renderGraph 前确保存在） */
function ensureDefs() {
  if (G.defs) return;
  const defs = G.svg.append("defs");
  const grad = (id, from, to) => {
    const g = defs.append("radialGradient").attr("id", id)
      .attr("cx", "35%").attr("cy", "35%").attr("r", "75%");
    g.append("stop").attr("offset", "0%").attr("stop-color", from);
    g.append("stop").attr("offset", "100%").attr("stop-color", to);
  };
  grad("gBlue", "#7c93ff", "#3b5bef");
  grad("gMother", "#93a7fb", "#5f79e8");
  SAT_PALETTE.forEach((c, i) => grad("gPal" + i, lighten(c, 0.45), c));
  const f = defs.append("filter").attr("id", "softShadow")
    .attr("x", "-60%").attr("y", "-60%").attr("width", "220%").attr("height", "220%");
  f.append("feDropShadow").attr("dx", 0).attr("dy", 3)
    .attr("stdDeviation", 4).attr("flood-color", "rgba(23,29,47,.35)");
  G.defs = defs;
}

function renderGraph(animate) {
  const wrap = $("#graph-wrap");
  G.width = wrap.clientWidth || 900;
  G.height = wrap.clientHeight || 620;

  if (!G.svg) {
    G.svg = d3.select("#graph-svg");
    ensureDefs();
    G.g = G.svg.append("g");
    G.g.append("g").attr("class", "links");
    G.g.append("g").attr("class", "nodes");
    G.svg.call(d3.zoom().scaleExtent([0.4, 3]).on("zoom",
      (ev) => G.g.attr("transform", ev.transform)));
    G.svg.on("click", () => $("#graph-detail").classList.add("hidden"));
  }
  G.svg.attr("viewBox", [-G.width / 2, -G.height / 2, G.width, G.height]);

  const nodes = [G.center, ...(G.mother ? [G.mother] : []), ...G.satellites];
  const links = [];
  for (const n of G.satellites) links.push({ source: G.center, target: n });
  if (G.mother) links.push({ source: G.center, target: G.mother, mother: true });

  const linkSel = G.g.select("g.links").selectAll("line").data(links,
    (l) => (l.mother ? "M" : "") + l.target.s2_id);
  // 消失的连线淡出
  linkSel.exit().transition().duration(400).attr("stroke-opacity", 0).remove();
  linkSel.enter().append("line")
    .attr("class", (l) => (l.mother ? "lmother" : (l.target.rel === "ref" ? "lref" : "lcite")))
    .attr("stroke-opacity", 0)
    .transition().duration(animate ? 600 : 0)
    .attr("stroke-opacity", 0.55);

  const nodeSel = G.g.select("g.nodes").selectAll("g.node").data(nodes, (d) => d.s2_id);
  // 消失的节点淡出
  nodeSel.exit().transition().duration(400).attr("opacity", 0).remove();

  const nodeEnter = nodeSel.enter().append("g").attr("class", "node")
    .attr("cursor", "pointer")
    .attr("opacity", 0);
  // 新节点从中心涟漪展开 + 级联延迟
  nodeEnter.transition().duration(550)
    .delay((d, i) => (animate ? i * 45 : 0))
    .attr("opacity", 1);
  nodeEnter.call(d3.drag()
    .on("start", (ev, d) => { if (!ev.active && d.kind !== "center") G.sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
    .on("end", (ev, d) => { if (!ev.active) G.sim.alphaTarget(0); if (d.kind !== "center") { d.fx = null; d.fy = null; } }))
    .on("click", (ev, d) => {
      ev.stopPropagation();
      hideGraphCtx();
      if (d.kind === "center") { showGraphDetail(d); return; }
      if (d.kind === "mother") { goBackCenter(); return; }
      recenter(d);
    })
    .on("contextmenu", (ev, d) => {
      ev.preventDefault();
      ev.stopPropagation();
      showGraphCtx(ev, d);
    });

  nodeEnter.append("circle").attr("class", "halo")
    .attr("r", (d) => KIND_META[d.kind].r + 7)
    .attr("fill", (d) => `url(#${KIND_META[d.kind].grad})`)
    .attr("opacity", 0.18);
  nodeEnter.append("circle").attr("class", "dot")
    .attr("fill", (d) => `url(#${KIND_META[d.kind].grad})`)
    .attr("filter", "url(#softShadow)")
    .attr("stroke", (d) => (d.kind === "mother" ? "#94a8ff" : "#fff"))
    .attr("stroke-dasharray", (d) => (d.kind === "mother" ? "5,3" : null))
    .attr("stroke-width", (d) => (d.kind === "mother" ? 2 : 2));
  nodeEnter.append("text").attr("class", "mbadge")
    .attr("text-anchor", "middle").attr("dy", -26)
    .attr("font-size", 11).attr("font-weight", 700)
    .attr("fill", "#7b93f8")
    .text((d) => (d.kind === "mother" ? "母类" : ""));
  nodeEnter.append("text").attr("class", "nlabel")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => (d.kind === "center" ? 46 : 30));

  const all = nodeEnter.merge(nodeSel);
  // 半径/渐变变化平滑过渡（缩放感）
  all.select("circle.dot")
    .transition().duration(animate ? 450 : 0)
    .attr("r", (d) => KIND_META[d.kind].r)
    .attr("fill", (d) => (d.kind === "ref" || d.kind === "cite")
      ? `url(#gPal${d.__pal % SAT_PALETTE.length})`
      : `url(#${KIND_META[d.kind].grad})`);
  all.select("circle.halo")
    .attr("r", (d) => KIND_META[d.kind].r + 7)
    .attr("fill", (d) => (d.kind === "ref" || d.kind === "cite")
      ? `url(#gPal${d.__pal % SAT_PALETTE.length})`
      : `url(#${KIND_META[d.kind].grad})`)
    .attr("opacity", (d) => (d.kind === "center" ? 0.2 : 0.14));
  all.select("text.nlabel")
    .text((d) => (d.title.length > 22 ? d.title.slice(0, 21) + "…" : d.title))
    .attr("font-size", (d) => (d.kind === "center" ? 15 : 12));

  // 卫星深浅渐变：按被引数排名，越紧密颜色越深
  const satSel = all.filter((d) => d.kind !== "center" && d.kind !== "mother");
  const sorted = satSel.data().slice().sort((a, b) =>
    (b.citation_count || 0) - (a.citation_count || 0));
  sorted.forEach((d, i) => { d.__fade = Math.max(0.5, 1 - i * 0.09); });
  satSel.select("circle.dot").attr("fill-opacity", (d) => d.__fade ?? 1);
  satSel.select("circle.halo").attr("opacity", (d) => (d.__fade ?? 1) * 0.14);

  if (G.sim) G.sim.stop();
  // 理想半径：卫星均匀摊开在一个环上（按角度分配初始位置避免扎堆）
  const RING = Math.min(G.width, G.height) * 0.34;
  for (let i = 0; i < G.satellites.length; i++) {
    const n = G.satellites[i];
    if (n.x == null) {
      const a = (i / Math.max(1, G.satellites.length)) * 2 * Math.PI - Math.PI / 2;
      n.x = Math.cos(a) * RING;
      n.y = Math.sin(a) * RING;
    }
  }
  const radialForce = (alpha) => {
    for (const n of G.satellites) {
      const dist = Math.hypot(n.x, n.y) || 1;
      const k = (RING - dist) * 0.12 * alpha;
      n.x += (n.x / dist) * k;
      n.y += (n.y / dist) * k;
    }
  };
  G.sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.s2_id)
      .distance((l) => (l.mother ? 170 : RING)).strength(0.4))
    .force("collide", d3.forceCollide(58))
    .force("charge", d3.forceManyBody().strength(-200))
    .force("ring", radialForce)
    .alpha(animate ? 0.9 : 0.6)
    .on("tick", () => {
      G.g.select("g.links").selectAll("line")
        .attr("x1", (l) => l.source.x).attr("y1", (l) => l.source.y)
        .attr("x2", (l) => l.target.x).attr("y2", (l) => l.target.y);
      all.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });
  // 中心固定原点；母类锚定左上角，标题永不与中心叠加
  G.center.fx = 0; G.center.fy = 0;
  if (G.mother) {
    G.mother.fx = -G.width / 2 + 120;
    G.mother.fy = -G.height / 2 + 96;
  }
}

function showGraphDetail(d) {
  const box = $("#graph-detail");
  box.classList.remove("hidden");
  const kindName = d.kind === "center" ? "中心论文"
    : (d.kind === "mother" ? "母类（上一中心）"
    : (d.rel === "ref" ? "中心引用的论文" : "引用中心论文的论文"));
  box.innerHTML = `
    <div class="kw-head"><i class="fa-solid fa-book-open"></i>
      <b>${escapeHtml(d.title.slice(0, 60))}</b></div>
    <div class="paper-sub" style="margin:6px 0 10px">
      ${d.year || "—"} · ${escapeHtml(d.venue || "未知来源")} · 被引 ${d.citation_count}
      · ${kindName}</div>
    <div class="graph-detail-btns">
      ${d.kind === "mother" ? `<button class="btn primary small" id="gd-recenter">
        <i class="fa-solid fa-arrow-left"></i> 返回此中心</button>`
      : (d.kind !== "center" ? `<button class="btn primary small" id="gd-recenter">
        <i class="fa-solid fa-bullseye"></i> 以此为中心</button>` : "")}
      ${d.arxiv_id ? `<button class="btn ghost small" id="gd-translate">
        <i class="fa-solid fa-language"></i> 翻译</button>` : ""}
      ${d.s2_id ? `<a class="btn ghost small" target="_blank"
        href="${d.s2_id.startsWith("W") ? "https://openalex.org/" + d.s2_id
             : "https://www.semanticscholar.org/paper/" + d.s2_id}">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> 数据页</a>` : ""}
    </div>`;
  const rbtn = $("#gd-recenter");
  if (rbtn) rbtn.addEventListener("click", () => {
    if (d.kind === "mother") goBackCenter(); else recenter(d);
  });
  const tbtn = $("#gd-translate");
  if (tbtn) tbtn.addEventListener("click", async () => {
    tbtn.disabled = true;
    try {
      await api("/api/tasks/paper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper: {
          title: d.title, year: d.year, venue: d.venue || "OpenAlex",
          pdf_url: d.arxiv_id ? `https://arxiv.org/pdf/${d.arxiv_id}` : null,
          arxiv_id: d.arxiv_id, source: "graph",
        }, dual: $("#dual-checkbox").checked }),
      });
      toast("已加入翻译任务", "ok");
      switchView("tasks");
      refreshTasks();
    } catch (e) {
      tbtn.disabled = false;
      toast("创建任务失败：" + e.message, "err");
    }
  });
}


/* ================= 图谱右键菜单：下载/翻译/阅读器/AI 分析 ================= */
function hideGraphCtx() { $("#graph-ctx").classList.add("hidden"); }
document.addEventListener("click", hideGraphCtx);
document.addEventListener("scroll", hideGraphCtx, true);

function showGraphCtx(ev, d) {
  const menu = $("#graph-ctx");
  menu.dataset.title = d.title;
  menu.dataset.s2id = d.s2_id;
  menu.dataset.arxiv = d.arxiv_id || "";
  menu.dataset.year = d.year || "";
  // 中心论文已翻译过，不重复提供翻译入口
  menu.querySelector('[data-act="translate"]').style.display =
    d.kind === "center" ? "none" : "flex";
  menu.classList.remove("hidden");
  const x = Math.min(ev.clientX + 4, window.innerWidth - 200);
  const y = Math.min(ev.clientY + 4, window.innerHeight - 190);
  menu.style.left = x + "px";
  menu.style.top = y + "px";
}

/* 复用同标题的已有任务，否则创建新任务（后端自动按标题补 arXiv 链接） */
async function ensureGraphTask(node) {
  const data = await api("/api/tasks?limit=100");
  const hit = data.tasks.find((t) =>
    t.title.trim().toLowerCase() === node.title.trim().toLowerCase());
  if (hit) return hit;
  return await api("/api/tasks/paper", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paper: {
      title: node.title, year: node.year, venue: node.venue || "OpenAlex",
      pdf_url: node.arxiv_id ? `https://arxiv.org/pdf/${node.arxiv_id}` : null,
      arxiv_id: node.arxiv_id, source: "graph",
    }, dual: $("#dual-checkbox").checked }),
  });
}

/* 等待任务的源 PDF 就绪（下载中 → has_source） */
async function waitForSource(taskId, timeoutMs = 90000) {
  const t0 = Date.now();
  while (Date.now() - t0 < timeoutMs) {
    const t = await api(`/api/tasks/${taskId}`);
    if (t.has_source) return t;
    if (t.status === "failed") throw new Error(t.error || "任务失败");
    await new Promise((r) => setTimeout(r, 1500));
  }
  throw new Error("下载超时，请稍后在任务列表重试");
}

async function graphAction(node, action) {
  hideGraphCtx();
  toast("正在准备：" + action, "info");
  try {
    const t = await ensureGraphTask(node);
    let fresh = t;
    if (action !== "translate" && !t.has_source) fresh = await waitForSource(t.id);
    if (action === "download") {
      const a = document.createElement("a");
      a.href = `/api/tasks/${t.id}/file/source`;
      a.download = "";
      document.body.appendChild(a);
      a.click();
      a.remove();
      toast("PDF 已开始下载", "ok");
    } else if (action === "translate") {
      toast("已加入翻译任务，可在任务列表查看进度", "ok");
      switchView("tasks");
      refreshTasks();
    } else if (action === "reader") {
      openViewer(t.id, [fresh.has_source ? "source" : "",
                        fresh.has_mono ? "mono" : "",
                        fresh.has_dual ? "dual" : ""].join(","));
    } else if (action === "ai") {
      openSummary(t.id);
    }
    refreshTasks();
  } catch (e) {
    toast(action + "失败：" + e.message, "err");
  }
}

$("#graph-ctx").querySelectorAll("button").forEach((b) =>
  b.addEventListener("click", (ev) => {
    ev.stopPropagation();
    const ds = $("#graph-ctx").dataset;
    const node = { title: ds.title, s2_id: ds.s2id,
                   arxiv_id: ds.arxiv === "" ? null : ds.arxiv,
                   year: ds.year ? Number(ds.year) : null, venue: "" };
    graphAction(node, b.dataset.act);
  }));


/* ================= AI 助手桌宠「小鱼」 ================= */
const chatHistory = [];      // [{role, content}]

const aiMessages = $("#ai-messages");
const aiInput = $("#ai-input");
const aiChat = $("#ai-chat");

document.addEventListener("pet:chat", () => {       // 桌宠右键 = 打开对话
  const opening = aiChat.classList.toggle("hidden");
  if (!opening) aiInput.focus();
  if (window.petAPI) window.petAPI.show();
});
$("#ai-close").addEventListener("click", () => aiChat.classList.add("hidden"));

function addMsg(role, content) {
  const div = document.createElement("div");
  div.className = "ai-msg " + role;
  if (role === "bot") div.innerHTML = '<div class="md">' + md(content) + "</div>";
  else div.textContent = content;
  aiMessages.appendChild(div);
  aiMessages.scrollTop = aiMessages.scrollHeight;
  return div;
}

function botTyping() {
  const div = document.createElement("div");
  div.className = "ai-typing";
  div.innerHTML = "<i></i><i></i><i></i>";
  aiMessages.appendChild(div);
  aiMessages.scrollTop = aiMessages.scrollHeight;
  return div;
}

// 首次打开对话面板时的欢迎语（右键桌宠触发）
let petWelcomed = false;
document.addEventListener("pet:chat", () => {
  if (!petWelcomed && !aiChat.classList.contains("hidden")) {
    petWelcomed = true;
    setTimeout(() => addMsg("bot",
      "嗨～我是小鱼 🐳 论文助手的首席问答官！\n\n可以问我：\n- 这个工具怎么用（翻译/批注/图谱…）\n- 论文里的概念、方法\n- 或者任何学习上的问题"), 350);
  }
});

let aiBusy = false;
async function sendChat() {
  const text = aiInput.value.trim();
  if (!text || aiBusy) return;
  aiBusy = true;
  aiInput.value = "";
  addMsg("user", text);
  const typing = botTyping();
  if (window.petAPI) window.petAPI.thinking(true);
  chatHistory.push({ role: "user", content: text });
  try {
    const r = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: chatHistory }),
    });
    typing.remove();
    chatHistory.push({ role: "assistant", content: r.reply });
    addMsg("bot", r.reply);
    if (window.petAPI) window.petAPI.thinking(false);
  } catch (e) {
    typing.remove();
    addMsg("bot", "⚠️ " + e.message);
    if (window.petAPI) { window.petAPI.thinking(false); window.petAPI.setEmotion("angry"); }
  } finally {
    aiBusy = false;
    aiMessages.scrollTop = aiMessages.scrollHeight;
  }
}
$("#ai-send").addEventListener("click", sendChat);
aiInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChat(); }
});
$("#ai-clear").addEventListener("click", () => {
  chatHistory.length = 0;
  aiMessages.innerHTML = "";
  addMsg("bot", "对话已清空～有什么新问题？");
});
// 开场气泡提示（8 秒后消失，之后悬停仍显示）
setTimeout(() => $("#pet-bubble").classList.add("show"), 2500);
setTimeout(() => $("#pet-bubble").classList.remove("show"), 11000);


/* ================= 桌宠设置视图 ================= */
function syncPetSettingsUI() {
  if (!window.petAPI) return;
  const c = window.petAPI.cfg;
  $("#pc-scale").value = Math.round(c.scale * 100);
  $("#pv-scale").textContent = Math.round(c.scale * 100) + "%";
  $("#pc-opacity").value = Math.round(c.opacity * 100);
  $("#pv-opacity").textContent = Math.round(c.opacity * 100) + "%";
  $("#pc-quiet").checked = !!c.quiet;
  $("#pc-calm").checked = !!c.calm;
  // 状态按钮高亮跟随当前动画状态
  const cur = window.petAPI.state;
  document.querySelectorAll(".ps-states button").forEach((x) =>
    x.classList.toggle("on", x.dataset.state === cur));
}

$("#pc-scale").addEventListener("input", (e) => {
  const v = Number(e.target.value) / 100;
  $("#pv-scale").textContent = e.target.value + "%";
  window.petAPI?.applyConfig({ scale: v });
});
$("#pc-opacity").addEventListener("input", (e) => {
  const v = Number(e.target.value) / 100;
  $("#pv-opacity").textContent = e.target.value + "%";
  window.petAPI?.applyConfig({ opacity: v });
});
$("#pc-quiet").addEventListener("change", (e) =>
  window.petAPI?.applyConfig({ quiet: e.target.checked }));
$("#pc-calm").addEventListener("change", (e) =>
  window.petAPI?.applyConfig({ calm: e.target.checked }));
$("#pc-resetpos").addEventListener("click", () => {
  window.petAPI?.resetPos();
  toast("小鱼已回到默认位置", "ok");
});
$("#pc-hide").addEventListener("click", () => {
  window.petAPI?.hide();
  toast("小鱼已隐藏（在「翻译论文」右下角点 👁 唤回）", "info");
});

// 状态动画手动预览
petViewStateBound = false;
document.addEventListener("click", (e) => {
  const b = e.target.closest?.(".ps-states button");
  if (!b) return;
  window.petAPI?.setState(b.dataset.state, true);
  document.querySelectorAll(".ps-states button").forEach((x) =>
    x.classList.toggle("on", x === b));
});


/* ================= 个性化背景 ================= */
const bgCfg = Object.assign(
  { mode: "library", brightness: 100, blur: 0 },
  JSON.parse(localStorage.getItem("app-bg") || "{}")
);

const BG_BUILTIN = {
  library: "/static/img/bg-library.jpg",
  reading: "/static/img/bg-reading.jpg",
};

function bgSave() {
  try { localStorage.setItem("app-bg", JSON.stringify(bgCfg)); } catch { }
}

function applyBg() {
  const imgEl = document.getElementById("app-bg-img");
  const tintEl = document.getElementById("app-bg-tint");
  if (!imgEl || !tintEl) return;
  const dark = document.documentElement.dataset.theme === "dark";

  // 图片层
  let url = null;
  if (bgCfg.mode === "library") url = BG_BUILTIN.library;
  else if (bgCfg.mode === "reading") url = BG_BUILTIN.reading;
  else if (bgCfg.mode === "custom") url = "/api/bg-custom";
  imgEl.style.backgroundImage = url ? `url("${url}")` : "none";
  imgEl.style.display = url ? "block" : "none";
  imgEl.style.filter = `brightness(${bgCfg.brightness}%) blur(${bgCfg.blur}px)`;

  // 柔光层：亮度过高时加深保护，保证前景可读
  const over = dark ? 0.78 : 0.62;
  const extra = Math.max(0, (bgCfg.brightness - 100)) / 100 * 0.45;
  const alpha = Math.max(0.08, Math.min(0.9, over + extra));
  tintEl.style.background = dark
    ? `rgba(10, 12, 20, ${alpha.toFixed(2)})`
    : `rgba(255, 249, 238, ${alpha.toFixed(2)})`;

  // 同步高亮与滑块（设置视图存在时）
  document.querySelectorAll(".bg-mode").forEach((b) =>
    b.classList.toggle("on", b.dataset.bgm === bgCfg.mode));
  const pb = $("#pv-bright"), pl = $("#pv-blur");
  if (pb) pb.textContent = bgCfg.brightness + "%";
  if (pl) pl.textContent = bgCfg.blur + "px";
  const sb = $("#bg-brightness"), sl = $("#bg-blur");
  if (sb) sb.value = bgCfg.brightness;
  if (sl) sl.value = bgCfg.blur;
}

function bindBgControls() {
  document.querySelectorAll(".bg-mode").forEach((b) =>
    b.addEventListener("click", () => {
      bgCfg.mode = b.dataset.bgm;
      bgSave(); applyBg();
    }));
  $("#bg-brightness").addEventListener("input", (e) => {
    bgCfg.brightness = Number(e.target.value);
    bgSave(); applyBg();
  });
  $("#bg-blur").addEventListener("input", (e) => {
    bgCfg.blur = Number(e.target.value);
    bgSave(); applyBg();
  });
  $("#bg-upload").addEventListener("change", async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    $("#bg-msg").textContent = "上传中…";
    try {
      await api("/api/background/upload", { method: "POST", body: fd });
      bgCfg.mode = "custom"; bgSave(); applyBg();
      $("#bg-msg").textContent = "✅ 已应用为背景";
      window.__bgTs = Date.now(); applyBg();
      toast("自定义背景已启用", "ok");
    } catch (err) {
      $("#bg-msg").textContent = "上传失败：" + err.message;
    }
  });
  $("#bg-remove-custom").addEventListener("click", async () => {
    try {
      await api("/api/background/custom", { method: "DELETE" });
      $("#bg-msg").textContent = "已删除自定义背景";
      toast("已删除", "ok");
      refreshBgThumb();
    } catch (e) { toast("删除失败：" + e.message, "err"); }
  });
  $("#bg-reset").addEventListener("click", () => {
    Object.assign(bgCfg, { mode: "library", brightness: 100, blur: 0 });
    bgSave(); applyBg();
    toast("已恢复默认背景", "ok");
  });
}

async function refreshBgThumb() {
  try {
    const st = await api("/api/background/status");
    const btn = document.querySelector('.bg-mode[data-bgm="custom"]');
    const img = btn.querySelector("img");
    if (st.custom) {
      img.src = "/api/bg-custom?t=" + Date.now();
      img.style.display = "block";
      btn.querySelector("span").textContent = "我的背景";
    }
  } catch { /* 忽略 */ }
}

// 主题切换时重算柔光颜色
$("#theme-btn").addEventListener("click", () => setTimeout(applyBg, 50));


// 背景初始化（文件末尾调用：此时所有 const 已初始化）
applyBg();
bindBgControls();