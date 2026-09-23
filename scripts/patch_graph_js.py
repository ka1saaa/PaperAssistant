# -*- coding: utf-8 -*-
"""向 app/static/app.js 注入文献图谱逻辑。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

# 1) 任务卡图谱按钮
old = '  const readable = !running && (t.has_source || t.has_mono || t.has_dual);'
new = '''  const readable = !running && (t.has_source || t.has_mono || t.has_dual);
  if (!running) actions.push(
    `<button class="act graph" data-graph="${t.id}" title="引用辐射图">
       <i class="fa-solid fa-circle-nodes"></i> 图谱</button>`);'''
assert old in s
s = s.replace(old, new, 1)

# 2) 绑定
old2 = '''    ul.querySelectorAll("[data-read]").forEach((b) =>
      b.addEventListener("click", () => openViewer(b.dataset.read, b.dataset.kinds)));'''
new2 = old2 + '''
    ul.querySelectorAll("[data-graph]").forEach((b) =>
      b.addEventListener("click", () => openGraph(b.dataset.graph)));'''
assert old2 in s
s = s.replace(old2, new2, 1)

graph_code = '''
/* ================= 文献图谱 ================= */
const G = { task: null, nodes: [], links: [], byId: {}, sim: null, svg: null, g: null,
            width: 0, height: 0, expanded: new Set() };

const KIND_META = {
  center: { label: "中心论文", color: "#4f6ef7", r: 26 },
  ref:    { label: "它引用的", color: "#8f6bff", r: 15 },
  cite:   { label: "引用了它的", color: "#18a058", r: 15 },
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
  $("#graph-sub").innerHTML = '<span class="spin"></span> 正在从 Semantic Scholar 解析论文与引用网络…';

  try {
    const d = await api(`/api/tasks/${taskId}/graph`);
    G.task = await api(`/api/tasks/${taskId}`);
    $("#graph-sub").textContent = `中心论文：${d.node.title || G.task.title}（数据来源：Semantic Scholar，免费）`;
    initGraph(d.node, d.references, d.citations);
  } catch (e) {
    $("#graph-sub").textContent = "图谱生成失败";
    const err = $("#graph-error");
    err.classList.remove("hidden");
    err.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(e.message)}`;
  }
}

function initGraph(center, references, citations) {
  G.nodes = []; G.links = []; G.byId = {}; G.expanded = new Set();
  const centerNode = { ...center, kind: "center", x: 0, y: 0, fx: 0, fy: 0 };
  addNode(centerNode);
  for (const n of references) addNeighbor(centerNode, { ...n, kind: "ref" });
  for (const n of citations) addNeighbor(centerNode, { ...n, kind: "cite" });
  G.expanded.add(center.s2_id);
  renderGraph();
  $("#graph-wrap").classList.remove("hidden");
}

function addNode(node) {
  if (G.byId[node.s2_id]) return G.byId[node.s2_id];
  G.byId[node.s2_id] = node;
  G.nodes.push(node);
  return node;
}

function addNeighbor(parent, child) {
  if (G.byId[child.s2_id]) {
    if (!G.links.some((l) => l.source.s2_id === parent.s2_id && l.target.s2_id === child.s2_id)) {
      G.links.push({ source: parent, target: G.byId[child.s2_id] });
    }
    return;
  }
  const node = addNode(child);
  G.links.push({ source: parent, target: node });
}

function renderGraph() {
  const wrap = $("#graph-wrap");
  G.width = wrap.clientWidth || 900;
  G.height = wrap.clientHeight || 620;

  if (!G.svg) {
    G.svg = d3.select("#graph-svg");
    G.g = G.svg.append("g");
    G.g.append("g").attr("class", "links");
    G.g.append("g").attr("class", "nodes");
    G.svg.call(d3.zoom().scaleExtent([0.3, 3]).on("zoom",
      (ev) => G.g.attr("transform", ev.transform)));
  }
  G.svg.attr("viewBox", [-G.width / 2, -G.height / 2, G.width, G.height]);

  const nodeSel = G.g.select("g.nodes").selectAll("g.node").data(G.nodes, (d) => d.s2_id);
  nodeSel.exit().remove();

  const nodeEnter = nodeSel.enter().append("g").attr("class", "node")
    .attr("cursor", "pointer")
    .call(d3.drag()
      .on("start", (ev, d) => { if (!ev.active) G.sim.alphaTarget(0.25).restart(); d.fx = d.x; d.fy = d.y; })
      .on("drag", (ev, d) => { d.fx = ev.x; d.fy = ev.y; })
      .on("end", (ev, d) => { if (!ev.active) G.sim.alphaTarget(0); }))
    .on("click", (ev, d) => { ev.stopPropagation(); onNodeClick(d); });

  nodeEnter.append("circle").attr("class", "ring");
  nodeEnter.append("circle").attr("class", "dot");
  nodeEnter.append("text").attr("class", "nlabel")
    .attr("text-anchor", "middle")
    .attr("dy", (d) => (d.kind === "center" ? 44 : 28));

  const all = nodeEnter.merge(nodeSel);
  all.select("circle.dot")
    .attr("r", (d) => KIND_META[d.kind].r)
    .attr("fill", (d) => KIND_META[d.kind].color)
    .attr("stroke", (d) => (G.expanded.has(d.s2_id) ? "var(--text)" : "transparent"))
    .attr("stroke-width", 2);
  all.select("text.nlabel")
    .text((d) => (d.title.length > 26 ? d.title.slice(0, 24) + "…" : d.title))
    .attr("font-size", (d) => (d.kind === "center" ? 15 : 12));

  const linkSel = G.g.select("g.links").selectAll("line")
    .data(G.links, (l) => l.source.s2_id + "->" + l.target.s2_id);
  linkSel.exit().remove();
  linkSel.enter().append("line")
    .attr("class", (l) => (l.target.kind === "ref" ? "lref" : "lcite"));

  if (G.sim) G.sim.stop();
  G.sim = d3.forceSimulation(G.nodes)
    .force("link", d3.forceLink(G.links).id((d) => d.s2_id).distance(130).strength(0.5))
    .force("collide", d3.forceCollide((d) => KIND_META[d.kind].r + 24))
    .force("charge", d3.forceManyBody().strength(-320))
    .on("tick", () => {
      G.g.select("g.links").selectAll("line")
        .attr("x1", (l) => l.source.x).attr("y1", (l) => l.source.y)
        .attr("x2", (l) => l.target.x).attr("y2", (l) => l.target.y);
      all.attr("transform", (d) => `translate(${d.x},${d.y})`);
    });
  const c = G.nodes.find((n) => n.kind === "center");
  if (c) { c.fx = 0; c.fy = 0; }
}

async function onNodeClick(d) {
  showGraphDetail(d);
  if (G.expanded.has(d.s2_id) || d.kind === "center") return;
  G.expanded.add(d.s2_id);
  const detail = $("#graph-detail");
  detail.insertAdjacentHTML("beforeend",
    '<div class="kw-loading"><span class="spin"></span> 展开该论文的相关研究…</div>');
  try {
    const data = await api(`/api/graph/node/${d.s2_id}`);
    detail.querySelector(".kw-loading")?.remove();
    for (const n of data.references) addNeighbor(d, { ...n, kind: "ref" });
    for (const n of data.citations) addNeighbor(d, { ...n, kind: "cite" });
    renderGraph();
  } catch (e) {
    detail.querySelector(".kw-loading")?.remove();
    toast(e.message, "err");
    G.expanded.delete(d.s2_id);
  }
}

function showGraphDetail(d) {
  const box = $("#graph-detail");
  box.classList.remove("hidden");
  const kindName = d.kind === "center" ? "中心论文"
    : (d.kind === "ref" ? "它引用的论文" : "引用了它的论文");
  box.innerHTML = `
    <div class="kw-head"><i class="fa-solid fa-book-open"></i>
      <b>${escapeHtml(d.title.slice(0, 60))}</b></div>
    <div class="paper-sub" style="margin:6px 0 10px">
      ${d.year || "—"} · ${escapeHtml(d.venue || "未知来源")} · 被引 ${d.citation_count}
      · ${kindName}</div>
    <div class="graph-detail-btns">
      ${d.arxiv_id ? `<button class="btn primary small" id="gd-translate">
        <i class="fa-solid fa-language"></i> 翻译此论文</button>` : ""}
      ${d.s2_id ? `<a class="btn ghost small" target="_blank"
        href="https://www.semanticscholar.org/paper/${d.s2_id}">
        <i class="fa-solid fa-arrow-up-right-from-square"></i> S2 页面</a>` : ""}
    </div>`;
  const tbtn = $("#gd-translate");
  if (tbtn) tbtn.addEventListener("click", async () => {
    tbtn.disabled = true;
    try {
      await api("/api/tasks/paper", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paper: {
          title: d.title, year: d.year, venue: d.venue || "Semantic Scholar",
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

assert "/* ================= 文献图谱" not in s, "已注入过"
s = s.rstrip() + "\n" + graph_code
p.write_text(s, encoding="utf-8")
print("注入完成")
