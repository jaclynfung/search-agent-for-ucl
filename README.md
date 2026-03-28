# UCL Bartlett Info Agent
https://search-agent-for-ucl.onrender.com/
一个最小可运行的单 agent 框架，用于回答 UCL The Bartlett 相关问题。

当前版本支持：

- 教授信息查询
- 课程信息查询
- office hour 查询
- 基于意图识别的工具路由
- UCL 官方站点网页搜索（失败时自动回退到本地示例数据）
- 本地网页抓取与真实 FAISS 索引检索

## 设计目标

这个项目刻意保持简单，重点演示单 agent 的核心流程：

1. 识别用户意图
2. 抽取实体
3. 选择工具
4. 检索候选信息
5. 生成结构化答案

## 项目结构

```text
app/
  agent.py
  data.py
  intents.py
  main.py
  models.py
  tools.py
```

## 运行

```bash
python3 -m app.main
```

然后输入示例问题：

- `Who leads The Bartlett School of Architecture?`
- `What does Amy Catania Kulper research?`
- `What are the opening hours for The Bartlett School of Architecture?`

输入 `exit` 退出。

## FastAPI 接口

启动服务：

```bash
uvicorn app.api:app --reload
```

打开页面：

- [http://127.0.0.1:8000](http://127.0.0.1:8000)
- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

接口：

- `GET /health`
- `POST /query`

请求示例：

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"What does Amy Catania Kulper research?"}'
```

返回示例：

```json
{
  "intent": "professor_info",
  "entity": "Amy Catania Kulper",
  "answer": "Amy Catania Kulper is a Professor and Director at UCL The Bartlett. Research areas: architectural design, history and theory, representation.",
  "sources": [
    "https://www.ucl.ac.uk/bartlett/architecture/people"
  ],
  "confidence": "high",
  "routing_reason": "Detected professor-related language in the query."
}
```

## 前端说明

现在已经包含一个轻量前端页面，使用原生 HTML、CSS、JavaScript 直接调用 FastAPI 接口。

这版我没有上 React，原因是：

- 当前页面交互很简单，一个输入框加结果展示就够了
- 不需要额外引入构建工具和前端工程配置
- 更适合你现在这个 demo 阶段，启动和部署都更轻

如果后面你要加这些能力，再考虑 React 会更划算：

- 多页面
- 对话历史管理
- 更复杂的状态流转
- 登录、埋点、组件复用

## 现在有没有用 LLM

当前版本支持可选接入 Gemini。

- 意图识别：优先 Gemini，失败时回退到规则匹配
- search：真实网页搜索 + 本地兜底
- faiss：本地真实索引优先，找不到时回退到示例数据
- answer refine：如果配置了 Gemini，会对检索结果做一次更自然的答案整理

当前搜索范围已收紧到 The Bartlett 主页里的主要 tabs 及其下属学院路径：

- `/bartlett/study`
- `/bartlett/research`
- `/bartlett/our-schools-and-institutes`
- `/bartlett/people`
- `/bartlett/ideas`
- `/bartlett/engage`
- `/bartlett/news-and-events`
- `/bartlett/about`

如果没有配置 Gemini key，系统会自动退回到纯规则版本。

如果日志里出现：

```text
gemini_intent_skip reason=disabled
gemini_refine_skip reason=disabled
```

这说明服务进程启动时没有读到 `GEMINI_API_KEY`。

## 接入 Gemini 免费 LLM

按照 Google 官方文档，Gemini Developer API 提供 free tier，Python SDK 是 `google-genai`。我现在默认接的是 `gemini-2.5-flash-preview-09-2025`，并保留 `gemini-2.5-flash` 作为回退。

参考：

- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini Python quickstart](https://ai.google.dev/gemini-api/docs/get-started/tutorial)
- [Gemini text generation](https://ai.google.dev/gemini-api/docs/text-generation)

1. 在 Google AI Studio 创建 API key
2. 推荐使用 `.env`

先参考 [`.env.example`](/Users/liuchenguang/Documents/job_apply_tool/small-agent/.env.example) 新建本地 `.env`：

```bash
cp .env.example .env
```

然后填入真实值：

```bash
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.5-flash-preview-09-2025
GEMINI_FALLBACK_MODEL=gemini-2.5-flash
APP_STORAGE_DIR=storage
```

应用启动时会自动加载项目根目录下的 `.env`。

3. 或者继续使用 shell 环境变量

```bash
export GEMINI_API_KEY="your_api_key"
export GEMINI_MODEL="gemini-2.5-flash-preview-09-2025"
export GEMINI_FALLBACK_MODEL="gemini-2.5-flash"
```

4. 启动服务

```bash
uvicorn app.api:app --reload
```

配置后，接口返回里会包含：

```json
{
  "llm_used": true
}
```

这表示最终答案经过了 Gemini 整理。

现在 Gemini 会参与两步：

1. 意图识别
2. 结果整合

## 构建本地 FAISS 索引

1. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. 抓取 UCL Bartlett 页面

```bash
python3 scripts/crawl_pages.py --max-pages 20
```

输出会写到 `storage/raw/ucl_bartlett_pages.jsonl`。

3. 构建 FAISS 索引

```bash
python3 scripts/build_faiss_index.py
```

或者一条命令同时抓取并重建：

```bash
python3 scripts/rebuild_index.py --max-pages 25
```

索引会写到：

- `storage/faiss/ucl_bartlett.index`
- `storage/faiss/metadata.json`
- `storage/faiss/vectorizer.pkl`

4. 启动 agent

```bash
python3 -m app.main
```

如果本地索引存在，`FaissTool` 会优先使用真实索引。

## 存储目录

默认情况下，抓取数据和索引会写到项目内的 `storage/`。

如果你要部署到 Render，建议设置：

```bash
export APP_STORAGE_DIR=/var/data
```

这样原始页面和 FAISS 索引就会写到 Render persistent disk 的挂载目录里。

## FAISS 部署建议

最小 demo 场景里，FAISS 最适合和 agent 部署在同一台机器上，作为本地文件索引使用。

- 本地开发：直接放在项目目录下的 `storage/faiss/`
- 单机 demo 服务：和 FastAPI 或 CLI 服务部署在同一个容器/VM
- 线上小规模服务：单独做一个检索服务也可以，但对你这个项目来说通常没有必要

原因很简单：

- FAISS 本质上是一个本地向量索引库，不是一个必须单独部署的数据库
- 对小数据量，最省事的是“本地磁盘索引 + 服务启动时加载”
- 你这个 UCL Bartlett 信息查询 agent 很适合单机架构，简单、稳定、好讲

如果以后数据量大了，再考虑：

- 把抓取和建索引做成离线任务
- 把查询服务做成独立检索层
- 或者换成托管向量数据库

## Render 部署建议

仓库里已经带了 [render.yaml](/Users/liuchenguang/Documents/job_apply_tool/small-agent/render.yaml)，默认配置是：

- Web Service 跑 FastAPI
- `APP_STORAGE_DIR=/var/data`
- 挂一个 Render persistent disk

首次部署后，你有两种方式准备数据：

1. 本地先抓取并把 `storage/` 一起提交部署
2. 在 Render shell 里执行

```bash
python scripts/rebuild_index.py --max-pages 25
```

第二种更适合长期运行，因为索引会直接写到挂载盘 `/var/data`。

## 后续扩展

- 用 LLM 替换规则版意图识别
- 用 embedding 模型替换当前 TF-IDF 向量化
- 增加网页抓取与数据构建脚本
