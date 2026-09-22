"""任务历史持久化（SQLite + aiosqlite）。"""
import aiosqlite

from app.config import DB_PATH

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    created_at  TEXT NOT NULL,
    source      TEXT NOT NULL,
    title       TEXT NOT NULL,
    lang_out    TEXT,
    dual        INTEGER NOT NULL DEFAULT 1,
    status      TEXT NOT NULL,
    stage       TEXT DEFAULT '',
    progress    REAL,
    error       TEXT,
    mono_path   TEXT,
    dual_path   TEXT,
    log_path    TEXT,
    finished_at TEXT
);
"""

_COLUMNS = ["id", "created_at", "source", "title", "lang_out", "dual", "status",
            "stage", "progress", "error", "mono_path", "dual_path", "log_path",
            "finished_at"]


def _to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["dual"] = bool(d["dual"])
    return d


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(_SCHEMA)
        await db.commit()


async def insert_task(**fields) -> None:
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute(f"INSERT INTO tasks ({cols}) VALUES ({marks})", tuple(fields.values()))
        await db.commit()


async def update_task(task_id: str, **fields) -> None:
    sets = ", ".join(f"{k} = ?" for k in fields)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE tasks SET {sets} WHERE id = ?", (*fields.values(), task_id))
        await db.commit()


async def get_task(task_id: str) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM tasks WHERE id = ?", (task_id,))
        row = await cur.fetchone()
        return _to_dict(row) if row else None


async def list_tasks(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            f"SELECT {', '.join(_COLUMNS)} FROM tasks ORDER BY created_at DESC LIMIT ?",
            (limit,))
        rows = await cur.fetchall()
        return [_to_dict(r) for r in rows]


async def delete_task(task_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        await db.commit()


async def pending_task_ids() -> list[str]:
    """启动时调用：找出所有非终态任务（服务重启后被中断）。"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id FROM tasks WHERE status IN ('queued', 'downloading', 'translating')")
        return [r["id"] for r in await cur.fetchall()]
