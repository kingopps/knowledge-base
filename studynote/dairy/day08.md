/home/ubuntu/project/ZGzhiku/study/dairy/day08.md
# 【掌柜智库】Day 08 学习日记：SSE 流式输出与对话历史完善

> 📅 日期：2026-09-23
> 🎯 今日目标：搭建 FastAPI Web 服务 + SSE 流式输出验证 + 对话历史完善
> ✅ 完成情况：100%（FastAPI 服务启动成功 + SSE 流式输出完整验证通过）

---

## 一、今日任务清单

| 序号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | 创建 web/api/ 目录结构 | ✅ 完成 | 对齐原始代码 `web/api/` 结构 |
| 2 | 编写 query_service.py（查询接口） | ✅ 完成 | 5 个接口：/query、/stream、/history、/health |
| 3 | 修复 main_graph.py 导入错误 | ✅ 完成 | `get_chat_history` → `get_recent_messages` |
| 4 | 修复 base.py 循环导入问题 | ✅ 完成 | 恢复原始设计，进度推送由 task_utils 内部完成 |
| 5 | 非流式查询测试 | ✅ 完成 | curl POST /query 返回完整答案 |
| 6 | SSE 流式查询测试 | ✅ 完成 | 完整事件流：ready → progress → delta → final |
| 7 | 历史记录接口测试 | ✅ 完成 | GET /history/{session_id} 返回对话记录 |

---

## 二、目录结构创建

### 2.1 创建命令

```bash
cd ~/project/ZGzhiku/code/knowledge_base
mkdir -p web/api
touch web/__init__.py
touch web/api/__init__.py
touch web/api/query_service.py
touch web/api/import_service.py
```

### 2.2 目录结构说明

对齐原始代码 `study/original_code/web/api/` 的组织方式：

```
knowledge_base/
├── web/
│   ├── __init__.py
│   └── api/
│       ├── __init__.py
│       ├── query_service.py     # 查询流程接口（Day 08 重点）
│       └── import_service.py    # 导入流程接口（Day 10 联调用）
```

> 💡 之前考虑过在根目录创建 `api/main.py`，但对比原始代码后发现应该用 `web/api/query_service.py`，保持与原始代码一致。

---

## 三、query_service.py 编写

### 3.1 接口清单

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/query` | 查询接口（支持流式/非流式） |
| GET | `/stream/{session_id}` | SSE 流式输出 |
| GET | `/history/{session_id}` | 查询历史记录 |
| DELETE | `/history/{session_id}` | 清空历史记录 |
| GET | `/health` | 健康检查 |

### 3.2 核心设计

**流式模式工作流程**：

```
1. 前端 POST /query（is_stream=true）
2. 后端立即返回 session_id
3. 后台线程启动 LangGraph 工作流
4. 前端用 session_id 连接 GET /stream/{session_id}
5. 后端通过 SSE 推送：ready → progress → delta → final
```

**关键代码结构**：

```python
# 1. 创建 FastAPI 应用
app = FastAPI(title="掌柜智库-查询API")

# 2. 跨域配置
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# 3. 请求数据结构
class QueryRequest(BaseModel):
    query: str          # 用户问题
    session_id: str     # 会话ID（可选）
    is_stream: bool     # 是否流式输出

# 4. 查询接口
@app.post("/query")
async def query(background_tasks, request):
    if is_stream:
        create_sse_queue(session_id)
        background_tasks.add_task(run_query_graph, ...)
        return {"session_id": session_id}
    else:
        run_query_graph(...)
        return {"answer": answer}

# 5. SSE 流式输出接口
@app.get("/stream/{session_id}")
async def stream(session_id, request):
    return StreamingResponse(sse_generator(session_id, request), ...)
