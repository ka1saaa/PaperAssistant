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
    "https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js";
}

const V = { task: null, kinds: {}, kind: "source", doc: null, page: 1, scale: 1.0,
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
const G = { task: null, center: null, satellites: [], sim: null, svg: null, g: null,
            width: 0, height: 0, history: [], loading: false };

const KIND_META = {
  center: { label: "中心论文", color: "#4f6ef7", r: 26 },
  ref:    { label: "中心引用的", color: "#8f6bff", r: 16 },
  cite:   { label: "引用中心的", color: "#18a058", r: 16 },
};

function switchToGraphView() {
  $$(".nav-item").forEach((b) => b.classList.toggle("active", b.dataset.view === "graph"));
  $$(".view").forEach((v) => v.classList.toggle("active", v.id === "view-graph"));
}

async function openGraph(taskId) {
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
  }
}

/* 关系翻转：卫星变中心后，原中心相对新中心的关系取反 */
function flipRel(rel) { return rel === "ref" ? "cite" : "ref"; }

function setCenter(node, references, citations) {
  G.center = { ...node, rel: "center", kind: "center" };
  const sats = [];
  for (const n of references || []) sats.push({ ...n, rel: "ref", kind: "ref" });
  for (const n of citations || []) sats.push({ ...n, rel: "cite", kind: "cite" });
  G.satellites = sats;
  $("#graph-sub").textContent = `中心论文：${G.center.title}（引用网络免费来自 OpenAlex / Semantic Scholar）`;
}

