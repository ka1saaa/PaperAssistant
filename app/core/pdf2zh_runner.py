"""pdf2zh_next 封装层：子进程运行翻译、进度解析、产物收集与错误分类。

产物命名规律（实测 v2.9.0）：
    <name>.<lang_out>.mono.pdf  纯译文
    <name>.<lang_out>.dual.pdf  双语对照
    <name>.<lang_out>.glossary.csv  自动提取的术语表
"""
import asyncio
import inspect
import logging
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3600.0

# 进度行示例: "Translate Paragraphs (1/1)  -----  12/31  0:00:05  0:00:08"
_STAGE_RE = re.compile(
    r"(?P<stage>[A-Za-z][A-Za-z /]+?)\s+\(\d+/\d+\)\s*[-–]+\s*(?P<done>\d+)/(?P<total>\d+)"
)

# 常见错误的归类提示（对日志原文做小写匹配）
_ERROR_HINTS: list[tuple[str, str]] = [
    ("401", "API Key 无效或未授权（HTTP 401）"),
    ("403", "API 拒绝访问（HTTP 403），请检查 Key 权限"),
    ("429", "请求过于频繁或额度受限（HTTP 429），请降低 QPS 后重试"),
    ("insufficient_quota", "API 账户额度不足"),
    ("invalid_api_key", "API Key 无效"),
    ("connection error", "无法连接翻译服务，请检查网络或 BASE_URL"),
    ("no text layer", "PDF 没有文本层（扫描件），暂不支持，请使用文字版 PDF"),
    ("scanned", "检测到扫描版 PDF，暂不支持"),
]


@dataclass
class TranslateResult:
    mono_path: Path | None = None
    dual_path: Path | None = None
    glossary_path: Path | None = None
    log_path: Path | None = None
    duration: float = 0.0


@dataclass
class _RunState:
    returncode: int | None = None
    log_lines: list[str] = field(default_factory=list)


def _classify_error(log_text: str) -> str:
    low = log_text.lower()
    for marker, hint in _ERROR_HINTS:
        if marker in low:
            return hint
    return "翻译失败，详见日志"


def _find_exe() -> str:
    """定位 pdf2zh_next 可执行文件（venv Scripts 目录或 PATH）。"""
    exe = shutil.which("pdf2zh_next")
    if exe:
        return exe
    cand = Path(sys.executable).parent / ("pdf2zh_next.exe" if sys.platform == "win32" else "pdf2zh_next")
    if cand.exists():
        return str(cand)
    return "pdf2zh_next"


def _build_cmd(pdf_path: Path, out_dir: Path, *, service: str, lang_in: str, lang_out: str,
               dual: bool, qps: int, api_key: str, base_url: str, model: str,
               pages: str | None = None, no_watermark: bool = True,
               glossary_csv: Path | None = None) -> list[str]:
    cmd = [
        _find_exe(),
        str(pdf_path),
        "--output", str(out_dir),
        "--lang-in", lang_in,
        "--lang-out", lang_out,
        "--watermark-output-mode", "no_watermark" if no_watermark else "watermarked",
        "--disable-config-auto-save",
    ]
    if glossary_csv:
        cmd += ["--glossaries", str(glossary_csv)]
    if service == "siliconflowfree":
        cmd.append("--siliconflowfree")
    else:
        cmd += ["--openai", "--openai-api-key", api_key, "--openai-base-url", base_url,
                "--openai-model", model]
    if qps > 0:
        cmd += ["--qps", str(qps)]
    if not dual:
        cmd.append("--no-dual")
    if pages:
        cmd += ["--pages", pages]
    return cmd


async def translate_pdf(
    pdf_path: Path,
    out_dir: Path,
    *,
    service: str = "openai",
    lang_in: str = "en",
    lang_out: str = "zh",
    dual: bool = True,
    qps: int = 4,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    pages: str | None = None,
    glossary_csv: Path | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    on_progress: Callable[[str, float | None], Awaitable[None]] | None = None,
) -> TranslateResult:
    """运行 pdf2zh_next 翻译单个 PDF。

    on_progress(stage, percent)：percent 为 None 表示该阶段无法量化。
    失败时抛出 RuntimeError（消息为归类后的中文提示）。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = _build_cmd(pdf_path, out_dir, service=service, lang_in=lang_in, lang_out=lang_out,
                     dual=dual, qps=qps, api_key=api_key, base_url=base_url, model=model,
                     pages=pages, glossary_csv=glossary_csv)
    logger.info("pdf2zh cmd: %s", " ".join(cmd[:2]) + " ...")

    state = _RunState()
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=str(out_dir),
    )

    async def _pump() -> None:
        assert proc.stdout is not None
        last_stage, last_percent = "", None
        while True:
            raw = await proc.stdout.readline()
            if not raw:
                break
            # rich 进度可能用 \r 刷新同一行
            for chunk in raw.decode("utf-8", errors="replace").replace("\r", "\n").split("\n"):
                line = chunk.strip()
                if not line:
                    continue
                state.log_lines.append(line)
                m = _STAGE_RE.search(line)
                if m:
                    stage = m.group("stage").strip()
                    percent = int(m.group("done")) / int(m.group("total")) * 100
                    if stage != last_stage or percent != last_percent:
                        last_stage, last_percent = stage, percent
                        if on_progress:
                            ret = on_progress(stage, percent)
                            if inspect.isawaitable(ret):
                                await ret
            if time.monotonic() - started > timeout:
                proc.kill()
                state.log_lines.append(f"[runner] 超时（{timeout:.0f}s），已终止")
                break

    try:
        await _pump()
        state.returncode = await proc.wait()
    except asyncio.CancelledError:
        proc.kill()
        await proc.wait()
        raise

    duration = time.monotonic() - started

    # 保存完整日志
    log_path = out_dir / "translate.log"
    log_path.write_text("\n".join(state.log_lines), encoding="utf-8")

    # 收集产物
    mono = next(iter(sorted(out_dir.glob("*.mono.pdf"))), None)
    dual_path = next(iter(sorted(out_dir.glob("*.dual.pdf"))), None)
    glossary = next(iter(sorted(out_dir.glob("*.glossary.csv"))), None)

    if state.returncode != 0 or mono is None:
        tail = "\n".join(state.log_lines[-30:])
        raise RuntimeError(_classify_error(tail) + f"\n（日志: {log_path}）")

    return TranslateResult(
        mono_path=mono,
        dual_path=dual_path,
        glossary_path=glossary,
        log_path=log_path,
        duration=duration,
    )
