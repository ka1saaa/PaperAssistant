"""OpenAI 兼容接口的轻量客户端。

供论文概括、关键词解释、搜索词翻译共用；配置来自 runtime_config
（Web 界面保存的 model_config.json，未保存时回退 .env）。
"""
import logging

import httpx

from app.core.runtime_config import is_custom_ready, load

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """带用户可读信息的 LLM 调用失败。"""


async def chat_with(base_url: str, api_key: str, model: str, messages: list[dict],
                    *, temperature: float = 0.3, timeout: float = 180.0,
                    max_tokens: int | None = None) -> str:
    """用显式参数调用 chat/completions（用于测试未保存的配置）。"""
    payload = {"model": model, "messages": messages, "temperature": temperature}
    if max_tokens:
        payload["max_tokens"] = max_tokens

    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = await _post_chat(url, headers, payload, timeout)

    text = _content(resp)
    # 部分推理模型会把 max_tokens 预算耗在思考上导致 content 为空，去掉限制重试一次
    if not text and max_tokens:
        payload.pop("max_tokens")
        resp = await _post_chat(url, headers, payload, timeout)
        text = _content(resp)
    return text


async def chat(messages: list[dict], *, temperature: float = 0.3,
               timeout: float = 180.0, max_tokens: int | None = None) -> str:
    """用当前生效配置调用 chat/completions，返回首条回复文本。

    只要配置了自定义模型三要素即可用（service 仅决定 pdf2zh 翻译引擎）。
    """
    cfg = load()
    if not is_custom_ready(cfg):
        raise LLMError(
            "该功能需要大模型：点击左侧底部的模型状态栏打开「模型设置」，"
            "配置 API Key 后即可使用"
        )
    return await chat_with(cfg["base_url"], cfg["api_key"], cfg["model"], messages,
                           temperature=temperature, timeout=timeout, max_tokens=max_tokens)


def _content(resp: httpx.Response) -> str:
    try:
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        raise LLMError("大模型返回格式异常，请重试") from exc


async def _post_chat(url: str, headers: dict, payload: dict, timeout: float) -> httpx.Response:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=headers, json=payload)
    except httpx.HTTPError as exc:
        raise LLMError(f"无法连接大模型服务，请检查网络与 API 地址（{exc}）") from exc

    if resp.status_code == 401:
        raise LLMError("API Key 无效或未授权（401），请检查模型设置中的 Key")
    if resp.status_code == 404:
        raise LLMError("接口不存在（404），请检查 API 地址是否为 OpenAI 兼容根地址")
    if resp.status_code == 429:
        raise LLMError("请求受限或额度不足（429），请稍后重试或降低请求频率")
    if resp.status_code != 200:
        raise LLMError(f"大模型服务返回错误（HTTP {resp.status_code}）")
    return resp
