# -*- coding: utf-8 -*-
"""arXiv 检索：恢复单次 all: 查询（arXiv 限流 1 次/3 秒，避免连发超时）。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "core" / "search" / "arxiv.py"
s = p.read_text(encoding="utf-8")

# 双查询改回单查询
old = '''    # 1) 标题短语匹配（完整论文标题时召回最准）
    quoted = query.replace('"', "").strip()
    title_papers = await _arxiv_fetch(f'ti:"{quoted}"', limit, timeout) or []

    # 2) 全文检索补充
    all_papers = await _arxiv_fetch(f"all:{query}", limit, timeout) or []

    # 合并去重，标题精确/前缀命中置顶
    seen, merged = set(), []
    key_lower = _norm_title(query)
    exact = [p for p in title_papers if _norm_title(p.title).startswith(key_lower)]
    for p in exact + title_papers + all_papers:
        k = _norm_title(p.title)
        if k and k not in seen:
            seen.add(k)
            merged.append(p)
    return merged[:limit]'''
new = '''    # arXiv 限流 1 次/3 秒：仅发一次 all: 查询（标题精确置顶交给聚合层）
    papers = await _arxiv_fetch(f"all:{query}", limit, timeout) or []
    return papers[:limit]'''
assert old in s
s = s.replace(old, new, 1)
p.write_text(s, encoding="utf-8")
print("arxiv.py OK")
