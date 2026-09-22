"""AI 论文概括：提取 PDF 文本 → LLM 生成中文概括、流程思维导图与关键词。"""
import asyncio
import json
import logging
import re
from pathlib import Path

import fitz

from .llm import LLMError, chat

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 90_000  # 约 3 万 token，超出截断（保留开头：摘要+引言+方法通常在前部）

_SUMMARY_SYSTEM = (
    "你是学术论文分析助手。你的回复必须是严格的 JSON 对象，"
    "不要使用 markdown 代码块包裹，不要输出 JSON 以外的任何文字。"
)

_SUMMARY_PROMPT = """请分析以下论文全文，返回一个 JSON 对象，字段要求：

{{
  "summary": "中文概括，markdown 格式。包含四节：**研究问题**、**方法**、**实验结果**、**结论与贡献**。总长 300-500 字，忠实于原文，不要编造。",
  "mindmap": "论文结构与流程的思维导图，markdown 格式：第一行为 '# 论文主题'（10字内），之后用 '## 一级节点' 与 '- 子节点' 组织成 背景/方法流程/实验/结论 的树状结构。每个节点不超过 14 个字，总共 15-30 个节点。",
  "keywords": [{{"zh": "中文术语", "en": "English Term"}}]
}}

keywords 是 8-10 个论文核心术语（专业名词、模型名、数据集等）。

论文标题：{title}

论文全文：
{text}"""

_EXPLAIN_PROMPT = """请解释论文中的这段内容：「{keyword}」

它出自论文《{title}》。论文相关背景：
{context}

它可能是一个术语、短语，也可能是完整句子。返回 JSON 对象：
{{
  "explanation": "中文解释，markdown 格式，150-400 字。若是术语：说明定义、在论文中的作用、与其他概念的关系；若是句子：解释其含义与在论文中的意义。有专业公式或符号时用通俗语言说明。",
  "related": ["相关术语1", "相关术语2", "相关术语3"]
}}

回复必须是严格 JSON，不要 markdown 代码块，不要额外文字。"""


def extract_text(pdf_path: Path, max_chars: int = MAX_TEXT_CHARS) -> str:
    """提取 PDF 文本，超长截断；无文本层（扫描件）返回空串。"""
    doc = fitz.open(pdf_path)
    try:
        parts = [page.get_text("text") for page in doc]
    finally:
        doc.close()
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parts)).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n[注：论文过长，已截断]"
    return text


def _parse_json(raw: str) -> dict:
    """解析 LLM 输出的 JSON，容忍代码块包裹与前后杂文字。"""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 容错：截取首个大括号到末个大括号之间再试
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise LLMError("大模型未返回有效结果，请重试")


async def summarize_paper(pdf_path: Path, title: str = "") -> dict:
    """生成论文概括。返回 {summary, mindmap, keywords}，keywords 为字符串列表。"""
    text = await asyncio.to_thread(extract_text, pdf_path)
    if len(text) < 200:
        raise LLMError("PDF 没有可提取的文本（扫描件不支持概括）")

    messages = [
        {"role": "system", "content": _SUMMARY_SYSTEM},
        {"role": "user", "content": _SUMMARY_PROMPT.format(title=title or "未知", text=text)},
    ]
    last_err: Exception | None = None
    for attempt in range(2):  # 推理模型偶发输出不规范，自动重试一次
        raw = await chat(messages, temperature=0.2, max_tokens=4000)
        try:
            data = _parse_json(raw)
            break
        except LLMError as exc:
            last_err = exc
    else:
        raise last_err or LLMError("大模型未返回有效结果，请重试")

    summary = (data.get("summary") or "").strip()
    mindmap = (data.get("mindmap") or "").strip()
    if not summary:
        raise LLMError("大模型未返回概括内容，请重试")

    keywords: list[str] = []
    for kw in data.get("keywords") or []:
        if isinstance(kw, dict):
            zh, en = str(kw.get("zh", "")).strip(), str(kw.get("en", "")).strip()
            label = f"{zh}（{en}）" if zh and en else (zh or en)
        else:
            label = str(kw).strip()
        if label and label not in keywords:
            keywords.append(label)

    return {"summary": summary, "mindmap": mindmap, "keywords": keywords}


async def explain_keyword(keyword: str, *, title: str = "", context: str = "") -> dict:
    """解释术语或选中的文本片段，返回 {explanation, related}。context 可为概括文本或摘要片段。"""
    keyword = keyword.strip()
    if not keyword or len(keyword) > 300:
        raise LLMError("请选中有效的文本（300 字以内）")
    context = (context or "（无额外背景）")[:4000]

    raw = await chat(
        [
            {"role": "system", "content": "你是学术论文术语解释助手。回复必须是严格 JSON，不要代码块。" },
            {"role": "user", "content": _EXPLAIN_PROMPT.format(
                keyword=keyword, title=title or "未知", context=context)},
        ],
        temperature=0.2,
        max_tokens=1500,
    )
    data = _parse_json(raw)
    explanation = (data.get("explanation") or "").strip()
    if not explanation:
        raise LLMError("大模型未返回解释内容，请重试")
    related = [str(r).strip() for r in (data.get("related") or []) if str(r).strip()][:6]
    return {"explanation": explanation, "related": related}
