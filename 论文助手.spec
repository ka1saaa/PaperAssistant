# -*- mode: python ; coding: utf-8 -*-
"""论文助手桌面应用打包配置（onedir，双 exe）。

构建：.venv/Scripts/pyinstaller 论文助手.spec --noconfirm
产物：dist/论文助手/ 下的 论文助手.exe（主程序）与 pdf2zh_next.exe（翻译子进程）
"""
import importlib.util
import os
import shutil
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

PROJECT = Path(SPECPATH)

hidden = []
hidden += collect_submodules("uvicorn")            # 动态加载的 loop/protocol 模块
hidden += ["uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
           "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
           "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
           "uvicorn.lifespan", "uvicorn.lifespan.on"]
hidden += collect_submodules("babeldoc")
hidden += collect_submodules("pdf2zh_next")
hidden += collect_submodules("pdf2zh_next.translator.translator_impl")  # 翻译器插件按名动态导入
hidden += collect_submodules("pdf2zh_next.translator")
hidden += collect_submodules("pydantic")
hidden += collect_submodules("bitstring")   # 懒加载后端 bitstore_*
hidden += collect_submodules("tiktoken_ext")  # tiktoken 编码注册插件
binaries = []
binaries += collect_dynamic_libs("pypdfium2")
binaries += collect_dynamic_libs("pymupdf")
# hyperscan 的 pyd 依赖哈希命名的 msvcp140 DLL（WinSxS 解析，PyInstaller 环境缺失），
# 把系统 msvcp140.dll 复制成该名字原位打包
import shutil
_hs = importlib.util.find_spec("hyperscan")
if _hs and _hs.submodule_search_locations:
    _hs_dir = Path(next(iter(_hs.submodule_search_locations)))
    for _pyd in _hs_dir.glob("_hs_ext*.pyd"):
        import re as _re
        _data = _pyd.read_bytes()
        for _name in sorted(set(m.group(0).decode() for m in
                                _re.finditer(rb"msvcp140[a-f0-9\-]*\.dll", _data))):
            _sys_dll = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "msvcp140.dll"
            if _sys_dll.exists():
                _staged = PROJECT / "build" / "hyperscan_dll" / _name
                _staged.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(_sys_dll, _staged)
                binaries.append((str(_staged), "hyperscan"))
hidden += ["httpx", "anyio", "sniffio", "certifi"]

datas = []
datas += [(p, str(Path(d).parent)) for p, d in collect_data_files("babeldoc", include_py_files=True)]
datas += collect_data_files("pdf2zh_next")
datas += collect_data_files("webview")
datas += [(PROJECT / "app" / "templates", "app/templates")]
datas += [(PROJECT / "app" / "static", "app/static")]
datas += [(PROJECT / ".env.example", ".")]

a_main = Analysis(
    [str(PROJECT / "desktop.py")],
    pathex=[str(PROJECT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "IPython"],
    noarchive=False,
)

a_cli = Analysis(
    [str(PROJECT / "scripts" / "pdf2zh_next_bridge.py")],
    pathex=[str(PROJECT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "pandas", "IPython"],
    noarchive=False,
)

pyz_main = PYZ(a_main.pure)
pyz_cli = PYZ(a_cli.pure)

exe_main = EXE(
    pyz_main,
    a_main.scripts,
    [],
    exclude_binaries=True,
    name="论文助手",
    debug=False,
    console=False,           # 桌面应用：无黑窗
    icon=str(PROJECT / "icon.ico"),
    disable_windowed_traceback=False,
)
exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="pdf2zh_next",
    debug=False,
    console=True,            # 子进程：保留控制台管道以解析进度
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe_main,
    a_main.binaries,
    a_main.datas,
    exe_cli,
    a_cli.binaries,
    a_cli.datas,
    strip=False,
    upx=False,
    name="论文助手",
)
