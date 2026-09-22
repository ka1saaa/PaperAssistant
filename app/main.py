"""FastAPI 入口：托管 API、静态资源与单页界面。"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router
from app.config import BASE_DIR
from app.tasks.manager import manager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

STATIC_DIR = BASE_DIR / "app" / "static"
TEMPLATES_DIR = BASE_DIR / "app" / "templates"


@asynccontextmanager
async def lifespan(_: FastAPI):
    await manager.startup()
    logger.info("AutoTranslate ready on http://%s:%s", "127.0.0.1", 8000)
    yield


app = FastAPI(title="AutoTranslate 论文自动翻译", lifespan=lifespan)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {"request": request})
