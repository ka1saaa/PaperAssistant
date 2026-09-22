"""术语表：存 glossary.json（用户界面维护），翻译时生成 pdf2zh 用的 CSV。"""
import csv
import json
import logging
from pathlib import Path

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

GLOSSARY_PATH = BASE_DIR / "glossary.json"


def load_entries() -> list[dict]:
    if not GLOSSARY_PATH.exists():
        return []
    try:
        data = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
        return [e for e in data if isinstance(e, dict) and e.get("src") and e.get("tgt")]
    except (ValueError, OSError):
        return []


def save_entries(entries: list[dict]) -> int:
    """清洗并保存术语条目，返回条数。"""
    clean: list[dict] = []
    seen: set[str] = set()
    for e in entries or []:
        src = str(e.get("src", "")).strip()
        tgt = str(e.get("tgt", "")).strip()
        if not src or not tgt or src.lower() in seen:
            continue
        if len(src) > 120 or len(tgt) > 120:
            continue
        seen.add(src.lower())
        clean.append({"src": src, "tgt": tgt})
    GLOSSARY_PATH.write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("glossary saved: %d entries", len(clean))
    return len(clean)


def write_csv(dest: Path) -> bool:
    """生成 pdf2zh --glossaries 需要的 CSV（列名必须为 source/target）；无术语返回 False。"""
    entries = load_entries()
    if not entries:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["source", "target"])
        w.writerows([(e["src"], e["tgt"]) for e in entries])
    return True
