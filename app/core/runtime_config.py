"""运行时可变配置：Web 界面保存到 model_config.json，未保存时回退 .env。

翻译服务、模型、Key、QPS、目标语言等都从这里读，
使界面修改即时生效（新任务使用新配置，无需重启）。
"""
import json
import os
import threading
from pathlib import Path

from app.config import BASE_DIR, settings

CONFIG_PATH = BASE_DIR / "model_config.json"
_LOCK = threading.Lock()

_FIELDS = ("service", "base_url", "api_key", "model", "qps",
           "lang_in", "lang_out", "enable_dual", "access_password")


def _defaults() -> dict:
    return {
        "service": settings.translate_service,   # openai / siliconflowfree
        "base_url": settings.llm_base_url,
        "api_key": settings.llm_api_key,
        "model": settings.llm_model,
        "qps": settings.qps,
        "lang_in": settings.lang_in,
        "lang_out": settings.lang_out,
        "enable_dual": settings.enable_dual,
        "access_password": os.getenv("ACCESS_PASSWORD", ""),
    }


def load() -> dict:
    cfg = _defaults()
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for k in _FIELDS:
                if saved.get(k) not in (None, ""):
                    cfg[k] = saved[k]
        except (ValueError, OSError):
            pass
    return cfg


def save(**fields) -> dict:
    """合并保存（只更新传入的字段），返回合并后的完整配置。"""
    with _LOCK:
        cfg = load()
        for k in _FIELDS:
            if fields.get(k) is not None:
                cfg[k] = fields[k]
        CONFIG_PATH.write_text(
            json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return cfg


def is_custom_ready(cfg: dict) -> bool:
    """自定义大模型（openai 服务）三要素是否齐全。"""
    return bool(
        cfg.get("base_url") and cfg.get("api_key") and cfg.get("model")
        and "your-api-key" not in str(cfg.get("api_key")).lower()
    )
