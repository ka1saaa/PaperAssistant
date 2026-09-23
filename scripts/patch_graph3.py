# -*- coding: utf-8 -*-
"""图谱颜色改版：母类保留原蓝色方便切回；子类按关系紧密度深浅渐变。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

marker = "/* ================= 文献图谱（切换式中心导航） ================= */"
idx = s.index(marker)

new_block = '''/* ================= 文献图谱（切换式中心导航） ================= */
const G = { task: null, center: null, mother: null, satellites: [], sim: null,
            svg: null, g: null, width: 0, height: 0, history: [], loading: false };

const KIND_META = {
  center: { label: "中心论文", color: "#4f6ef7", r: 26 },
  mother: { label: "母类（上一中心）", color: "#4f6ef7", r: 18 },
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
    G.mother = null;
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

/* 卫星深浅渐变：按被引数（关系紧密程度）排名，越紧密颜色越深 */
function applyGradient(sel) {
  const sats = sel.filter((d) => d.kind !== "center" && d.kind !== "mother");
  sats.sort((a, b) => (b.citation_count || 0) - (a.citation_count || 0));
  sats.each((d, i) => {
    const fade = Math.max(0.45, 1 - i * 0.11);   // 排名越靠后越浅
    d3.select(this).select("circle.dot").attr("fill-opacity", fade);
  });
}

/* 点击卫星：以此论文为新中心；母类颜色保持不变，方便切回 */
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

/* 返回上一中心（母类）：数据在服务端缓存里，秒回 */
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
    // 原中心降为新中心的母类，颜色保持蓝色不变
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

  const nodes = [G.center, ...(G.mother ? [G.mother] : []), ...G.satellites];
  const links = [];
  for (const n of G.satellites) links.push({ source: G.center, target: n });
  if (G.mother) links.push({ source: G.center, target: G.mother, mother: true });

  const linkSel = G.g.select("g.links").selectAll("line").data(links,
    (l) => (l.mother ? "M" : "") + l.target.s2_id);
  linkSel.exit().remove();
  linkSel.enter().append("line")
    .attr("class", (l) => (l.mother ? "lmother" : (l.target.rel === "ref" ? "lref" : "lcite")));

  const nodeSel = G.g.select("g.nodes").selectAll("g.node").data(nodes, (d) => d.s2_id);
  nodeSel.exit().remove();

  const nodeEnter = nodeSel.enter().append("g").attr("class", "node")
    .attr("cursor", "pointer")
    .on("click", (ev, d) => {
      ev.stopPropagation();
      if (d.kind === "center") { showGraphDetail(d); return; }
      if (d.kind === "mother") { goBackCenter(); return; }
      recenter(d);
    });
  nodeEnter.append("circle").attr("class", "dot");
  nodeEnter.append("text").attr("class", "mbadge")
    .attr("text-anchor", "middle").attr("dy", -24)
    .text((d) => (d.kind === "mother" ? "母类" : ""))
    .attr("font-size", 11).attr("fill", "#4f6ef7").attr("font-weight", 700);
  nodeEnter.append("text").attr("class", "nlabel")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => (d.kind === "center" ? 44 : 30));

  const all = nodeEnter.merge(nodeSel);
  all.select("circle.dot")
    .attr("r", (d) => (d.kind === "center" ? 26 : (d.kind === "mother" ? 18 : 16)))
    .attr("fill", (d) => KIND_META[d.kind].color)
    .attr("fill-opacity", (d) => (d.kind === "center" || d.kind === "mother" ? 1 : null))
    .attr("stroke", (d) => (d.kind === "mother" ? "#94a8ff" : (d.kind === "center" ? "#fff" : "transparent")))
    .attr("stroke-dasharray", (d) => (d.kind === "mother" ? "5,3" : null))
    .attr("stroke-width", (d) => (d.kind === "center" ? 3 : (d.kind === "mother" ? 2 : 0)));
  all.select("text.nlabel")
    .text((d) => (d.title.length > 26 ? d.title.slice(0, 24) + "…" : d.title))
    .attr("font-size", (d) => (d.kind === "center" ? 15 : 12));

  applyGradient(all);
  // 卫星渐变随数据刷新
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
'''

assert marker in s
idx = s.index(marker)
s = s[:idx] + new_block
p.write_text(s, encoding="utf-8")
print("颜色改版完成")