/* 点击卫星：以此论文为新中心重新辐射（原中心降为卫星，关系取反） */
async function recenter(node) {
  if (G.loading) return;
  G.loading = true;
  const oldCenter = G.center;
  $("#graph-loading").classList.remove("hidden");
  $("#graph-loading").innerHTML =
    `<span class="spin big"></span><p>正在以《${escapeHtml(node.title.slice(0, 40))}》为中心加载相关论文…</p>`;
  try {
    const d = await api(`/api/graph/node/${node.s2_id}`);
    G.history.push(oldCenter);
    const oldAsSat = { ...oldCenter, rel: flipRel(node.rel), kind: node.rel };
    setCenter(node, d.references, d.citations);
    if (!G.satellites.some((n) => n.s2_id === oldAsSat.s2_id)) {
      G.satellites.push(oldAsSat);
    }
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

/* 返回上一中心（邻居数据在服务端缓存里，秒回） */
async function goBackCenter() {
  if (!G.history.length || G.loading) return;
  G.loading = true;
  const prev = G.history.pop();
  const oldCenter = G.center;
  $("#graph-loading").classList.remove("hidden");
  $("#graph-loading").innerHTML = '<span class="spin big"></span>';
  try {
    const d = await api(`/api/graph/node/${prev.s2_id}`);
    const oldAsSat = { ...oldCenter, rel: flipRel(prev.__lastRel || "ref"), kind: "cite" };
    setCenter(prev, d.references, d.citations);
    if (!G.satellites.some((n) => n.s2_id === oldAsSat.s2_id)) G.satellites.push(oldAsSat);
    $("#graph-loading").classList.add("hidden");
    renderGraph(true);
    showGraphDetail(G.center);
  } catch (e) {
    G.history.push(prev);
    $("#graph-loading").classList.add("hidden");
    toast(e.message, "err");
  } finally {
    G.loading = false;
  }
}

function renderGraph(animate) {
  const wrap = $("#graph-wrap");
  G.width = wrap.clientWidth || 900;
  G.height = wrap.clientHeight || 620;

  if (!G.svg) {
    G.svg = d3.select("#graph-svg");
    G.g = G.svg.append("g");
    G.g.append("g").attr("class", "links");
    G.g.append("g").attr("class", "nodes");
    G.svg.call(d3.zoom().scaleExtent([0.4, 3]).on("zoom",
      (ev) => G.g.attr("transform", ev.transform)));
    G.svg.on("click", () => $("#graph-detail").classList.add("hidden"));
  }
  G.svg.attr("viewBox", [-G.width / 2, -G.height / 2, G.width, G.height]);

  const nodes = [G.center, ...G.satellites];
  const links = G.satellites.map((n) => ({ source: G.center, target: n }));

  const linkSel = G.g.select("g.links").selectAll("line").data(links,
    (l) => l.target.s2_id);
  linkSel.exit().remove();
  linkSel.enter().append("line")
    .attr("class", (l) => (l.target.rel === "ref" ? "lref" : "lcite"));

  const nodeSel = G.g.select("g.nodes").selectAll("g.node").data(nodes, (d) => d.s2_id);
  nodeSel.exit().remove();

  const nodeEnter = nodeSel.enter().append("g").attr("class", "node")
    .attr("cursor", "pointer")
    .on("click", (ev, d) => {
      ev.stopPropagation();
      if (d.kind === "center") { showGraphDetail(d); return; }
      d.__lastRel = d.rel;
      recenter(d);
    });
  nodeEnter.append("circle").attr("class", "dot");
  nodeEnter.append("text").attr("class", "nlabel")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => (d.kind === "center" ? 44 : 30));

  const all = nodeEnter.merge(nodeSel);
  all.select("circle.dot")
    .attr("r", (d) => (d.kind === "center" ? 26 : 16))
    .attr("fill", (d) => KIND_META[d.kind].color)
    .attr("stroke", (d) => (d.kind === "center" ? "#fff" : "transparent"))
    .attr("stroke-width", (d) => (d.kind === "center" ? 3 : 0));
  all.select("text.nlabel")
    .text((d) => (d.title.length > 26 ? d.title.slice(0, 24) + "…" : d.title))
    .attr("font-size", (d) => (d.kind === "center" ? 15 : 12));

  if (G.sim) G.sim.stop();
  G.sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.s2_id).distance(150).strength(0.6))
    .force("collide", d3.forceCollide(46))
    .force("charge", d3.forceManyBody().strength(-360))
    .alpha(animate ? 0.9 : 0.6)
    .on("tick", () => {
      G.g.select("g.links").selectAll("line")
        .attr("x1", (l) => l.source.x).attr("y1", (l) => l.source.y)
        .attr("x2", (l) => l.target.x).attr("y2", (l) => l.target.y);
      all.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });
  G.center.fx = 0; G.center.fy = 0;
}

function showGraphDetail(d) {
  const box = $("#graph-detail");
  box.classList.remove("hidden");
  const kindName = d.kind === "center" ? "中心论文"
    : (d.rel === "ref" ? "中心引用的论文" : "引用中心论文的论文");
  box.innerHTML = `
    <div class="kw-head"><i class="fa-solid fa-book-open"></i>
      <b>${escapeHtml(d.title.slice(0, 60))}</b></div>
    <div class="paper-sub" style="margin:6px 0 10px">
      ${d.year || "—"} · ${escapeHtml(d.venue || "未知来源")} · 被引 ${d.citation_count}
      · ${kindName}</div>
    <div class="graph-detail-btns">
      ${d.kind !== "center" ? `<button class="btn primary small" id="gd-recenter">
        <i class="fa-solid fa-bullseye"></i> 以此为中心</button>` : ""}
      ${d.arxiv_id ? `<button class="btn ghost small" id="gd-translate">
        <i class="fa-solid fa-language"></i> 翻译</button>` : ""}
      ${d.s2_id ? `<a class="btn ghost small" target="_blank"
        href="${d.s2_id.startsWith("W") ? "https://openalex.org/" + d.s2_id
             : "https://www.semanticscholar.org/paper/" + d.s2_id}">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> 数据页</a>` : ""}
    </div>`;
  const rbtn = $("#gd-recenter");
  if (rbtn) rbtn.addEventListener("click", () => recenter(d));
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
