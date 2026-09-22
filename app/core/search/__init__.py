"""论文搜索统一入口：并发查询多个数据源，合并去重，带简单缓存。

中文关键词处理：arXiv 元数据为纯英文，中文直接匹配只会得到垃圾结果，
因此检测到 CJK 时先用已配置的大模型把关键词译成英文再搜（未配置模型
则跳过 arXiv，仅靠 Semantic Scholar）。
"""
import asyncio
import re
import time

from .arxiv import search_arxiv
from .models import Paper
from .semantic import search_semantic

from app.core.llm import chat

_CACHE: dict[str, tuple[float, list[Paper]]] = {}
CACHE_TTL = 300.0  # 秒
CACHE_MAX = 100


def _norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


def _has_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


async def _translate_query(query: str) -> str | None:
    """用已配置的大模型把中文关键词译成英文检索词；不可用时返回 None。"""
    from app.core.llm import LLMError

    try:
        text = await chat(
            [
                {"role": "system", "content":
                    "把用户的学术论文检索请求翻译成简洁的英文检索关键词。"
                    "只回复英文关键词本身，不要引号、不要解释。"},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=100,
            timeout=15,
        )
    except LLMError:
        return None
    if not text or not text.strip():
        return None
    text = text.splitlines()[0].strip().strip('"“”').strip()
    # 结果仍是中文（模型没执行翻译）则视为失败
    return text if text and not _has_cjk(text) and len(text) <= 200 else None


def _merge(primary: Paper, other: Paper) -> Paper:
    """用 other 补全 primary 的缺失字段。"""
    if not primary.abstract and other.abstract:
        primary.abstract = other.abstract
    if not primary.year and other.year:
        primary.year = other.year
    if not primary.venue and other.venue:
        primary.venue = other.venue
    if not primary.pdf_url and other.pdf_url:
        primary.pdf_url = other.pdf_url
    if not primary.authors and other.authors:
        primary.authors = other.authors
    if not primary.arxiv_id and other.arxiv_id:
        primary.arxiv_id = other.arxiv_id
    return primary


async def _do_search(query: str, limit: int, *, cjk: bool) -> list[Paper]:
    """对（可能是译后的）检索词执行双源检索并合并。"""
    if cjk:
        # 纯中文检索词对 arXiv 无意义，只查 S2，失败重试一次
        semantic = await search_semantic(query, limit)
        if semantic is None:
            await asyncio.sleep(1.5)
            semantic = await search_semantic(query, limit)
        return list(semantic or [])

    results = await asyncio.gather(
        search_arxiv(query, limit),
        search_semantic(query, limit),
        return_exceptions=True,
    )
    arxiv_papers = results[0] if isinstance(results[0], list) else []
    semantic_papers = results[1] if isinstance(results[1], list) else []

    # S2 被限流且 arXiv 无结果时，稍候重试一次 S2
    if results[1] is None and not arxiv_papers:
        await asyncio.sleep(1.5)
        semantic_papers = await search_semantic(query, limit) or []

    by_title: dict[str, Paper] = {_norm_title(p.title): p for p in arxiv_papers}
    merged: list[Paper] = list(arxiv_papers)
    for sp in semantic_papers:
        key = _norm_title(sp.title)
        if key in by_title:
            _merge(by_title[key], sp)
        else:
            by_title[key] = sp
            merged.append(sp)
    return merged


async def search_papers(query: str, limit: int = 10) -> list[Paper]:
    """关键词检索：中文先译成英文；arXiv + Semantic Scholar 并发，标题去重合并。"""
    query = query.strip()
    if not query:
        return []

    cache_key = f"{limit}:{query.lower()}"
    now = time.monotonic()
    if cache_key in _CACHE and now - _CACHE[cache_key][0] < CACHE_TTL:
        return _CACHE[cache_key][1]

    effective_query = query
    if _has_cjk(query):
        effective_query = await _translate_query(query) or query

    merged = await _do_search(effective_query, limit, cjk=_has_cjk(effective_query))
    merged.sort(key=lambda p: p.download_url is None)

    # 只缓存非空结果，避免限流/网络抖动导致的空结果被钉住
    if merged:
        if len(_CACHE) > CACHE_MAX:
            _CACHE.clear()
        _CACHE[cache_key] = (now, merged)
    return merged
