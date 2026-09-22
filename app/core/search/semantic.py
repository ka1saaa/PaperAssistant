"""Semantic Scholar API 检索源（免费，有限流）。

接口文档: https://api.semanticscholar.org/api-docs/graph
未认证限流约 1 次/秒，超限返回 429，此实现将其视为"该源无结果"处理。
"""
import httpx

from .models import Paper

API_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
FIELDS = "title,abstract,year,authors,venue,externalIds,openAccessPdf"


async def search_semantic(query: str, limit: int = 10, timeout: float = 15.0) -> list[Paper] | None:
    """按关键词检索 Semantic Scholar。

    返回 None 表示该源失败/被限流（区别于"确实没有结果"的空列表）。
    """
    params = {"query": query, "limit": limit, "fields": FIELDS}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(API_URL, params=params)
            if resp.status_code == 429:
                return None
            resp.raise_for_status()
    except httpx.HTTPError:
        return None

    data = resp.json()
    papers: list[Paper] = []
    for item in data.get("data") or []:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        ext = item.get("externalIds") or {}
        oa = item.get("openAccessPdf") or {}
        papers.append(
            Paper(
                source="semantic",
                id=item.get("paperId") or title,
                title=title,
                authors=[a.get("name", "") for a in item.get("authors") or [] if a.get("name")],
                year=item.get("year"),
                abstract=item.get("abstract") or "",
                venue=item.get("venue") or "",
                pdf_url=oa.get("url"),
                arxiv_id=ext.get("ArXiv"),
            )
        )
    return papers
