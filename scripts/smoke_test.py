"""核心引擎冒烟测试：用真实论文 PDF 验证 pdf2zh 翻译链路。

用法:
    python scripts/smoke_test.py                # 无 LLM Key 时用内置免费服务
    python scripts/smoke_test.py --openai       # 用 .env 里的 OpenAI 兼容配置

默认只翻译前 2 页以控制耗时/费用。产物输出到 testdata/out/。
"""
import asyncio
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings  # noqa: E402
from app.core.pdf2zh_runner import translate_pdf  # noqa: E402

PDF_PATH = BASE_DIR / "testdata" / "attention.pdf"
OUT_DIR = BASE_DIR / "testdata" / "out"


async def main() -> int:
    if not PDF_PATH.exists():
        print(f"[FAIL] 测试 PDF 不存在: {PDF_PATH}")
        print("       可运行: curl -L https://arxiv.org/pdf/1706.03762 -o testdata/attention.pdf")
        return 2

    use_openai = "--openai" in sys.argv
    service = "openai" if use_openai and settings.llm_configured else "siliconflowfree"
    if service == "openai":
        print(f"[INFO] 使用 .env 配置: base_url={settings.llm_base_url} model={settings.llm_model}")
    else:
        print("[INFO] 使用内置 SiliconFlow 免费服务（仅用于链路验证）")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("attention.*"):
        old.unlink()

    t0 = time.monotonic()

    def on_progress(stage: str, percent) -> None:
        pct = f"{percent:.0f}%" if percent is not None else "-"
        print(f"  [{stage}] {pct}")

    try:
        result = await translate_pdf(
            PDF_PATH,
            OUT_DIR,
            service=service,
            lang_in=settings.lang_in,
            lang_out=settings.lang_out,
            dual=settings.enable_dual,
            qps=settings.qps,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            pages="1-2",
            on_progress=on_progress,
        )
    except RuntimeError as exc:
        print(f"[FAIL] 翻译失败: {exc}")
        return 1

    print(f"[OK] 翻译完成，耗时 {time.monotonic() - t0:.1f}s（引擎内部 {result.duration:.1f}s）")
    for label, p in [("纯译文 mono", result.mono_path), ("双语 dual", result.dual_path),
                     ("术语表", result.glossary_path), ("日志", result.log_path)]:
        print(f"  {label}: {p}")

    if result.mono_path and result.mono_path.stat().st_size > 100_000:
        print("[PASS] 冒烟测试通过")
        return 0
    print("[FAIL] 产物异常")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
