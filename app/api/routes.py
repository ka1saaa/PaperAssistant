"""REST API：搜索、任务创建/进度/下载/取消/删除/历史、AI 概括与术语解释、模型设置。"""
import json
import logging

import httpx
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.config import UPLOAD_DIR
from app.core import summarizer
from app.core.llm import LLMError, chat_with
from app.core.runtime_config import is_custom_ready, load as load_cfg, save as save_cfg
from app.core.search import search_papers
from app.tasks.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


def _mask(key: str) -> str:
    if not key:
        return ""
    return key[:5] + "***" + key[-4:] if len(key) > 12 else "***"


def _ensure_llm() -> None:
    cfg = load_cfg()
    if cfg["service"] == "openai" and not is_custom_ready(cfg):
        raise HTTPException(
            status_code=400,
            detail="尚未配置大模型：点击左侧底部模型状态栏打开「模型设置」，"
                   "或在 .env 中配置（参考 .env.example）",
        )


# ---- 服务信息 ----

@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.get("/config")
async def config() -> dict:
    cfg = load_cfg()
    return {
        "service": cfg["service"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
        "api_key_masked": _mask(cfg["api_key"]),
        "has_api_key": bool(cfg["api_key"]),
        "llm_configured": cfg["service"] == "siliconflowfree" or is_custom_ready(cfg),
        "qps": cfg["qps"],
        "lang_in": cfg["lang_in"],
        "lang_out": cfg["lang_out"],
        "enable_dual": cfg["enable_dual"],
    }


# ---- 模型设置 ----

class ConfigBody(BaseModel):
    service: str | None = None
    base_url: str | None = None
    api_key: str | None = None       # 空串/None 表示保留原值
    model: str | None = None
    qps: int | None = None
    lang_in: str | None = None
    lang_out: str | None = None
    enable_dual: bool | None = None


@router.post("/config")
async def save_config(body: ConfigBody) -> dict:
    """保存模型设置（合并式，api_key 留空保留原值）。"""
    if body.service is not None and body.service not in ("openai", "siliconflowfree"):
        raise HTTPException(status_code=400, detail="服务类型仅支持 openai / siliconflowfree")
    fields = body.model_dump()
    if fields.get("api_key") == "":
        fields.pop("api_key")
    cfg = save_cfg(**fields)
    if cfg["service"] == "openai" and not is_custom_ready(cfg):
        return {"saved": True, "ready": False,
                "detail": "已保存，但自定义模型三要素（API 地址 / Key / 模型）尚不完整"}
    return {"saved": True, "ready": True}


@router.post("/config/test")
async def test_config(body: ConfigBody) -> dict:
    """测试连接：优先用传入值（未填的回退当前配置），发起一次最小对话。"""
    cfg = load_cfg()
    if body.service == "siliconflowfree":
        return {"ok": True, "detail": "免费试用服务无需测试"}
    base = body.base_url or cfg["base_url"]
    key = body.api_key or cfg["api_key"]
    model = body.model or cfg["model"]
    if not (base and key and model):
        return {"ok": False, "detail": "请先填写 API 地址、Key 和模型名"}
    try:
        reply = await chat_with(base, key, model,
                                [{"role": "user", "content": "回复：OK"}],
                                temperature=0, timeout=30)
        return {"ok": True, "detail": f"连接成功（{model}）"}
    except LLMError as exc:
        return {"ok": False, "detail": str(exc)}


@router.post("/models")
async def list_models(body: ConfigBody) -> dict:
    """从服务商拉取可用模型列表（OpenAI 兼容 /models 接口）。"""
    cfg = load_cfg()
    base = body.base_url or cfg["base_url"]
    key = body.api_key or cfg["api_key"]
    if not (base and key):
        return {"models": [], "detail": "请先填写 API 地址与 Key"}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(base.rstrip("/") + "/models",
                                    headers={"Authorization": f"Bearer {key}"})
        if resp.status_code != 200:
            return {"models": [], "detail": f"获取失败（HTTP {resp.status_code}），可手动输入模型名"}
        ids = sorted(m.get("id", "") for m in resp.json().get("data", []) if m.get("id"))
        return {"models": ids[:200], "detail": ""}
    except (httpx.HTTPError, ValueError):
        return {"models": [], "detail": "获取失败，可手动输入模型名"}


# ---- 论文搜索 ----

@router.get("/search")
async def search(q: str, limit: int = 10) -> dict:
    q = q.strip()
    if not q:
        raise HTTPException(status_code=400, detail="搜索词不能为空")
    limit = max(5, min(20, limit))
    results = await search_papers(q, limit)
    return {"results": [p.model_dump() for p in results]}


# ---- 任务创建 ----

class InputBody(BaseModel):
    input: str
    dual: bool | None = None


class PaperBody(BaseModel):
    paper: dict
    dual: bool | None = None


@router.post("/tasks/upload")
async def create_upload_task(file: UploadFile = File(...), dual: bool | None = Form(None)) -> dict:
    _ensure_llm()
    data = await file.read()
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件超过 100MB 限制")
    try:
        task = await manager.create_upload(file.filename or "paper.pdf", data, dual)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return task.to_api()


@router.post("/tasks/input")
async def create_input_task(body: InputBody) -> dict:
    _ensure_llm()
    try:
        task = await manager.create_from_url(body.input, body.dual)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return task.to_api()


@router.post("/tasks/paper")
async def create_paper_task(body: PaperBody) -> dict:
    _ensure_llm()
    try:
        task = await manager.create_from_paper(body.paper, body.dual)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return task.to_api()


# ---- 任务查询 / 控制 ----

@router.get("/tasks")
async def list_tasks(limit: int = 50) -> dict:
    return {"tasks": [t.to_api() for t in manager.history(limit)]}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str) -> dict:
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task.to_api()


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict:
    ok = await manager.cancel(task_id)
    if not ok:
        raise HTTPException(status_code=400, detail="任务已结束或不存在，无法取消")
    return {"ok": True}


