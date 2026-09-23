"""任务管理器：创建/执行/取消翻译任务，维护内存状态并落库。"""
import asyncio
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.config import OUTPUT_DIR, UPLOAD_DIR
from app.core import pdf2zh_runner
from app.core.glossary import load_entries as load_glossary, write_csv as write_glossary_csv
from app.core.runtime_config import load as load_cfg
from app.core.search import downloader
from app.storage import db

logger = logging.getLogger(__name__)

TRANSLATE_CONCURRENCY = 2  # 同时翻译的任务数上限
MAX_CONCURRENT_DOWNLOADS = 4

_TERMINAL = {"done", "failed", "canceled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _safe_stem(title: str) -> str:
    stem = re.sub(r'[\\/:*?"<>|\s]+', "_", title).strip("_")
    return (stem or "paper")[:80]


@dataclass
class Task:
    id: str
    source: str                 # upload / search / input
    title: str
    lang_out: str
    dual: bool
    status: str = "queued"      # queued/downloading/translating/done/failed/canceled
    stage: str = ""
    progress: float | None = None
    error: str | None = None
    pdf_url: str | None = None  # 需要先下载的来源
    pdf_path: Path | None = None
    mono_path: Path | None = None
    dual_path: Path | None = None
    log_path: Path | None = None
    created_at: str = field(default_factory=_now)
    finished_at: str | None = None

    def to_api(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "lang_out": self.lang_out,
            "dual": self.dual,
            "status": self.status,
            "stage": self.stage,
            "progress": self.progress,
            "error": self.error,
            "has_mono": self.mono_path is not None,
            "has_dual": self.dual_path is not None,
            "has_source": self.source_pdf() is not None,
            "has_summary": self.summary_path().exists(),
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }

    def source_pdf(self) -> Path | None:
        """原文路径（重启后恢复的任务无 pdf_path，按约定路径找）。"""
        for p in (self.pdf_path, UPLOAD_DIR / f"{self.id}.pdf"):
            if p and p.exists():
                return p
        return None

    def summary_path(self) -> Path:
        return OUTPUT_DIR / self.id / "summary.json"


class TaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._jobs: dict[str, asyncio.Task] = {}
        self._dl_sem = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        self._tr_sem = asyncio.Semaphore(TRANSLATE_CONCURRENCY)

    # ---- 生命周期 ----

    async def startup(self) -> None:
        await db.init_db()
        # 服务重启时，把中断的任务标记为失败
        for task_id in await db.pending_task_ids():
            await db.update_task(task_id, status="failed", error="服务重启，任务中断",
                                 finished_at=_now())
        for row in await db.list_tasks(limit=200):
            self._tasks[row["id"]] = self._task_from_row(row)
        logger.info("task manager started, %d history tasks", len(self._tasks))

    @staticmethod
    def _task_from_row(row: dict) -> Task:
        return Task(
            id=row["id"], source=row["source"], title=row["title"],
            lang_out=row["lang_out"] or "zh", dual=bool(row["dual"]),
            status=row["status"], stage=row["stage"] or "",
            progress=row["progress"], error=row["error"],
            mono_path=Path(row["mono_path"]) if row["mono_path"] else None,
            dual_path=Path(row["dual_path"]) if row["dual_path"] else None,
            log_path=Path(row["log_path"]) if row["log_path"] else None,
            created_at=row["created_at"], finished_at=row["finished_at"],
        )

    # ---- 创建 ----

    def _new_task(self, source: str, title: str, dual: bool | None) -> Task:
        cfg = load_cfg()
        task = Task(
            id=uuid.uuid4().hex[:12],
            source=source,
            title=title.strip() or "未命名论文",
            lang_out=cfg["lang_out"],
            dual=cfg["enable_dual"] if dual is None else dual,
        )
        self._tasks[task.id] = task
        return task

    async def create_upload(self, filename: str, data: bytes, dual: bool | None = None) -> Task:
        """本地上传的 PDF 直接进入翻译队列。"""
        if not data.startswith(b"%PDF"):
            raise ValueError("上传文件不是有效的 PDF")
        title = re.sub(r"\.pdf$", "", Path(filename).name, flags=re.IGNORECASE) or "未命名论文"
        task = self._new_task("upload", title, dual)
        task.pdf_path = UPLOAD_DIR / f"{task.id}.pdf"
        task.pdf_path.write_bytes(data)
        await db.insert_task(id=task.id, created_at=task.created_at, source=task.source,
                             title=task.title, lang_out=task.lang_out, dual=int(task.dual),
                             status=task.status)
        self._spawn(task)
        return task

    async def create_from_url(self, text: str, dual: bool | None = None) -> Task:
        """输入 arXiv ID 或 PDF 链接：解析 → 下载 → 翻译。"""
        pdf_url = downloader.resolve_pdf_url(text)
        if not pdf_url:
            raise ValueError("无法识别输入：请提供 arXiv ID（如 1706.03762）或 PDF 链接")
        title = pdf_url.rsplit("/", 1)[-1]
        if title.endswith(".pdf"):
            title = title[:-4]
        task = self._new_task("input", title, dual)
        task.pdf_url = pdf_url
        await db.insert_task(id=task.id, created_at=task.created_at, source=task.source,
                             title=task.title, lang_out=task.lang_out, dual=int(task.dual),
                             status=task.status)
        self._spawn(task)
        return task

    async def create_from_paper(self, paper: dict, dual: bool | None = None) -> Task:
        """从搜索结果/图谱节点创建任务（前端回传论文元数据）。

        没有现成 PDF 链接时，按标题搜索 arXiv 自动补全。
        """
        url = paper.get("download_url") or paper.get("pdf_url")
        title = (paper.get("title") or "").strip()
        if not url and title:
            from app.core.search.arxiv import search_arxiv
            hits = await search_arxiv(title, limit=1)
            if hits:
                url = hits[0].download_url
        if not url:
            raise ValueError("该论文没有可下载的 PDF（arXiv 按标题也未找到），无法入库")
        task = self._new_task("search", title or "未命名论文", dual)
        task.pdf_url = url
        await db.insert_task(id=task.id, created_at=task.created_at, source=task.source,
                             title=task.title, lang_out=task.lang_out, dual=int(task.dual),
                             status=task.status)
        self._spawn(task)
        return task

    def _spawn(self, task: Task) -> None:
        self._jobs[task.id] = asyncio.create_task(
            self._run(task), name=f"task-{task.id}")

    # ---- 执行 ----

    async def _run(self, task: Task) -> None:
        try:
            # 1) 下载（来源为搜索/输入时）
            if task.pdf_url and task.pdf_path is None:
                task.status, task.stage, task.progress = "downloading", "下载 PDF", None
                await db.update_task(task.id, status=task.status, stage=task.stage)
                async with self._dl_sem:
                    task.pdf_path = await downloader.download_pdf(
                        task.pdf_url, UPLOAD_DIR, filename=f"{task.id}.pdf")

            # 2) 翻译
            task.status, task.stage, task.progress = "translating", "准备翻译", 0.0
            await db.update_task(task.id, status=task.status, stage=task.stage, progress=0)

            async def on_progress(stage: str, percent: float | None) -> None:
                task.stage = stage
                task.progress = percent
                await db.update_task(task.id, stage=stage, progress=percent)

            cfg = load_cfg()
            # 用户术语表：有则生成 CSV 传给 pdf2zh
            glossary_csv = None
            if load_glossary():
                glossary_csv = OUTPUT_DIR / task.id / "glossary.csv"
                write_glossary_csv(glossary_csv)

            async with self._tr_sem:
                result = await pdf2zh_runner.translate_pdf(
                    task.pdf_path,
                    OUTPUT_DIR / task.id,
                    service=cfg["service"],
                    lang_in=cfg["lang_in"],
                    lang_out=task.lang_out,
                    dual=task.dual,
                    qps=cfg["qps"],
                    api_key=cfg["api_key"],
                    base_url=cfg["base_url"],
                    model=cfg["model"],
                    glossary_csv=glossary_csv,
                    on_progress=on_progress,
                )

            task.mono_path = result.mono_path
            task.dual_path = result.dual_path
            task.log_path = result.log_path
            task.status, task.stage, task.progress = "done", "完成", 100.0
            task.finished_at = _now()
            await db.update_task(
                task.id, status=task.status, stage=task.stage, progress=100.0,
                mono_path=str(result.mono_path or ""), dual_path=str(result.dual_path or ""),
                log_path=str(result.log_path or ""), finished_at=task.finished_at)
            logger.info("task %s done in %.1fs", task.id, result.duration)

        except asyncio.CancelledError:
            task.status, task.finished_at = "canceled", _now()
            await db.update_task(task.id, status=task.status, finished_at=task.finished_at)
        except Exception as exc:  # noqa: BLE001 — 任何失败都要落到任务状态上
            logger.exception("task %s failed", task.id)
            task.status, task.error, task.finished_at = "failed", str(exc), _now()
            await db.update_task(task.id, status=task.status, error=task.error,
                                 finished_at=task.finished_at)
        finally:
            self._jobs.pop(task.id, None)

    # ---- 查询 / 取消 / 删除 ----

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def history(self, limit: int = 50) -> list[Task]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return tasks[:limit]

    async def cancel(self, task_id: str) -> bool:
        job = self._jobs.get(task_id)
        task = self._tasks.get(task_id)
        if job and not job.done():
            job.cancel()
            return True
        if task and task.status in ("queued",):
            task.status, task.finished_at = "canceled", _now()
            await db.update_task(task.id, status=task.status, finished_at=task.finished_at)
            return True
        return False

    async def delete(self, task_id: str) -> None:
        """删除单条历史记录及其产物文件；进行中/排队中的任务须先取消。"""
        task = self._tasks.get(task_id)
        if not task:
            raise ValueError("任务不存在或已删除")
        if task.status in ("queued", "downloading", "translating"):
            raise ValueError("任务进行中，请先取消再删除")

        job = self._jobs.pop(task_id, None)
        if job and not job.done():
            job.cancel()

        # 原文与产物按确定性路径清理（从 DB 恢复的任务没有 pdf_path）
        pdf_file = task.pdf_path or (UPLOAD_DIR / f"{task.id}.pdf")
        pdf_file.unlink(missing_ok=True)
        out_dir = OUTPUT_DIR / task.id
        if out_dir.exists():
            shutil.rmtree(out_dir, ignore_errors=True)

        self._tasks.pop(task_id, None)
        await db.delete_task(task_id)
        logger.info("task %s deleted", task_id)

    async def clear_history(self) -> int:
        """清空全部历史（进行中的任务除外），返回删除条数。"""
        deletable = [t.id for t in self._tasks.values()
                     if t.status not in ("queued", "downloading", "translating")]
        for task_id in deletable:
            await self.delete(task_id)
        return len(deletable)

    # ---- 下载文件名 ----

    def download_name(self, task: Task, kind: str) -> str:
        stem = _safe_stem(task.title)
        if kind == "mono":
            return f"{stem}.{task.lang_out}.pdf"
        if kind == "dual":
            return f"{stem}.{task.lang_out}.双语对照.pdf"
        return f"{stem}.原文.pdf"


manager = TaskManager()
