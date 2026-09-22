"""开发模式快速回归：APP_DIR 引入后服务仍正常。"""
import threading

import httpx
import uvicorn

from app.main import app

cfg = uvicorn.Config(app, host="127.0.0.1", port=8765, log_level="error")
server = uvicorn.Server(cfg)
t = threading.Thread(target=server.run, daemon=True)
t.start()
for _ in range(50):
    try:
        if httpx.get("http://127.0.0.1:8765/api/health", timeout=0.5).status_code == 200:
            break
    except Exception:
        time.sleep(0.2)
r = httpx.get("http://127.0.0.1:8765/")
print("首页:", r.status_code, "| 含静态引用:", "/static/app.js" in r.text)
js = httpx.get("http://127.0.0.1:8765/static/app.js?v=18")
print("静态JS:", js.status_code)
