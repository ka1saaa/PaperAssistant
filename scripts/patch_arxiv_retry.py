# -*- coding: utf-8 -*-
"""arXiv 检索：429/503 限流自动退避重试 + 短语引号包裹。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "core" / "search" / "arxiv.py"
s = p.read_text(encoding="utf-8")

old = '''async def _arxiv_fetch(search_query: str, limit: int, timeout: float) -> list[Paper] | None:
    """执行一次 arXiv 查询，返回论文列表；网络/解析失败返回 None。"""
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(API_URL, params=params)
            resp.raise_for_status()
        papers = []
        for entry in root.findall("atom:entry", NS):
            paper = _parse_entry(entry)
            if paper:
                papers.append(paper)
        return papers
    except (httpx.HTTPError, ET.ParseError):
        return None'''
new = '''async def _arxiv_fetch(search_query: str, limit: int, timeout: float) -> list[Paper] | None:
    """执行 arXiv 查询，限流（429/503）自动退避重试；最终失败返回 None。"""
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    }
    import asyncio as _asyncio

    for wait in (0, 3.5, 7.0):          # arXiv 要求 3 秒间隔，退避重试两轮
        if wait:
            await _asyncio.sleep(wait)
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
    return papers'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("arxiv 重试 OK")
