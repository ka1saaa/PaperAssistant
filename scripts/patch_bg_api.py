# -*- coding: utf-8 -*-
"""routes.py 追加背景上传端点。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "app" / "api" / "routes.py"
s = p.read_text(encoding="utf-8")

marker = "# ---- 论文图谱（引用辐射网络，Semantic Scholar 免费数据） ----"
block = '''# ---- 个性化背景 ----

@router.post("/background/upload")
async def upload_background(file: UploadFile = File(...)) -> dict:
    """上传自定义背景图（jpg/png，≤8MB），保存到应用数据目录。"""
    from app.config import BASE_DIR

    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="图片超过 8MB 限制")
    if data[:3] == b"\\xff\\xd8\\xff":
        ext = ".jpg"
    elif data[:8] == b"\\x89PNG\\r\\n\\x1a\\n":
        ext = ".png"
    else:
        raise HTTPException(status_code=400, detail="仅支持 jpg / png 图片")
    for old in BASE_DIR.glob("bg-custom.*"):
        old.unlink(missing_ok=True)
    (BASE_DIR / f"bg-custom{ext}").write_bytes(data)
    return {"ok": True}


@router.get("/bg-custom")
async def bg_custom():
    """服务自定义背景图文件。"""
    from fastapi.responses import Response

    from app.config import BASE_DIR

    for ext in (".jpg", ".png"):
        f = BASE_DIR / f"bg-custom{ext}"
        if f.exists():
            media = "image/png" if ext == ".png" else "image/jpeg"
            return Response(content=f.read_bytes(), media_type=media)
    raise HTTPException(status_code=404, detail="未上传自定义背景")


@router.get("/background/status")
async def bg_status() -> dict:
    from app.config import BASE_DIR

    return {"custom": any((BASE_DIR / f"bg-custom{e}").exists() for e in (".jpg", ".png"))}


@router.delete("/background/custom")
async def remove_custom_bg() -> dict:
    from app.config import BASE_DIR

    for f in BASE_DIR.glob("bg-custom.*"):
        f.unlink(missing_ok=True)
    return {"ok": True}


''' + marker

assert marker in s
s = s.replace(marker, block, 1)
p.write_text(s, encoding="utf-8")
print("routes OK")
