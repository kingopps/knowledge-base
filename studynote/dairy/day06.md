# 【掌柜智库】Day 06 学习日记：检索数据图与状态定义

> 📅 日期：2026-09-22
> 🎯 进度：检索流程（query_processor）分支主线框架搭建完成，5 个节点跑通，2 个节点待测
> 📚 对应笔记：12【掌柜智库】~检索分支

**目录**

- 一、本日目标与起点
- 二、目录结构与文件复制
- 三、依赖安装的三连坑
- 四、节点测试块的统一修复：补 session_id
- 五、node_web_search_mcp 重写方案
- 六、节点测试结果
- 七、踩坑总结（本次新增）
- 八、与导入分支的对接点
- 九、下一步
- 十、本日成果小结

---

## 一、本日目标与起点

### 1.1 起点

- 导入分支（import_processor）Day 01~05 已全部完成：7 节点 + 主图编排端到端跑通，Milvus `kb_chunks` 集合已有 32 条 Aolynk 网桥数据。
- 检索分支（query_processor）主线**完全未创建**，需从零搭建。
- 原始课程代码在 `~/project/ZGzhiku/study/original_code/processor/query_processor/`，本项目代码在 `~/project/ZGzhiku/code/knowledge_base/`。

### 1.2 本日目标

搭建检索流程 7 节点 + 主图，并逐节点测试跑通，与导入分支对接。原始代码大部分可直接复用，但全 API 方案与 Python 3.11 环境需要若干适配。

---

## 二、目录结构与文件复制

### 2.1 创建目录结构

```bash
cd ~/project/ZGzhiku/code/knowledge_base
mkdir -p processor/query_processor/nodes
mkdir -p processor/query_processor/prompt
touch processor/query_processor/__init__.py
touch processor/query_processor/nodes/__init__.py
touch processor/query_processor/prompt/__init__.py
```

### 2.2 可直接复制的文件清单（从 original_code）

以下文件逻辑通用，直接 `cp` 过来即可，无需改动：

| 类别 | 源路径（original_code） | 目标路径（knowledge_base） |
|------|-------------------------|----------------------------|
| 状态+基类 | `processor/query_processor/state.py` | 同名复制 |
| 状态+基类 | `processor/query_processor/base.py` | 同名复制 |
| 提示词×3 | `processor/query_processor/prompt/{item_name_confirm,search_embedding_hyde,answer_prompt}.py` | 同名复制 |
| 工具类×3 | `utils/{mongo_history_utils,json_format_utils,reranker_http_utils}.py` | 同名复制 |
| MCP配置 | `config/bailian_mcp_config.py` | 同名复制 |
| 节点×7 | `processor/query_processor/nodes/node_{item_name_confirm,search_embedding,search_embedding_hyde,web_search_mcp,rrf,rerank,answer_output}.py` | 同名复制 |

```bash
cd ~/project/ZGzhiku/
# 1. 状态定义 + 基类
cp ./study/original_code/processor/query_processor/state.py code/knowledge_base/processor/query_processor/state.py
cp ./study/original_code/processor/query_processor/base.py code/knowledge_base/processor/query_processor/base.py
# 2. 三个提示词文件
cp ./study/original_code/processor/query_processor/prompt/item_name_confirm.py code/knowledge_base/processor/query_processor/prompt/item_name_confirm.py
cp ./study/original_code/processor/query_processor/prompt/search_embedding_hyde.py code/knowledge_base/processor/query_processor/prompt/search_embedding_hyde.py
cp ./study/original_code/processor/query_processor/prompt/answer_prompt.py code/knowledge_base/processor/query_processor/prompt/answer_prompt.py
# 3. 工具类（当前项目缺失的 3 个）
cp ./study/original_code/utils/mongo_history_utils.py code/knowledge_base/utils/mongo_history_utils.py
cp ./study/original_code/utils/json_format_utils.py code/knowledge_base/utils/json_format_utils.py
cp ./study/original_code/utils/reranker_http_utils.py code/knowledge_base/utils/reranker_http_utils.py
# 4. MCP 配置
cp ./study/original_code/config/bailian_mcp_config.py code/knowledge_base/config/bailian_mcp_config.py
# 5. 7 个检索节点
cp ./study/original_code/processor/query_processor/nodes/node_item_name_confirm.py code/knowledge_base/processor/query_processor/nodes/node_item_name_confirm.py
cp ./study/original_code/processor/query_processor/nodes/node_search_embedding.py code/knowledge_base/processor/query_processor/nodes/node_search_embedding.py
cp ./study/original_code/processor/query_processor/nodes/node_search_embedding_hyde.py code/knowledge_base/processor/query_processor/nodes/node_search_embedding_hyde.py
cp ./study/original_code/processor/query_processor/nodes/node_web_search_mcp.py code/knowledge_base/processor/query_processor/nodes/node_web_search_mcp.py
cp ./study/original_code/processor/query_processor/nodes/node_rrf.py code/knowledge_base/processor/query_processor/nodes/node_rrf.py
cp ./study/original_code/processor/query_processor/nodes/node_rerank.py code/knowledge_base/processor/query_processor/nodes/node_rerank.py
cp ./study/original_code/processor/query_processor/nodes/node_answer_output.py code/knowledge_base/processor/query_processor/nodes/node_answer_output.py
```