# ---- AI 概括与术语解释 ----

class KeywordBody(BaseModel):
    keyword: str
    task_id: str | None = None
    title: str = ""
    context: str = ""


@router.post("/tasks/{task_id}/summarize")
async def summarize_task(task_id: str) -> dict:
    """AI 概括任务原文：文字概括 + 流程思维导图 + 关键词。结果落盘缓存。"""
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    pdf = task.source_pdf()
    if not pdf:
        raise HTTPException(status_code=404, detail="找不到原文 PDF，无法概括")

    try:
        summary = await summarizer.summarize_paper(pdf, task.title)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    sp = task.summary_path()
    sp.parent.mkdir(parents=True, exist_ok=True)
    sp.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    return summary


@router.get("/tasks/{task_id}/summary")
async def get_summary(task_id: str) -> dict:
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    sp = task.summary_path()
    if not sp.exists():
        raise HTTPException(status_code=404, detail="尚未生成概括")
    return json.loads(sp.read_text(encoding="utf-8"))


@router.post("/explain")
async def explain_keyword(body: KeywordBody) -> dict:
    """解释术语。带 task_id 时用该论文的概括作上下文，解释更贴合论文。"""
    context = body.context
    title = body.title
    if body.task_id:
        task = manager.get(body.task_id)
        if task:
            sp = task.summary_path()
            if sp.exists():
                try:
                    data = json.loads(sp.read_text(encoding="utf-8"))
                    context = context or str(data.get("summary", ""))
                    title = title or task.title
                except (OSError, ValueError):
                    pass
    try:
        return await summarizer.explain_keyword(
            body.keyword, title=title, context=context)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/tasks/{task_id}")
async def delete_task(task_id: str) -> dict:
    try:
        await manager.delete(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True}


