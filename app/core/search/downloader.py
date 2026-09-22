"""PDF 下载与输入类型识别。

支持三种输入：
1. arXiv ID（1706.03762 / arXiv:1706.03762v2）
2. 任意 http(s) PDF 链接
3. arXiv abs 页面链接（自动转成 PDF 链接）
"""
import re
from pathlib import Path

import httpx

from .arxiv import extract_arxiv_id

MAX_PDF_SIZE = 100 * 1024 * 1024  # 100MB

_ABS_URL_RE = re.compile(r"arxiv\.org/(?:abs|pdf)/([^\s?#]+)", re.IGNORECASE)


def resolve_pdf_url(text: str) -> str | None:
    """把用户输入解析为可下载的 PDF 直链；不是可识别的链接/ID 时返回 None。"""
    text = text.strip()
    if not text:
        return None

    # 纯 arXiv ID
    arxiv_id = extract_arxiv_id(text)
    if arxiv_id:
        return f"https://arxiv.org/pdf/{arxiv_id}"

    # URL
    if text.lower().startswith(("http://", "https://")):
        m = _ABS_URL_RE.search(text)
        if m:
            return f"https://arxiv.org/pdf/{m.group(1)}"
        return text

    return None


async def download_pdf(url: str, dest_dir: Path, filename: str | None = None,
                       timeout: float = 120.0) -> Path:
    """下载 PDF 到 dest_dir，返回本地路径。内容校验失败时抛出 ValueError。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        data = resp.content

    if len(data) > MAX_PDF_SIZE:
        raise ValueError(f"文件超过大小限制（{MAX_PDF_SIZE // 1024 // 1024}MB）")
    if not data.startswith(b"%PDF"):
        raise ValueError(f"下载内容不是有效的 PDF（content-type: {content_type}）")

    if not filename:
        name = url.rstrip("/").split("/")[-1] or "paper.pdf"
        if not name.lower().endswith(".pdf"):
            name += ".pdf"
        filename = re.sub(r'[\\/:*?"<>|]', "_", name)
    path = dest_dir / filename
    path.write_bytes(data)
    return path
