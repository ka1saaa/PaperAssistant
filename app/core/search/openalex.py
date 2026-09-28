"""OpenAlex 检索源（免费无 Key，标题匹配精准，日限 10 万次）。"""
import logging
import re

import httpx

from .models import Paper

logger = logging.getLogger(__name__)

OA_BASE = "https://api.openalex.org"
MAILTO = "paperassistant@local"
SELECT = "id,display_name,publication_year,cited_by_count,doi,authorships,primary_location"


def _node(payload: dict) -> Paper | None:
    title = (payload.get("display_name") or "").strip()
    if not title:
        return None
    doi = payload.get("doi") or ""
    arxiv_id = None
    m = re.search(r"10\.48550/arxiv\.(.+)$", doi, re.IGNORECASE)
    if m:
        arxiv_id = m.group(1)
    loc = payload.get("primary_location") or {}
    src = loc.get("source") or {}
    pdf_url = loc.get("pdf_url")
    authors = [a.get("author", {}).get("display_name", "")
               for a in payload.get("authorships") or []][:6]
    return Paper(
        source="openalex",
        id=(payload.get("id") or "").rsplit("/", 1)[-1] or title,
        title=title,
        authors=[a for a in authors if a],
        year=payload.get("publication_year"),
        abstract="",
        venue=(src.get("display_name") or "").strip(),
        citation_count=payload.get("cited_by_count") or 0,
        pdf_url=pdf_url or (f"https://arxiv.org/pdf/{arxiv_id}" if arxiv_id else None),
        arxiv_id=arxiv_id,
    )


async def search_openalex(query: str, limit: int = 10, timeout: float = 20.0) -> list[Paper]:
    """按标题/关键词检索 OpenAlex；失败返回空列表。"""
    params = {
        "filter": f"title.search:{query}",
        "per_page": min(limit, 25),
        "select": SELECT,
        "mailto": MAILTO,
    }
    import asyncio as _asyncio

    for wait in (0, 1.2):           # 网络抖动重试一次
        if wait:
            await _asyncio.sleep(wait)
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(f"{OA_BASE}/works", params=params)
                resp.raise_for_status()
            break
        except httpx.HTTPError:
            continue
    else:
        return []
    out = []
    for item in resp.json().get("results") or []:
        p = _node(item)
        if p:
            out.append(p)
    return out