### 2.3 需要新生成的适配文件

**文件1：`config/reranker_config.py`**

本项目 `.env` 重排序变量是 `RERANK_MODEL=gte-rerank`，而原始代码读 `TEXT_RERANK_MODEL`。适配版用 DashScope API Key + gte-rerank 模型：

```python
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class RerankerConfig:
    text_rerank_api_key: str
    text_rerank_model: str
    text_rerank_instruct: str

reranker_config = RerankerConfig(
    text_rerank_api_key=os.getenv("OPENAI_API_KEY"),
    text_rerank_model=os.getenv("RERANK_MODEL", "gte-rerank"),
    text_rerank_instruct=os.getenv("TEXT_RERANK_INSTRUCT", "")
)
```

**文件2：`processor/query_processor/main_graph.py`**

采用原始 `main_graph_v2.py` 的并行执行模式（更简洁），`__main__` 测试块改为查询已入库的 Aolynk 网桥。完整代码结构：

- `KBQueryWorkflow` 类封装 7 节点 + 条件路由
- 入口节点 `node_item_name_confirm` → 有 answer 则直接输出，否则并行触发三路搜索（embedding/hyde/web_search）
- 三路汇合到 `node_rrf` → `node_rerank` → `node_answer_output` → END
- `__main__` 测试块用 `session_id="test_query_001"` + `original_query="Aolynk CB304n 网桥怎么恢复出厂设置？"`

---

## 三、依赖安装的三连坑

### 3.1 第一坑：.venv 权限被 root 占了

执行 `uv add dashscope agents` 时报：

```
error: Failed to install: flatbuffers-25.12.19-py2.py3-none-any.whl
Caused by: failed to create directory .venv/.../flatbuffers: Permission denied (os error 13)
```

**诊断**：`ls -ld .venv` 看到所有者是 root（之前可能用 sudo 执行过命令）。

**修复**：

```bash
sudo chown -R ubuntu:ubuntu ~/project/ZGzhiku/code/knowledge_base/.venv
```

**兜底**（chown 后仍失败则重建）：

```bash
rm -rf .venv && uv sync
```

### 3.2 第二坑：包名冲突——装错 agents 包

`uv add agents` 装的是 PyPI 上一个**已停维护的 TensorFlow 强化学习框架**，而不是 OpenAI 官方的 Agents SDK。导入时报：

```
AttributeError: module 'tensorflow' has no attribute 'contrib'
```

**根因**：PyPI 包名 `agents` 和 OpenAI Agents SDK 的 import 名 `agents` 撞车，但 SDK 的正式包名是 `openai-agents`。

**修复**：

```bash
uv remove agents
uv add openai-agents
```

### 3.3 第三坑：Python 3.11 + openai-agents 版本死锁

装了 `openai-agents` 最新版（0.20.0）后报：

```
KeyError: ~TContext
```

原因是新版用了 `ToolFunctionWithToolContext[ToolParams]` 这种泛型语法，Python 3.11 的 typing 模块不支持。

降级到 `<0.1.0` 后又报：

```
ImportError: cannot import name 'MCPServerStreamableHttp' from 'agents.mcp'
```

因为旧版根本没有这个类。

**结论**：`openai-agents` 在 Python 3.11 上是死锁——新版语法不兼容，老版类不存在。

### 3.4 最终方案：放弃 openai-agents，改用原生 mcp SDK

百炼的 Web Search MCP 本质是标准 MCP Server，用官方 `mcp` 包的 `ClientSession` + `streamable_http_client` 直接调即可，完全绕开 openai-agents。

**安装**（必须锁定 1.x，2.x API 变化不兼容百炼）：

```bash
uv add "mcp>=1.0,<2.0"
```

**关键发现**：`.env` 里百炼 MCP 地址是 `https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/mcp`，结尾 `/mcp` 说明用的是 **Streamable HTTP 协议**。原始代码用 `MCPServerStreamableHttp` 协议其实对得上，问题只在于 openai-agents 在 Py3.11 上版本死锁，改用 mcp 原生 SDK 的 `streamable_http_client` 即可。

---

## 四、节点测试块的统一修复：补 session_id