```

---

## 四、踩坑记录

### 坑 40：ModuleNotFoundError: No module named 'processor'

**现象**：`uv run python web/api/query_service.py` 报错

**原因**：直接运行脚本时，Python 把脚本目录加入 sys.path，但 `processor` 模块在项目根目录下

**解决方案**：使用 `-m` 模块方式运行：
```bash
uv run python -m web.api.query_service
```

### 坑 41：ImportError: cannot import name 'get_chat_history'

**现象**：`main_graph.py` 导入 `get_chat_history` 失败

**原因**：`mongo_history_utils.py` 中实际函数名是 `get_recent_messages`，之前代码写错了函数名

**解决方案**：修改 `main_graph.py` 两处：
- 第 19 行：`from utils.mongo_history_utils import get_recent_messages`
- 第 86 行：`history = get_recent_messages(session_id, limit=10)`

### 坑 42：name 'push_to_session' is not defined

**现象**：SSE 流式输出时，节点执行到 `node_item_name_confirm` 后报错

**原因**：`base.py` 中被多加了 `push_to_session` 的直接调用和导入，但原始代码的设计是通过 `add_running_task` → `task_utils.py` 内部的 `task_push_queue` → `push_to_session` 间接完成进度推送

**解决方案**：恢复 `base.py` 为原始代码，删除多余的导入和调用

**设计原理**：
```
base.py 的 __call__()
    ↓
add_running_task(session_id, node_name, is_stream)
    ↓  (task_utils.py 内部)
task_push_queue(task_id)
    ↓
push_to_session(task_id, "progress", {...})
```

---

## 五、SSE 流式输出验证

### 5.1 非流式查询测试

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Aolynk 网桥怎么恢复出厂设置？", "is_stream": false}'
```

**结果**：✅ 返回完整答案（含操作步骤 + 图片 URL）

### 5.2 SSE 流式查询测试

```bash
# 发起查询 + 立即连接 SSE
SESSION_ID=$(curl -s -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Aolynk 网桥怎么恢复出厂设置？", "is_stream": true}' | grep -o '"session_id":"[^"]*"' | cut -d'"' -f4)

curl -N http://localhost:8001/stream/$SESSION_ID
```

**SSE 事件流完整输出**：

| 事件类型 | 内容 | 说明 |
|---------|------|------|
| `ready` | `{}` | 连接建立 |
| `progress` ×14 | `done_list` / `running_list` | 7 个节点依次完成 |
| `delta` ×80+ | `{"delta": "根据"}` ... | LLM 逐字流式输出 |
| `final` | 完整答案 + 4 张图片 URL | 最终结果 |
| `progress` | `status: completed` | 任务完成 |

**结论**：✅ SSE 流式输出完全成功，7 个节点进度实时推送 + LLM 逐字输出 + 最终答案 + 图片 URL

---

## 六、本日成果小结

### 6.1 完成内容

✅ **web/api/ 目录结构**：对齐原始代码，创建 query_service.py + import_service.py

✅ **query_service.py**：5 个接口（/query、/stream、/history、/health）

✅ **非流式查询**：curl POST /query 返回完整答案

✅ **SSE 流式查询**：完整事件流 ready → progress → delta → final

✅ **3 个坑修复**：ModuleNotFoundError / ImportError / push_to_session 未定义

### 6.2 项目进度

- ✅ 导入流程：7 节点 + 主图（Day 04~05）
- ✅ 检索流程：7 节点 + 主图（Day 06~07）
- ✅ SSE 流式输出 + FastAPI Web 服务（Day 08）
- ⏳ 下一步：Day 09 对话历史完善 + Day 10 import_service.py + 全流程联调

### 6.3 技术要点

1. **FastAPI 模块运行**：用 `uv run python -m web.api.query_service` 而非直接运行脚本
2. **SSE 两阶段设计**：先 POST /query 获取 session_id，再 GET /stream/{session_id} 接收事件流
3. **进度推送设计**：不在 base.py 直接调用 push_to_session，而是通过 task_utils 内部自动完成
4. **BackgroundTasks**：FastAPI 后台任务机制，避免阻塞 HTTP 响应

---

## 七、明日计划

1. 对话历史完善（多轮对话上下文管理）
2. import_service.py 编写（导入流程 API）
3. 全流程联调（上传 PDF → 导入知识库 → 提问 → 流式回答）
