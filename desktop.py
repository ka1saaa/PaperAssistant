"""论文助手桌面模式：双击运行，独立窗口打开，无需浏览器。

服务以后台线程运行（随机空闲端口，避免冲突），窗口关闭即退出。
WebView2 不可用时自动回退到系统浏览器。
"""
import multiprocessing
import socket
import threading
import time

multiprocessing.freeze_support()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def main() -> None:
    port = _free_port()
    url = f"http://127.0.0.1:{port}"

    import uvicorn
    from app.main import app

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    import httpx

    for _ in range(120):
        try:
            if httpx.get(f"{url}/api/health", timeout=0.5).status_code == 200:
                break
        except Exception:
            time.sleep(0.15)

    try:
        import webview

        webview.create_window(
            "论文助手 · PaperAssistant",
            url,
            width=1280,
            height=880,
            min_size=(980, 640),
        )
        webview.start()
    except Exception as exc:  # noqa: BLE001 — WebView2 缺失等环境问题
        print(f"桌面窗口不可用（{exc}），回退到系统浏览器：{url}")
        import webbrowser

        webbrowser.open(url)
        while thread.is_alive():
            time.sleep(1)


if __name__ == "__main__":
    main()
