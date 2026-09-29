# 掌柜智库（ZGzhiku Knowledge Base）

> 企业级 RAG（检索增强生成）智能知识库问答系统  
> 将非结构化文档（PDF / Markdown）转化为可检索的结构化知识，提供精准的多路召回 + 流式问答能力。

---

## 📖 项目简介

**掌柜智库** 是一个面向垂直领域（电子产品手册、维修指南、技术文档等）的智能知识库系统，基于 RAG 技术构建。系统包含两条核心流水线：

- **数据导入流水线**：上传文件 → 入口判断 → PDF 转 MD → 图片处理 → 文档切分 → 主体识别 → 向量化 → 存入 Milvus
- **检索问答流水线**：用户提问 → 产品确认 → 向量检索 → HyDE 检索 → 网络搜索 → RRF 融合 → Rerank 重排 → 生成答案

### 核心功能

| 功能模块 | 描述 |
|---------|------|
| 文档智能导入 | 支持 PDF / Markdown 上传，自动解析、切分、向量化 |
| 混合向量检索 | 稠密向量 + 稀疏向量（BM25）混合检索 |
| 多路召回融合 | 向量检索 + HyDE 假想文档 + MCP Web 搜索 |
| 智能重排序 | Reranker 模型精排 + 断崖检测动态截断 |
| 流式问答 | SSE 实时推送，逐字输出答案 |
| 会话历史管理 | MongoDB 存储对话历史，支持多轮上下文（代词改写） |

---

## 🏗️ 系统架构

### 四层架构

| 层级 | 职责 | 技术实现 |
|------|------|---------|
| API 层 | HTTP 接口、请求路由 | FastAPI + Uvicorn |
| Processor 层 | 业务流程编排、节点调度 | LangGraph |
| Utils 层 | 工具函数封装、外部服务调用 | Python 模块 |
| 数据层 | 数据持久化、检索 | Milvus / MongoDB / MinIO |

### 关键架构决策：全 API 方案

本项目与课程原方案的最大差异是 **全 API 方案**（适配 4 核 8G 轻量服务器，无需本地 GPU）：

| 能力 | 课程原方案 | 本项目方案 |
|------|-----------|-----------|
| LLM 问答 | DashScope API | qwen-flash API |
| 图片理解 | DashScope API | qwen3-vl-flash API |
| 文本向量化 | 本地 BGE-M3 | text-embedding-v4 API（1024 维） |
| 检索重排 | 本地 BGE-Reranker | gte-rerank-v2 API |

**好处**：不下载 GB 级模型、不装 torch / FlagEmbedding、4 核 8G 服务器足够、开发期几乎零成本。

---

## 🛠️ 技术栈

| 类别 | 选型 | 说明 |
|------|------|------|
| 工作流编排 | LangGraph | 有状态多节点流程图 |
| Web 框架 | FastAPI | 异步 + SSE 流式输出 |
| 向量数据库 | Milvus 2.5.5 (+Attu 2.5.10) | 混合检索（稠密 + 稀疏向量） |
| 对象存储 | MinIO | 存原始 PDF / 图片 |
| 文档数据库 | MongoDB | 存对话历史 |
| PDF 解析 | MinerU API | PDF → Markdown |
| 容器化 | Docker + Docker Compose | 全部中间件容器部署 |
| 包管理 | uv | 极速 Python 包管理器 |

---

## 📁 目录结构

```
knowledge_base/
├── processor/
│   ├── import_processor/      # 数据导入分支（7 节点）
│   │   ├── nodes/             # node_entry / node_pdf_to_md / node_md_img /
│   │   │                      # node_document_split / node_item_name_recognition /
│   │   │                      # node_bge_embedding / node_import_milvus
│   │   ├── prompt/            # 商品名识别提示词
│   │   ├── base.py            # BaseNode 模板方法
│   │   ├── state.py           # TypedDict 状态定义
│   │   └── main_graph.py      # 导入主图（LangGraph 编排）
│   └── query_processor/       # 检索问答分支（7 节点）
│       ├── nodes/             # node_item_name_confirm / node_search_embedding /
│       │                      # node_search_embedding_hyde / node_web_search_mcp /
│       │                      # node_rrf / node_rerank / node_answer_output
│       ├── prompt/            # 主体确认 / HyDE / 答案生成 提示词
│       ├── base.py
│       ├── state.py
│       └── main_graph.py      # 检索主图（并行三路搜索 + RRF + Rerank）
├── config/                    # 配置包（LLM / Milvus / MinIO / Reranker / MCP）
├── utils/                     # 工具函数（Milvus / MinIO / Embedding / SSE / ...）
├── web/
│   ├── api/
│   │   ├── query_service.py   # 查询服务（端口 8001，5 接口 + SSE）
│   │   └── import_service.py  # 导入服务（端口 8000，3 接口）
│   └── page/                  # chat.html / import.html
├── tool/logger.py             # 全局彩色日志
├── test/                      # 单元测试与端到端测试
├── studynote/                 # 学习笔记与开发日记
│   ├── note/                  # 课程笔记（项目简介、原理讲解）
│   └── dairy/                 # 开发日记 + 项目复现指南
├── doc/                       # 测试用 PDF 文档（不入库）
├── output/                    # 节点产出（不入库）
├── pyproject.toml
├── .env.example               # 环境变量模板
└── .gitignore
```
---

## 🚀 快速开始

### 前置条件

