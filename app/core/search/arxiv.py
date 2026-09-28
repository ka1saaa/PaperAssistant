"""arXiv API 检索源（免费，无需 Key）。

接口文档: https://info.arxiv.org/help/api/user-manual.html
限流策略：arXiv 要求请求间隔 3 秒，429/503 自动退避重试。
"""
import asyncio
import re
import xml.etree.ElementTree as ET

import httpx

from .models import Paper

API_URL = "http://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom"}

_ARXIV_ID_RE = re.compile(
    r"^(?:(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?|([a-z-]+/\d{7})(v\d+)?)$", re.IGNORECASE
)


def is_arxiv_id(text: str) -> bool:
    """判断输入是否为 arXiv ID（如 1706.03762 或 arXiv:1706.03762v2）。"""
    return bool(_ARXIV_ID_RE.match(text.strip()))


def extract_arxiv_id(text: str) -> str | None:
    m = _ARXIV_ID_RE.match(text.strip())
    if not m:
        return None
    return (m.group(1) or m.group(3)) + (m.group(2) or "")


def _parse_entry(entry: ET.Element) -> Paper | None:
    def txt(path: str) -> str:
        el = entry.find(path, NS)
        return (el.text or "").strip() if el is not None and el.text else ""

    title = re.sub(r"\s+", " ", txt("atom:title"))
    if not title:
        return None

    abs_url = txt("atom:id")            # 形如 http://arxiv.org/abs/1706.03762v2
    arxiv_id = abs_url.rsplit("/abs/", 1)[-1].split("v")[0] if "/abs/" in abs_url else None

    authors = [
        (a.find("atom:name", NS).text or "").strip()
        for a in entry.findall("atom:author", NS)
        if a.find("atom:name", NS) is not None and a.find("atom:name", NS).text
    ]

    published = txt("atom:published")   # 形如 2017-06-12T17:57:34Z
    year = int(published[:4]) if published[:4].isdigit() else None

    return Paper(
        source="arxiv",
        id=abs_url or (arxiv_id or title),
        title=title,
        authors=authors,
        year=year,
        abstract=re.sub(r"\s+", " ", txt("atom:summary")),
        venue="arXiv",
        pdf_url=f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None,
        arxiv_id=arxiv_id,
    )


async def get_title_by_id(arxiv_id: str, timeout: float = 15.0) -> str | None:
    """按 arXiv ID 获取论文标题（用于直接输入 ID 时展示）。"""
    params = {"id_list": arxiv_id, "max_results": 1}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
        root = ET.fromstring(resp.text)
        entry = root.find("atom:entry", NS)
        if entry is None:
            return None
        title = entry.find("atom:title", NS)
        return re.sub(r"\s+", " ", title.text or "").strip() if title is not None else None
    except httpx.HTTPError:
        return None


async def _arxiv_fetch(search_query: str, limit: int, timeout: float) -> list[Paper] | None:
    """执行一次 arXiv 查询；429/503 退避重试；最终失败返回 None。"""
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    for wait in (0, 3.5, 7.0):          # arXiv 要求 3 秒间隔，退避重试两轮
        if wait:
            await asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(API_URL, params=params)
            if resp.status_code in (429, 503):
                continue
            resp.raise_for_status()
            break
        except httpx.HTTPError:
            if wait:
                return None
            continue
    else:
        return None
    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return None
    papers = []
    for entry in root.findall("atom:entry", NS):
        paper = _parse_entry(entry)
        if paper:
            papers.append(paper)
    return papers


def _norm_title(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (t or "").lower())


async def search_arxiv(query: str, limit: int = 10, timeout: float = 15.0) -> list[Paper]:
    """检索 arXiv：单次 all: 查询（限流由 _arxiv_fetch 内部退避处理）。"""
    query = query.strip()

    # arXiv 限流 1 次/3 秒：仅发一次 all: 查询（标题精确置顶交给聚合层）
    papers = await _arxiv_fetch(f"all:{query}", limit, timeout) or []
    return papers[:limit]