# ---- 批注 ----

class AnnotBody(BaseModel):
    page: int
    quote: str
    note: str
    kind: str = "source"          # 批注所在的文档：source / mono / dual


def _annot_path(task_id: str):
    from app.config import OUTPUT_DIR
    return OUTPUT_DIR / task_id / "annotations.json"


def _read_annots(task_id: str) -> list[dict]:
    p = _annot_path(task_id)
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []


def _write_annots(task_id: str, annots: list[dict]) -> None:
    p = _annot_path(task_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(annots, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("/tasks/{task_id}/page/{kind}/{page_no}")
async def task_page_png(task_id: str, kind: str, page_no: int, zoom: float = 1.0) -> Response:
    """把 PDF 单页渲染成 PNG（服务端 PyMuPDF，任何浏览器都能可靠显示）。"""
    from app.config import OUTPUT_DIR
    import fitz

    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if kind not in ("source", "mono", "dual"):
        raise HTTPException(status_code=400, detail="文档类型无效")
    folder = {"source": UPLOAD_DIR, "mono": OUTPUT_DIR, "dual": OUTPUT_DIR}[kind]
    if kind == "source":
        path = task.source_pdf()
    else:
        path = (OUTPUT_DIR / task_id).glob(f"*.{'mono' if kind == 'mono' else 'dual'}.pdf")
        path = next(iter(path), None)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail=f"{kind} 文档不存在")

    page_no = max(1, page_no)
    zoom = min(max(zoom, 0.5), 4.0)
    try:
        doc = fitz.open(path)
        if page_no > len(doc):
            raise HTTPException(status_code=404, detail="页码超出范围")
        pix = doc[page_no - 1].get_pixmap(matrix=fitz.Matrix(1.6 * zoom, 1.6 * zoom))
        png = pix.tobytes("png")
        doc.close()
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"页面渲染失败：{exc}")
    return Response(content=png, media_type="image/png")


@router.get("/tasks/{task_id}/annotations")
async def list_annotations(task_id: str) -> dict:
    if not manager.get(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"annotations": _read_annots(task_id)}


@router.post("/tasks/{task_id}/annotations")
async def add_annotation(task_id: str, body: AnnotBody) -> dict:
    import uuid as _uuid
    from datetime import datetime, timezone

    if not manager.get(task_id):
        raise HTTPException(status_code=404, detail="任务不存在")
    if not body.quote.strip():
        raise HTTPException(status_code=400, detail="批注引用不能为空")
    if body.kind not in ("source", "mono", "dual") or body.page < 1:
        raise HTTPException(status_code=400, detail="批注位置无效")

    annot = {
        "id": _uuid.uuid4().hex[:10],
        "kind": body.kind,
        "page": body.page,
        "quote": body.quote.strip()[:500],
        "note": body.note.strip()[:2000],
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    annots = _read_annots(task_id)
    annots.append(annot)
    _write_annots(task_id, annots)
    return annot


@router.delete("/tasks/{task_id}/annotations/{annot_id}")
async def delete_annotation(task_id: str, annot_id: str) -> dict:
    annots = _read_annots(task_id)
    remain = [a for a in annots if a["id"] != annot_id]
    if len(remain) == len(annots):
        raise HTTPException(status_code=404, detail="批注不存在")
    _write_annots(task_id, remain)
    return {"ok": True}


@router.delete("/tasks")
async def clear_tasks() -> dict:
    """清空全部历史记录（进行中的任务除外）。"""
    deleted = await manager.clear_history()
    return {"deleted": deleted}


@router.get("/tasks/{task_id}/file/{kind}")
async def task_file(task_id: str, kind: str) -> FileResponse:
    task = manager.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    path = {"mono": task.mono_path, "dual": task.dual_path,
            "source": task.source_pdf()}.get(kind)
    if not path or not path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或任务未完成")
    return FileResponse(path, filename=manager.download_name(task, kind))
