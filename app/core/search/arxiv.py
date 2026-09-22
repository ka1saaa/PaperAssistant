"""arXiv API 检索源（免费，无需 Key）。

接口文档: https://info.arxiv.org/help/api/user-manual.html
"""
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


async def search_arxiv(query: str, limit: int = 10, timeout: float = 15.0) -> list[Paper]:
    """按关键词检索 arXiv，返回归一化结果列表；失败时返回空列表。"""
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
    except httpx.HTTPError:
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        return []

    papers = []
    for entry in root.findall("atom:entry", NS):
        paper = _parse_entry(entry)
        if paper:
            papers.append(paper)
    return papers
