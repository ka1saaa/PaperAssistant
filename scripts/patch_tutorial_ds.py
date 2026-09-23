# -*- coding: utf-8 -*-
"""使用教程：DeepSeek API 推荐与简略调用教程。"""
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "使用教程.md"
s = p.read_text(encoding="utf-8")

old = """## 二、配置大模型（两种方式，推荐界面配置）

翻译质量和 AI 功能取决于你配置的大模型。**两种方式二选一**："""
new = """## 二、配置大模型（两种方式，推荐界面配置）

> **🥇 推荐直接使用 DeepSeek API**：本工具的 AI 助手「小鱼」形象源自 DeepSeek 鲸鱼娘，
> 全部 AI 功能（翻译/概括/解释/对话）都按 OpenAI 兼容接口调用，
> DeepSeek 是性价比最高的选择——注册即送额度，翻译一篇论文只要几分钱。
> **传送门：[https://platform.deepseek.com/](https://platform.deepseek.com/)**

### 🐳 三分钟开通 DeepSeek API（简略教程）

1. 打开 **[DeepSeek 开放平台](https://platform.deepseek.com/)**，注册/登录（手机号即可）
2. 左侧菜单 → **「API keys」** → **创建 API key** → 复制保存（只显示一次）
3. 左侧菜单 → **「充值」** → 充 10 元足够翻译几百篇论文（新用户通常有赠送额度）
4. 打开论文助手的「模型设置」：
   - 服务商选 **DeepSeek**（API 地址自动填好）
   - 粘贴 API Key，模型选 **deepseek-chat**
   - 点「测试连接」→ 保存，完成！

DeepSeek API 就是标准 OpenAI 兼容接口，在任何其他工具里也可以这样调用：

```bash
curl https://api.deepseek.com/chat/completions -H "Content-Type: application/json" -H "Authorization: Bearer 你的APIKey" -d '{"model": "deepseek-chat", "messages": [{"role": "user", "content": "你好"}]}'
```

---

翻译质量和 AI 功能取决于你配置的大模型。除 DeepSeek 外也支持其他服务，**两种配置方式**："""
assert old in s, "第一处未匹配"
s = s.replace(old, new, 1)

old2 = "支持连续追问；点扫帚图标清空对话。"
assert old2 in s, "第二处未匹配"
s = s.replace(
    old2,
    "支持连续追问；点扫帚图标清空对话。小深使用你在「模型设置」里配置的模型（推荐 DeepSeek），一次提问通常不到一分钱。",
    1,
)

p.write_text(s, encoding="utf-8")
print("教程 OK")
