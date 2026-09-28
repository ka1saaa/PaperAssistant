# -*- coding: utf-8 -*-
"""聚合层：接入 OpenAlex 三源并发 + 标题精确命中置顶。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "core" / "search" / "__init__.py"
s = p.read_text(encoding="utf-8")

old = "from .semantic import search_semantic"
assert old in s
s = s.replace(old, old + "\nfrom .openalex import search_openalex", 1)

old2 = '''    results = await asyncio.gather(
        search_arxiv(query, limit),
        search_semantic(query, limit),
        return_exceptions=True,
    )
    arxiv_papers = results[0] if isinstance(results[0], list) else []
    semantic_papers = results[1] if isinstance(results[1], list) else []

    # S2 被限流且 arXiv 无结果时，稍候重试一次 S2
    if results[1] is None and not arxiv_papers:
        await asyncio.sleep(1.5)
        semantic_papers = await search_semantic(query, limit) or []'''
new2 = '''    results = await asyncio.gather(
        search_arxiv(query, limit),
        search_semantic(query, limit),
        search_openalex(query, limit),
        return_exceptions=True,
    )
    arxiv_papers = results[0] if isinstance(results[0], list) else []
    semantic_papers = results[1] if isinstance(results[1], list) else []
    openalex_papers = results[2] if isinstance(results[2], list) else []

    # S2 被限流且其他源无结果时，稍候重试一次 S2
    if results[1] is None and not arxiv_papers and not openalex_papers:
        await asyncio.sleep(1.5)
        semantic_papers = await search_semantic(query, limit) or []'''
assert old2 in s, "gather 块未匹配"
s = s.replace(old2, new2, 1)

old3 = '''    by_title: dict[str, Paper] = {_norm_title(p.title): p for p in arxiv_papers}
    merged: list[Paper] = list(arxiv_papers)
    for sp in semantic_papers:
        key = _norm_title(sp.title)
        if key in by_title:
            _merge(by_title[key], sp)
        else:
            by_title[key] = sp
            merged.append(sp)
    return merged'''
new3 = '''    by_title: dict[str, Paper] = {_norm_title(p.title): p for p in arxiv_papers}
    merged: list[Paper] = list(arxiv_papers)
    for more in (semantic_papers, openalex_papers):
        for sp in more:
            key = _norm_title(sp.title)
            if key in by_title:
                _merge(by_title[key], sp)
            else:
                by_title[key] = sp
                merged.append(sp)

    # 标题精确/前缀命中置顶（完整标题搜索的关键），其余有 PDF 的靠前
    qkey = _norm_title(query)

    def _rank(p: Paper):
        exact = bool(qkey) and _norm_title(p.title).startswith(qkey)
        return (0 if exact else 1, p.download_url is None)

    merged.sort(key=_rank)
    return merged'''
assert old3 in s, "合并块未匹配"
s = s.replace(old3, new3, 1)
p.write_text(s, encoding="utf-8")
print("聚合层 OK")
