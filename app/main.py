"""FastAPI 入口：托管 API、静态资源与单页界面。"""
import hashlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.config import APP_DIR
from app.core.runtime_config import load as load_cfg
from app.tasks.manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = APP_DIR / "app" / "static"
TEMPLATES_DIR = APP_DIR / "app" / "templates"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await manager.startup()
    yield


app = FastAPI(title="AutoTranslate 论文自动翻译", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.middleware("http")
async def no_cache_static(request: Request, call_next):
    """静态资源与首页禁用强缓存，避免界面更新后浏览器用旧文件。"""
    resp = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.middleware("http")
async def access_password_middleware(request: Request, call_next):
    """可选访问密码：设置后拦截全部 API（静态页与登录端点除外）。"""
    pwd = load_cfg().get("access_password") or ""
    if pwd:
        path = request.url.path
        exempt = (path == "/" or path.startswith("/static")
                  or path == "/api/health" or path == "/api/auth")
        expected = hashlib.sha256(pwd.encode()).hexdigest()
        ok = request.cookies.get("at_auth") == expected
        if not exempt and not ok:
            return JSONResponse({"detail": "需要访问密码"}, status_code=401)
    return await call_next(request)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"request": request},
        headers={"Cache-Control": "no-cache"},
    )