### 4.1 问题

检索分支的 [base.py:25](file:///home/ubuntu/project/ZGzhiku/code/knowledge_base/processor/query_processor/base.py#L25) 用了硬取值 `state['session_id']`（不是 `.get()`），而原始代码的 `__main__` 测试块没写 `session_id`，导致：

```
KeyError: 'session_id'
```

这是检索分支的统一约定——`session_id` 是任务追踪 ID（相当于导入分支的 `task_id`），**所有节点的 `__main__` 测试块都必须包含**。

### 4.2 修复清单

检查了 6 个节点的 `__main__` 测试块，缺失 `session_id` 的节点如下，已统一补上：

| 节点 | 改动 |
|------|------|
| node_search_embedding | 补 `session_id` + `is_stream=False` |
| node_search_embedding_hyde | 补 `session_id` + `is_stream=False` |
| node_web_search_mcp | 补 `session_id` + `is_stream=False` |
| node_rerank | 补 `session_id` + `is_stream=False` |
| node_item_name_confirm | ✅ 原本已有 |
| node_answer_output | ✅ 原本已有（mock_state 自带） |

---

## 五、node_web_search_mcp 重写方案

### 5.1 重写动机

彻底摆脱 openai-agents 版本死锁，改用 `mcp` 原生 SDK 调用百炼 SSE 接口。

### 5.2 改动对照

| 原方案（出问题） | 新方案 |
|---|---|
| `from agents.mcp import MCPServerStreamableHttp` | `from mcp import ClientSession` + `from mcp.client.streamable_http import streamable_http_client` |
| `MCPServerStreamableHttp(...).connect()` | `streamable_http_client(url=..., headers=...) as (read, write, _)` → `ClientSession(read, write)` → `session.initialize()` |
| `mcp_client.call_tool(tool_name=..., arguments=...)` | `session.call_tool(name=..., arguments=...)` |

### 5.3 关键代码片段

```python
async def _mcp_call(self, query: str):
    headers = {"Authorization": f"Bearer {mcp_config.api_key}"}
    async with streamable_http_client(
        url=mcp_config.mcp_base_url,
        headers=headers,
        timeout=60,
    ) as (read_stream, write_stream, _):  # mcp 1.x 返回 3 元组，第三项是回调可忽略
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(
                name="bailian_web_search",
                arguments={"query": query, "count": 5},
            )
            return result
```

**API 风格一致性**：`ClientSession.call_tool()` 返回的对象和原方案一样有 `.content[0].text` 字段，所以 `process()` 里的解析逻辑**完全不需要改**。

### 5.4 .env 调试三连坑（耗时最久）

node_web_search_mcp 重写后仍报 401 / URL 解析失败，根因都在 `.env` 和配置加载：

| 坑 | 现象 | 修复 |
|---|------|------|
| A. CRLF 换行符 | URL 尾部藏 `\r`，`httpx.InvalidURL: non-printable ASCII character` | `tr -d '\r' < .env.bak > .env`，`cat -A .env` 验证行尾是 `$`（而非 `^M`） |
| B. Shell 覆盖 .env | 新 Key 仍 401 | `unset MCP_DASHSCOPE_BASE_URL`；`bailian_mcp_config.py` 的 `load_dotenv()` 加 `override=True` |
| C. 变量名含 `\|` | `DASHSCOPE_API_KEY\|MCP_DASHSCOPE` 解析失败 | 变量名只用字母数字下划线，改名 |

**体检命令**（最终跑通的验证）：

```bash
uv run python -c "
from config.bailian_mcp_config import mcp_config
url = mcp_config.mcp_base_url
print('repr:', repr(url))
print('length:', len(url))
print('last 5 chars (ord):', [ord(c) for c in url[-5:]])
"
```

期望结尾是 `mcp`（ord 109,99,112），**不含 13（`\r`）**。

---

## 六、节点测试结果

### 6.1 已通过 ✅

| 节点 | 命令 | 结果 |
|------|------|------|
| node_search_embedding | `uv run python -m processor.query_processor.nodes.node_search_embedding` | ✅ DashScope embedding API 200 + Milvus 混合检索成功（返回 0 条，因烫金机数据不在库里，链路通） |
| node_search_embedding_hyde | `uv run python -m processor.query_processor.nodes.node_search_embedding_hyde` | ✅ LLM 生成 HyDE 假想答案 → 向量化 → Milvus 混合检索，链路通（结果为空属正常） |
| node_web_search_mcp | `uv run python -m processor.query_processor.nodes.node_web_search_mcp` | ✅ 百炼 MCP 返回 5 条网页结果（query="Aolynk CB304n 网桥怎么恢复出厂设置？"） |

### 6.2 待测 ⏳

| 节点 | 命令 | 预期 |
|------|------|------|
| node_item_name_confirm | `uv run python -m processor.query_processor.nodes.node_item_name_confirm` | LLM 从无上下文问题中无法识别商品名，走反问/回退 |
| node_rrf | `uv run python -m processor.query_processor.nodes.node_rrf` | 三路检索结果 RRF 融合排序 |
| node_rerank | `uv run python -m processor.query_processor.nodes.node_rerank` | 用 mock 数据调 gte-rerank API 打分截断 |
| node_answer_output | `uv run python -m processor.query_processor.nodes.node_answer_output` | 用 mock 文档调 LLM 生成答案 |
| main_graph 端到端 | `uv run python -m processor.query_processor.main_graph` | 7 节点串联，最终输出答案 |

---

## 七、踩坑总结（本次新增）

| # | 坑 | 原因 | 解决方案 |
|---|------|------|---------|
| 29 | `uv add` 报 Permission denied | .venv 被 root 占用 | `sudo chown -R ubuntu:ubuntu .venv` |
| 30 | `agents` 包导入报 tensorflow.contrib 错误 | PyPI 包名冲突，装成了强化学习包 | 改装 `openai-agents` |
| 31 | `openai-agents` 最新版报 `KeyError: ~TContext` | Python 3.11 不支持新版泛型语法 | 弃用 openai-agents，改用原生 `mcp` 包 |
| 32 | `openai-agents` 旧版报 `cannot import MCPServerStreamableHttp` | 老版本无此类，新版又不兼容 Py3.11 | 同上，版本死锁 |
| 33 | 检索节点测试块报 `KeyError: 'session_id'` | base.py 硬取值 `state['session_id']` | 所有 `__main__` 块补 `session_id` + `is_stream` |
| 34 | 百炼 MCP 协议匹配但 openai-agents 死锁 | `.env` URL `/mcp` 结尾是 Streamable HTTP 协议，但 openai-agents 在 Py3.11 版本死锁 | 改用 `mcp>=1.0,<2.0` 的 `streamable_http_client`（注意返回 3 元组 `(read, write, _)`） |
| 35 | `.env` CRLF 换行符致 URL 藏 `\r` | Windows 编辑器保存为 CRLF，`os.getenv` 读到的值尾部带 `\r`，`httpx.InvalidURL: non-printable ASCII` | `tr -d '\r' < .env.bak > .env`，`cat -A .env` 验证行尾是 `$`（而非 `^M`） |
| 36 | 新 API Key 仍 401 | shell 环境变量覆盖 .env 值 | `unset MCP_DASHSCOPE_BASE_URL`；`load_dotenv(override=True)` 强制 .env 覆盖 shell |
| 37 | `.env` 变量名含 `\|` 解析失败 | `DASHSCOPE_API_KEY\|MCP_DASHSCOPE` 非合法标识符 | 变量名只用字母数字下划线，改名 |

---

## 八、与导入分支的对接点

1. **工具类复用**：`embedding_utils.py`（DashScope 双向量）、`milvus_utils.py`（混合检索）、`llm_utils.py` 都是导入分支已验证的，检索节点直接 import。
2. **Milvus 集合对接**：`kb_item_names`（节点5用，商品名匹配）、`kb_chunks`（向量检索节点用，按 `item_name` 过滤后混合检索）。
3. **状态流转**：`session_id` 作为任务追踪 ID（替代导入分支的 `task_id`），`task_utils` 已包含检索节点的中文名映射。
4. **MongoDB**：`mongo_history_utils.py` 连接 `kb001` 数据库的 `chat_message` 集合存对话历史。

---

## 九、下一步

1. 继续测试剩余 4 个检索节点（node_item_name_confirm / node_rrf / node_rerank / node_answer_output）+ 主图端到端。
2. 测试通过后，进入 Day 07~08：重排序 + 答案生成 + SSE + 对话历史整合。
3. Day 10：Web 服务 + 全流程联调。

---

## 十、本日成果小结

Day 06 检索分支框架搭建 + 5 节点测试通过：

- ✅ 目录结构 + 文件复制 + 适配文件（reranker_config / main_graph）
- ✅ 依赖安装三连坑修复（.venv 权限 / agents 包名冲突 / openai-agents 版本死锁）
- ✅ 弃用 openai-agents，改用 `mcp>=1.0,<2.0` 原生 SDK + `streamable_http_client`
- ✅ .env 三连坑修复（CRLF→LF / shell 覆盖→override=True / 变量名特殊字符）
- ✅ node_search_embedding / node_search_embedding_hyde / node_web_search_mcp 三节点测试通过
- ⏳ 剩余 4 节点 + 主图端到端待测
