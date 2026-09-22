"""应用配置：从 .env 加载，提供全局 settings 对象。"""
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 打包成 exe 后：只读资源（模板/静态文件）在 _MEIPASS 临时目录，
# 可写数据（数据库/uploads/outputs/配置）放 exe 旁边；开发态两者都是项目根。
if getattr(sys, "frozen", False):
    APP_DIR = Path(sys._MEIPASS)                       # 只读资源
    BASE_DIR = Path(sys.executable).resolve().parent   # 可写数据
else:
    APP_DIR = BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # 大模型（OpenAI 兼容）
    llm_api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    llm_base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", ""))
    llm_model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", ""))

    # 翻译服务：openai（OpenAI 兼容，需 Key）或 siliconflowfree（内置免费服务，试用用）
    translate_service: str = field(default_factory=lambda: os.getenv("TRANSLATE_SERVICE", "openai"))

    # 翻译参数
    lang_in: str = field(default_factory=lambda: os.getenv("TRANSLATE_LANG_IN", "en"))
    lang_out: str = field(default_factory=lambda: os.getenv("TRANSLATE_LANG_OUT", "zh"))
    enable_dual: bool = field(default_factory=lambda: _bool(os.getenv("ENABLE_DUAL"), True))
    qps: int = field(default_factory=lambda: int(os.getenv("TRANSLATE_QPS", "4")))

    # 服务
    host: str = field(default_factory=lambda: os.getenv("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("PORT", "8000")))

    @property
    def llm_configured(self) -> bool:
        return bool(
            self.llm_api_key
            and self.llm_base_url
            and self.llm_model
            and "your-api-key" not in self.llm_api_key.lower()
        )


settings = Settings()

UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"
DB_PATH = BASE_DIR / "autotranslate.db"

for d in (UPLOAD_DIR, OUTPUT_DIR):
    d.mkdir(parents=True, exist_ok=True)
