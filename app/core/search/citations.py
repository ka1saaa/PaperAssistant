"""论文引用图谱数据层。

主源 OpenAlex（完全免费、无 Key、日限 10 万次），兜底 Semantic Scholar。
节点 id 统一为字符串（OpenAlex 的 W-id 或 S2 的 40 位哈希），前端不感知来源。
"""
import asyncio
import logging
import re

import httpx

logger = logging.getLogger(__name__)

OA_BASE = "https://api.openalex.org"
S2_BASE = "https://api.semanticscholar.org/graph/v1"
MAILTO = "paperassistant@local"   # OpenAlex 礼貌池标识
LIMIT_EACH = 5
SELECT = "id,display_name,publication_year,cited_by_count,doi,primary_location"

# {node_id: {"node": {...}, "references": [...], "citations": [...]}}
_CACHE: dict[str, dict] = {}
_RESOLVE_FAIL: set[str] = set()

_ARXIV_RE = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5}|[a-z\-]+/\d{7})", re.IGNORECASE)


def extract_pdf_meta(pdf_path) -> tuple[str | None, str | None]:
    """从 PDF 首页提取 (arXiv ID, 真实标题)。

    标题启发式：第一页字号最大的文本行（排除页眉页脚/侧边栏）。
    """
    import fitz

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]
        text = page.get_text("text")
        arxiv_id = None
        m = _ARXIV_RE.search(text)
        if m:
            arxiv_id = m.group(1)

        best, best_size = None, 0.0
        for block in page.get_text("dict").get("blocks") or []:
            for line in block.get("lines") or []:
                d = line.get("dir") or (1, 0)
                if abs(d[0] - 1) > 0.01:      # 跳过竖排文本（arXiv 侧边水印）
                    continue
                line_text, line_size = "", 0.0
                for span in line.get("spans") or []:
                    t = span.get("text") or ""
                    if t.strip():
                        line_text += t
                        line_size = max(line_size, span.get("size") or 0)
                if line_text.strip().lower().startswith("arxiv"):
                    continue                   # arXiv 水印戳字号最大但不是标题
                if line_size > best_size and len(line_text.strip()) >= 8:
                    best, best_size = line_text.strip(), line_size
        doc.close()
        title = best if best and best_size >= 12 else None   # 排除小字号页眉
        return arxiv_id, title
    except Exception:  # noqa: BLE001 — 打不开就走文件名标题
        return None, None


class GraphError(RuntimeError):
    """带用户可读信息的图谱数据获取失败。"""


def _oa_node(payload: dict) -> dict:
    """OpenAlex work → 统一节点。"""
    wid = (payload.get("id") or "").rsplit("/", 1)[-1]
    doi = payload.get("doi") or ""
    arxiv = None
    m = re.search(r"10\.48550/arxiv\.(.+)$", doi, re.IGNORECASE)
    if m:
        arxiv = m.group(1)
    loc = payload.get("primary_location") or {}
    source = loc.get("source") or {}
    return {
        "s2_id": wid,                                   # 通用节点 id（历史命名）
        "title": (payload.get("display_name") or "").strip(),
        "year": payload.get("publication_year"),
        "venue": (source.get("display_name") or "").strip(),
        "citation_count": payload.get("cited_by_count") or 0,
        "arxiv_id": arxiv,
    }


def _s2_node(payload: dict) -> dict:
    ext = payload.get("externalIds") or {}
    return {
        "s2_id": payload.get("paperId") or "",
        "title": (payload.get("title") or "").strip(),
        "year": payload.get("year"),
        "venue": payload.get("venue") or "",
        "citation_count": payload.get("citationCount") or 0,
        "arxiv_id": ext.get("ArXiv"),
    }


def _w_id(full: str) -> str:
    return (full or "").rsplit("/", 1)[-1]


def _closest(nodes: list[dict], limit: int = LIMIT_EACH) -> list[dict]:
    """按被引数降序取关系最紧密的前 limit 篇（不硬凑数量）。"""
    pool = [n for n in nodes if n.get("title")]
    pool.sort(key=lambda n: n.get("citation_count") or 0, reverse=True)
    return pool[:limit]
    return (full or "").rsplit("/", 1)[-1]


async def _oa_get(client: httpx.AsyncClient, url: str, params: dict) -> httpx.Response:
    """OpenAlex 请求，5xx/网络抖动重试一次。"""
    params = {**params, "mailto": MAILTO}
    for wait in (0, 1.5):
        if wait:
            await asyncio.sleep(wait)
        try:
            r = await client.get(url, params=params, timeout=25.0)
        except httpx.HTTPError:
            if wait:
                raise
            continue
        if r.status_code < 500 or wait:
            return r
    return r


async def _resolve_oa(title: str, arxiv_id: str | None) -> dict | None:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        if arxiv_id:
            r = await _oa_get(client, f"{OA_BASE}/works/doi:10.48550/arxiv.{arxiv_id}",
                              {"select": SELECT})
            if r.status_code == 200:
                return _oa_node(r.json())
        if title:
            r = await _oa_get(client, f"{OA_BASE}/works",
                              {"filter": f"title.search:{title}", "per_page": 1,
                               "select": SELECT})
            if r.status_code == 200:
                results = r.json().get("results") or []
                if results:
                    return _oa_node(results[0])
    return None


