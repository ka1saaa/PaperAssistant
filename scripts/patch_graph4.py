# -*- coding: utf-8 -*-
"""图谱视觉改版：
1. 母类节点固定锚定左上角，中心/母类名称不再叠加
2. 节点渐变填充 + 柔和阴影 + 文字描边，更好看
3. 切换中心时淡入淡出 + 涟漪级联过渡动画
"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "static" / "app.js"
s = p.read_text(encoding="utf-8")

marker = "/* ================= 文献图谱（切换式中心导航） ================= */"
idx = s.index(marker)

new_block = '''/* ================= 文献图谱（切换式中心导航） ================= */
const G = { task: null, center: null, mother: null, satellites: [], sim: null,
            svg: null, g: null, defs: null, width: 0, height: 0,
            history: [], loading: false };

const KIND_META = {
  center: { label: "中心论文", grad: "gBlue", color: "#4f6ef7", r: 30 },
  mother: { label: "母类（上一中心）", grad: "gMother", color: "#7b93f8", r: 18 },
  ref:    { label: "中心引用的", grad: "gPurple", color: "#8f6bff", r: 17 },
  cite:   { label: "引用中心的", grad: "gGreen", color: "#18a058", r: 17 },
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
  }
}

function flipRel(rel) { return rel === "ref" ? "cite" : "ref"; }

function setCenter(node, references, citations) {
  G.center = { ...node, rel: "center", kind: "center" };
  const sats = [];
  for (const n of references || []) sats.push({ ...n, rel: "ref", kind: "ref" });
  for (const n of citations || []) sats.push({ ...n, rel: "cite", kind: "cite" });
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
  grad("gPurple", "#a98bff", "#7a4fe0");
  grad("gGreen", "#3ed17e", "#0f8a4d");
  const f = defs.append("filter").attr("id", "softShadow")
    .attr("x", "-60%").attr("y", "-60%").attr("width", "220%").attr("height", "220%");
  f.append("feDropShadow").attr("dx", 0).attr("dy", 3)
    .attr("stdDeviation", 4).attr(" flood-color", "rgba(23,29,47,.35)");
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
      if (d.kind === "center") { showGraphDetail(d); return; }
      if (d.kind === "mother") { goBackCenter(); return; }
      recenter(d);
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
    .attr("fill", (d) => `url(#${KIND_META[d.kind].grad})`);
  all.select("circle.halo")
    .attr("r", (d) => KIND_META[d.kind].r + 7)
    .attr("fill", (d) => `url(#${KIND_META[d.kind].grad})`)
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
  G.sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id((d) => d.s2_id).distance(150).strength(0.6))
    .force("collide", d3.forceCollide(54))
    .force("charge", d3.forceManyBody().strength(-360))
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
'''

assert marker in s
idx = s.index(marker)
s = s[:idx] + new_block
p.write_text(s, encoding="utf-8")
print("视觉改版完成")
