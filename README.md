# 论文助手 PaperAssistant

本地 Web 服务：搜索 / 上传英文论文 PDF → 大模型翻译 → 输出**保留原论文排版**的译文 PDF（公式、图表、版式与原文一致），可同时生成双语对照版；并提供 **AI 论文概括**（文字摘要 + 流程思维导图 + 核心术语）与**关键词 AI 解释**。

核心翻译由开源项目 [pdf2zh (PDFMathTranslate-next)](https://github.com/PDFMathTranslate/PDFMathTranslate-next) / [BabelDOC](https://github.com/funstory-ai/BabelDOC) 完成，本项目提供论文检索、任务队列、Web 界面、AI 辅助阅读与历史管理。

## 功能

- **联网搜索论文**：arXiv + Semantic Scholar 并发检索、合并去重，一键下载并翻译；中文关键词自动译成英文再检索
- **三种来源**：关键词搜索 / 本地 PDF 拖拽上传 / 粘贴 arXiv ID 或 PDF 链接
- **保留排版翻译**：译文 PDF 与原论文版式一致，公式、图表、超链接不破坏
- **双语对照**：可选生成「左原文 / 右译文」的对照 PDF
- **内置阅读器**：原文/译文/双语对照随切，翻页缩放；选中文字即可**添加批注**（持久保存、点击跳转）或 **AI 解释**（结合论文上下文）
- **AI 论文概括**：中文摘要（研究问题/方法/实验结果/结论）、结构化思维导图、8-10 个核心术语，结果缓存
- **关键词解释**：点术语即出 AI 解释（定义、在论文中的作用、相关术语）
- **界面内切换模型**：左侧底部状态栏点击打开「模型设置」——服务商预设（智谱/DeepSeek/OpenAI/Kimi/自定义）、一键拉取可用模型列表、测试连接，保存即时生效，无需改 .env
- **任务管理**：后台队列（并发 2）、实时进度、可取消、可删除单条/清空历史、SQLite 持久化
- **模型无关**：任何 OpenAI 兼容接口（智谱 GLM / DeepSeek / OpenAI / Kimi…）均可

## 快速开始

**最简单**：双击 **`start.bat`** —— 首次运行会自动创建虚拟环境、安装依赖并生成 `.env` 配置模板（用记事本填入 API Key 后再双击一次即可），浏览器自动打开。

**模型配置也可在界面里完成**：打开网页后点击左侧底部模型状态栏 → 「模型设置」→ 选服务商 / 填 Key / 测试连接 / 保存，即时生效。`.env` 仅作为初始默认值，界面保存的配置优先生效（存于 `model_config.json`）。

**或命令行方式**：

```bash
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python run.py
```

浏览器打开 **http://127.0.0.1:8000** 即可使用。

详细操作说明见 **[使用教程.md](使用教程.md)**（手把手教程：安装配置 / 翻译 / 阅读器批注 / AI 概括 / 故障排查 / FAQ）。

## 项目结构

```
app/
├── main.py                # FastAPI 入口
├── config.py              # .env 配置加载
├── api/routes.py          # REST API（搜索/任务/下载/AI 概括/术语解释）
├── core/
│   ├── pdf2zh_runner.py   # pdf2zh 子进程封装：进度解析、错误分类、产物收集
│   ├── llm.py             # OpenAI 兼容客户端（概括/解释/查询翻译共用）
│   ├── summarizer.py      # AI 论文概括：文本提取 + 摘要/导图/关键词
│   └── search/            # arXiv + Semantic Scholar 检索、PDF 下载
├── tasks/manager.py       # 任务状态机与后台执行
├── storage/db.py          # SQLite 持久化
├── templates/ static/     # 单页前端（侧边栏布局 + AI 弹窗）
scripts/smoke_test.py      # 核心链路冒烟测试
start.bat                  # Windows 双击启动
uploads/ outputs/          # 原文与译文存放
```

## API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/search?q=` | 论文检索（中文自动译英） |
| POST | `/api/tasks/upload` | 上传 PDF 创建翻译任务 |
| POST | `/api/tasks/input` | arXiv ID / PDF 链接创建任务 |
| POST | `/api/tasks/paper` | 搜索结果创建任务 |
| GET | `/api/tasks/{id}` | 任务进度轮询 |
| POST | `/api/tasks/{id}/cancel` | 取消任务 |
| DELETE | `/api/tasks/{id}` | 删除单条历史（含文件） |
| DELETE | `/api/tasks` | 清空全部历史 |
| POST | `/api/tasks/{id}/summarize` | 生成 AI 概括（缓存于 outputs） |
| GET | `/api/tasks/{id}/summary` | 读取已缓存的概括 |
| POST | `/api/explain` | 关键词/选中内容 AI 解释 |
| GET/POST | `/api/tasks/{id}/annotations` | 批注列表 / 添加批注 |
| DELETE | `/api/tasks/{id}/annotations/{aid}` | 删除批注 |
| GET | `/api/tasks/{id}/page/{kind}/{n}` | 单页 PNG（服务端渲染） |
| GET | `/api/tasks/{id}/file/{mono\|dual\|source}` | 下载产物 |
| GET | `/api/tasks` | 任务历史 |

## 已知限制

- **扫描版 PDF 不支持**（无文字层，需 OCR，超出本项目范围）
- 翻译质量与速度取决于所配置的大模型；费用与论文长度成正比
- 极复杂公式偶有排版偏移（BabelDOC 已知问题）
- Semantic Scholar 匿名调用有限流（1 req/s），超限时自动只用 arXiv 结果
