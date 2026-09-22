"""PyInstaller 桥接：打包为独立 pdf2zh_next.exe 供主程序子进程调用。

行为与 venv 里的 pdf2zh_next 控制台脚本完全一致。
freeze_support 必须最先调用：babeldoc 内部使用 multiprocessing，
冻结环境下缺失它会让子进程递归执行 CLI，造成静默挂起。
"""
import multiprocessing

multiprocessing.freeze_support()

from pdf2zh_next.main import cli  # noqa: E402

if __name__ == "__main__":
    sys_exit = cli()
    raise SystemExit(sys_exit)