async def _resolve_s2(title: str, arxiv_id: str | None) -> dict | None:
    waits = (0, 1.5, 3.0, 5.0)
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        if arxiv_id:
            for wait in waits:
                if wait:
                    await asyncio.sleep(wait)
                r = await client.get(f"{S2_BASE}/paper/arXiv:{arxiv_id}",
                                     params={"fields": "paperId,title,year,venue,externalIds,citationCount"})
                if r.status_code == 200:
                    return _s2_node(r.json())
                if r.status_code != 429:
                    break
        if title:
            for wait in waits:
                if wait:
                    await asyncio.sleep(wait)
                r = await client.get(f"{S2_BASE}/paper/search/match",
                                     params={"query": title, "fields": "paperId,title,year,venue,externalIds,citationCount"})
                if r.status_code == 200:
                    data = r.json().get("data") or []
                    if data:
                        return _s2_node(data[0])
                if r.status_code != 429:
                    break
    return None


async def resolve_center(fallback_title: str, pdf_path=None) -> dict:
    """把任务论文解析为图谱中心节点。

    解析顺序：arXiv ID → PDF 提取的真实标题 → 文件名标题。
    每个候选依次尝试 OpenAlex 标题匹配与 Semantic Scholar 标题匹配。
    """
    arxiv_id, real_title = (None, None)
    if pdf_path:
        arxiv_id, real_title = extract_pdf_meta(pdf_path)
    candidates: list[str] = []
    for t in (real_title, fallback_title):
        if t and t.strip() and t.strip()[:100] not in candidates:
            candidates.append(t.strip()[:100])

    for cand in candidates:
        node = await _resolve_oa(cand, arxiv_id)
        if node is None:
            node = await _resolve_s2(cand, arxiv_id)
        if node is not None:
            logger.info("graph center resolved: %s (%s)", node["title"][:40], node["s2_id"])
            return node

    raise GraphError("未能匹配到该论文的引用数据（OpenAlex / Semantic Scholar 均未收录），"
                     "可能是标题特殊或数据源未收录")


async def _oa_neighbors(wid: str) -> dict:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        # 1) 节点自身（拿 referenced_works）
        r = await _oa_get(client, f"{OA_BASE}/works/{wid}",
                          {"select": "id,display_name,publication_year,cited_by_count,doi,primary_location,referenced_works"})
        if r.status_code != 200:
            raise GraphError(f"论文数据获取失败（HTTP {r.status_code}）")
        work = r.json()
        node = _oa_node(work)

        # 2) 它引用的：候选池 8 篇批量查详情，按被引数排序取前 5（关系最紧密优先）
        references: list[dict] = []
        ref_ids = [_w_id(x) for x in (work.get("referenced_works") or [])][:8]
        if ref_ids:
            r2 = await _oa_get(client, f"{OA_BASE}/works",
                               {"filter": f"openalex_id:{'|'.join(ref_ids)}",
                                "per_page": 8, "select": SELECT})
            if r2.status_code == 200:
                pool = [_oa_node(x) for x in r2.json().get("results") or []]
                references = _closest(pool)

        # 3) 引用了它的：按被引数取前 5
        citations: list[dict] = []
        r3 = await _oa_get(client, f"{OA_BASE}/works",
                           {"filter": f"cites:{wid}", "sort": "cited_by_count:desc",
                            "per_page": LIMIT_EACH, "select": SELECT})
        if r3.status_code == 200:
            citations = _closest([_oa_node(x) for x in r3.json().get("results") or []])

        return {"node": node, "references": references, "citations": citations}


async def _s2_neighbors(s2_id: str) -> dict:
    async with httpx.AsyncClient(timeout=25.0, follow_redirects=True) as client:
        for wait in (0, 2.0, 4.0, 6.0):
            if wait:
                await asyncio.sleep(wait)
            r = await client.get(f"{S2_BASE}/paper/{s2_id}",
                                 params={"fields": "paperId,title,year,venue,externalIds,citationCount"})
            if r.status_code == 200:
                break
        else:
            raise GraphError("Semantic Scholar 限流中，请几秒后再试")
        node = _s2_node(r.json())

        async def _fetch(kind: str) -> list[dict]:
            params = {"fields": "paperId,title,year,venue,externalIds,citationCount",
                      "limit": LIMIT_EACH}
            for wait in (0, 2.0, 4.0, 6.0):
                if wait:
                    await asyncio.sleep(wait)
                rr = await client.get(f"{S2_BASE}/paper/{s2_id}/{kind}", params=params)
                if rr.status_code == 200:
                    break
            else:
                raise GraphError("Semantic Scholar 限流中，请几秒后重新点击该节点")
            if rr.status_code != 200:
                raise GraphError(f"引用数据获取失败（HTTP {rr.status_code}）")
            key = "citedPaper" if kind == "references" else "citingPaper"
            out = []
            for item in rr.json().get("data") or []:
                n = _s2_node(item.get(key) or {})
                if n["s2_id"] and n["title"]:
                    out.append(n)
            return out

        refs, cites = await asyncio.gather(_fetch("references"), _fetch("citations"))
        return {"node": node, "references": _closest(refs), "citations": _closest(cites)}


async def get_neighbors(node_id: str) -> dict:
    """拉取指定节点的相关论文（引用/被引各 5 篇），带进程内缓存。

    节点 id 按形态路由：W+纯数字 → OpenAlex，其余 → Semantic Scholar。
    """
    if node_id in _CACHE:
        return _CACHE[node_id]
    if re.fullmatch(r"W\d+", node_id):
        result = await _oa_neighbors(node_id)
    else:
        result = await _s2_neighbors(node_id)
    _CACHE[node_id] = result
    if len(_CACHE) > 200:
        _CACHE.clear()
    return result