- **云服务器**：4 核 8G 起，Ubuntu 22.04 LTS
- **Docker + Docker Compose**：用于部署 Milvus / MinIO / MongoDB
- **Python 3.11 + uv**：项目运行环境
- **DashScope API Key**：阿里云通义千问 API（新用户有免费额度）
- **MinerU API Token**：PDF 转 Markdown 服务

### 1. 部署中间件

部署 Milvus（含 etcd + 内置 MinIO + Attu）、独立 MinIO、MongoDB，开放端口：22 / 7000 / 9000-9001 / 19530 / 27017 / 8000-8001。

详细步骤参见 `studynote/dairy/00【掌柜智库】项目复现指南.md` 第四章。

### 2. 克隆代码 + 配置环境

```bash
git clone git@github.com :kingopps/knowledge-base.git
cd knowledge-base

# 复制环境变量模板并填入真实值
cp .env.example .env
nano .env   # 替换所有占位符为你的真实 Key / IP / 密码

```
### 3. 安装依赖

```bash
uv sync
```

### 4. 启动服务

```bash
# 终端 1：导入服务（端口 8000）
uv run python -m web.api.import_service

# 终端 2：查询服务（端口 8001）
uv run python -m web.api.query_service

```

### 5. 验证

```bash
# 健康检查
curl http://localhost:8000/health curl http://localhost:8001/health

# 上传 PDF 导入知识库
curl -X POST http://localhost:8000/upload -F "files=@doc/your.pdf"

# 提问（非流式）
curl -X POST http://localhost:8001/query
 -H "Content-Type: application/json"
 -d '{"query":"你的问题","is_stream":false}'


浏览器访问：
- 聊天页面：`http://服 务器IP:8001/chat.html`
- 导入页面：`http://服 务器IP:8000/import.html`
- Swagger 文档：`http://服 务器IP:8001/docs` / `http://服 务器IP:8000/docs`
- Milvus Attu：`http://服 务器IP:7000`
- MinIO 控制台：`http://服 务器IP:9001`

---

## 🔧 环境变量

所有环境变量定义在 `.env` 中，模板见 [`.env.example`](.env.example)。主要变量：

| 变量 | 说明 |
|------|------|
| `OPENAI_API_KEY` | DashScope API Key（兼容 OpenAI 格式） |
| `OPENAI_API_BASE` | DashScope 兼容模式地址 |
| `LLM_DEFAULT_MODEL` | 默认 LLM 模型（qwen-flash） |
| `VL_MODEL` | 视觉语言模型（qwen3-vl-flash） |
| `EMBEDDING_MODEL` | 嵌入模型（text-embedding-v4，1024 维） |
| `RERANK_MODEL` | 重排序模型（gte-rerank-v2） |
| `MILVUS_URL` | Milvus 连接地址 |
| `CHUNKS_COLLECTION` / `ITEM_NAME_COLLECTION` | Milvus 集合名 |
| `MONGO_URL` / `MONGO_DB_NAME` | MongoDB 连接信息 |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO 连接信息 |
| `MINERU_API_TOKEN` / `MINERU_BASE_URL` | MinerU PDF 转 MD 服务 |

> ⚠️ **安全提示**：`.env` 文件已在 `.gitignore` 中忽略，**切勿将真实 Key 提交到 Git**。

---

## 📡 API 接口

### 导入服务（端口 8000）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/upload` | 上传 PDF/MD 文件，触发后台 LangGraph 导入任务 |
| GET | `/status/{task_id}` | 查询导入任务进度（节点完成列表） |

### 查询服务（端口 8001）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/query` | 提交问题（`is_stream=true` 触发 SSE 流式） |
| GET | `/stream/{session_id}` | SSE 流式推送（ready → progress → delta → final） |
| GET | `/history/{session_id}` | 获取对话历史 |

---

## 📚 学习资料

本项目配套有完整的学习笔记与开发日记，位于 `studynote/` 目录：

- `studynote/note/`：课程笔记（项目简介、原理讲解、技术栈详解）
- `studynote/dairy/`：开发日记 + **项目复现指南**（含 36 个踩坑记录、10 天开发计划、常用命令速查）

> 任何人按 `studynote/dairy/00【掌柜智库】项目复现指南.md` 从零操作，可 1:1 复现当前全部进度。

---

## ⚠️ 重要说明

1. **敏感信息**：`.env`、`.env.bak.*`、`*.pem`、`*.key` 已在 `.gitignore` 中忽略，请勿提交真实密钥。
2. **不入库目录**：`doc/`（PDF 源数据）、`output/`（节点产出）、`.venv/`（虚拟环境）、`__pycache__/` 均不入库。
3. **运行方式**：所有节点和服务统一用 `uv run python -m 模块路径` 运行，避免绝对 import 失败。
4. **测试块要求**：节点的 `__main__` 测试块必须包含 `task_id`（导入分支）或 `session_id`（检索分支），否则会报 KeyError。

---

## 📝 开发进度

| 里程碑 | 状态 |
|--------|------|
| 数据导入 7 节点 + 主图编排 | ✅ 完成 |
| 检索问答 7 节点 + 主图端到端 | ✅ 完成 |
| FastAPI 双服务 + SSE 流式输出 | ✅ 完成 |
| 多轮对话历史 + 导入服务 | ✅ 完成 |
| 全流程联调（上传 → 导入 → 提问 → 流式回答） | ✅ 完成 |
| 前端页面 + 多文档测试 | ✅ 完成 |
| 部署优化（Nginx / 进程守护 / 日志） | 🚧 待办 |

详细进度与 47 项验证清单见 `studynote/dairy/00【掌柜智库】项目复现指南.md`。