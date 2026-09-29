/home/ubuntu/project/ZGzhiku/study/dairy/day09.md
# 【掌柜智库】Day 09 学习日记：对话历史完善（多轮对话验证）与 import_service.py 编写

> 📅 日期：2026-09-23
> 🎯 今日目标：对话历史完善（多轮对话上下文管理）+ import_service.py 编写（导入流程 API），上传 PDF → 导入知识库 → 提问 → 流式回答，端到端完整验证
> ✅ 完成情况：100%（对话历史验证通过 + import_service.py 3 接口完整可用）
> 🎯 对应原教程 13（检索 Web 服务端搭建）
---

## 一、今日任务清单

| 序号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | 修复 node_answer_output.py 中 `seld` → `self` 拼写错误 | ✅ 完成 | 导致助手答案无法写入 MongoDB |
| 2 | 多轮对话端到端验证 | ✅ 完成 | 两轮对话，"它"被正确改写为产品名 |
| 3 | MongoDB 历史记录完整性验证 | ✅ 完成 | 4 条记录（2 轮 user + 2 轮 assistant）全部正确存储 |
| 4 | import_service.py 编写 | ✅ 完成 | 3 个接口：/upload、/status/{task_id}、/health |
| 5 | .env 添加 DATA_BASED_ROOT_DIR 配置 | ✅ 完成 | 导入文件本地存储根目录 |
| 6 | 导入服务启动 + 健康检查 | ✅ 完成 | 端口 8000，/health 返回 {"ok": true} |
| 7 | 文件上传 + 导入流程测试 | ✅ 完成 | PDF 上传 → 本地保存 → MinIO 备份 → 后台 LangGraph 任务 |

---

## 二、任务一：对话历史完善

### 2.1 Bug 修复：`seld` → `self`

**现象**：MongoDB 中只有 user 消息，没有 assistant 消息

**原因**：`node_answer_output.py` 第 320 行 `_step_4_write_history` 方法的第一个参数写成了 `seld`（typo），导致调用时抛出 TypeError，外层 try/except 捕获了异常但助手答案未写入 MongoDB

**修复**：
```python
# 修复前
def _step_4_write_history(seld, state: QueryGraphState, image_urls=None) -> QueryGraphState:

# 修复后
def _step_4_write_history(self, state: QueryGraphState, image_urls=None) -> QueryGraphState:
```

### 2.2 多轮对话数据流分析

```
用户第1轮："Aolynk CB304n 网桥怎么恢复出厂设置？"
    │
    ▼
node_item_name_confirm:
    ① get_recent_messages() → 首轮为空
    ② save_chat_message(role="user") → 保存用户问题
    ③ LLM 提取商品名 → ["AolynkCB304nCable网桥"]
    ④ Milvus 匹配 → 确认商品名
    ⑤ _step_8_write_history → 更新用户消息 + 写助手答案
    │
    ▼（三路并行搜索 → RRF → Rerank）
    │
node_answer_output:
    ① 构建 Prompt（含 history 上下文）
    ② LLM 生成答案（含图片 URL）
    ③ save_chat_message(role="assistant") → 保存助手回复 ✅
    │
    ▼
用户第2轮："那它的指示灯怎么解读？"
    │
    ▼
node_item_name_confirm:
    ① get_recent_messages() → 读到第1轮 user + assistant
    ③ LLM 结合历史理解"它" → rewritten_query = "Aolynk CB304n 网桥的指示灯怎么解读？"
```

### 2.3 验证结果

**第一轮提问**：
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Aolynk CB304n 网桥怎么恢复出厂设置？", "is_stream": false}'
```
✅ 返回完整答案 + 图片 URL

**第二轮提问**（用代词"它"）：
```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "那它的指示灯怎么解读？", "session_id": "370eb16b-...", "is_stream": false}'
```
✅ 返回完整答案，rewritten_query 自动改写为 "Aolynk CB304n 网桥的指示灯怎么解读？"

**MongoDB 历史记录**（4 条记录完整）：
```bash
curl http://localhost:8001/history/370eb16b-5269-4041-9ef8-9587f4ef7d2b | python3 -m json.tool
```
✅ 2 轮 user + 2 轮 assistant，含 rewritten_query / item_names / image_urls 全部正确

---

## 三、任务二：import_service.py 编写

### 3.1 接口清单

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/upload` | 文件上传（支持多文件） |
| GET | `/status/{task_id}` | 任务进度查询 |
| GET | `/health` | 健康检查 |

### 3.2 核心设计

**上传接口 9 步流程**：
```
① 接收文件 → ② 按日期/任务ID创建本地目录 → ③ 保存文件到本地
→ ④ 上传至 MinIO（持久化备份）→ ⑤ 标记上传完成
→ ⑥ 启动后台 LangGraph 任务（BackgroundTasks）
→ ⑦ KBImportWorkflow.run(stream=True) → ⑧ 每完成一个节点 add_done_task()
→ ⑨ 全部完成 update_task_status("completed")
```

**状态查询接口**：
```json
{
    "code": 200,
    "task_id": "xxx",
    "status": "processing",
    "done_list": ["开始上传文件", "检查文件", "PDF转Markdown"],
    "running_list": ["文档切分"]
}
```

### 3.3 .env 配置

```bash
DATA_BASED_ROOT_DIR=/home/ubuntu/project/ZGzhiku/code/knowledge_base/output/import
```

### 3.4 验证结果

**启动服务**（端口 8000）：
```bash
uv run python -m web.api.import_service
```
✅ Application startup complete

**健康检查**：
```bash
curl http://localhost:8000/health
```
✅ 返回 `{"ok": true}`

**文件上传**：
```bash
curl -X POST http://localhost:8000/upload \
  -F "files=@doc/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.pdf"
```
✅ 返回 task_ids，后台 LangGraph 任务启动

**进度查询**：
```bash
curl http://localhost:8000/status/{task_id}
```
✅ 返回 status + done_list + running_list

---

## 四、踩坑记录

### 坑 43：`seld` → `self` 拼写错误导致助手答案未写入 MongoDB

**现象**：MongoDB 中只有 user 消息，assistant 消息缺失

**原因**：`node_answer_output.py` 第 320 行 `_step_4_write_history(seld, ...)` 参数名拼写错误

**解决方案**：`seld` → `self`

**教训**：外层 try/except 吞掉了异常，导致 bug 不易发现。日志中应该有 `TypeError` 记录但被忽略了。

### 坑 44：curl 上传文件路径错误

**现象**：`curl: (26) Failed to open/read local data from file/application`

**原因**：文件名有空格（`Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.pdf`），且路径不对

**解决方案**：用正确的文件名（含空格），curl 的 `@` 后直接跟含空格的文件名即可

### 坑 45：访问 localhost:8000 返回 404

**现象**：浏览器访问 `http://localhost:8000/` 显示 `{"detail":"Not Found"}`

**原因**：没有定义根路径 `/` 的路由，这是正常行为

**解决方案**：访问 `http://服务器IP:8000/docs` 查看 Swagger 自动文档

---

## 五、全流程联调（2026-09-23 完成）

### 5.1 环境确认

| 检查项 | 结果 |
|--------|------|
| Docker 容器（6 个） | ✅ 全部 Up 2 weeks |
| 端口 8000/8001 | ✅ 空闲，无旧服务占用 |
| 测试 PDF | ✅ 3 个文件（Aolynk CB304n / CC系列 / CS2610DNW） |
| Milvus 初始数据 | kb_chunks: 64 条，kb_item_names: 2 条 |

### 5.2 启动双服务

```bash
# 终端 1：导入服务（端口 8000）
uv run python -m web.api.import_service

# 终端 2：查询服务（端口 8001）
uv run python -m web.api.query_service

# 健康检查
curl http://localhost:8000/health  # {"ok": true}
curl http://localhost:8001/health  # {"ok": true}
```

### 5.3 上传 PDF → 导入知识库

```bash
# 上传文件
curl -X POST http://localhost:8000/upload \
  -F "files=@doc/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.pdf"
# 返回 task_ids: ["67ed8dd4-c2c1-46bf-a3dc-570fc907c703"]

# 轮询进度（每 5 秒一次）
curl http://localhost:8000/status/67ed8dd4-c2c1-46bf-a3dc-570fc907c703 | python3 -m json.tool
```

**导入进度 7 节点全部完成**：
```
✅ 开始上传文件 → ✅ 检查文件 → ✅ PDF转Markdown → ✅ Markdown图片处理
→ ✅ 文档切分 → ✅ 主体名称识别 → ✅ 向量生成 → ✅ 导入向量库
status: "completed"
```

### 6.4 Milvus 幂等写入验证

| 集合 | 上传前 | 上传后 | 结论 |
|------|--------|--------|------|
| kb_chunks | 64 | **64** | ✅ 不变，幂等去重正确 |
| kb_item_names | 2 | **2** | ✅ 不变，同一 PDF 不重复插入 |

### 6.5 非流式查询

```bash
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Aolynk CB304n 网桥怎么恢复出厂设置？", "is_stream": false}'
```
✅ 返回完整答案（Web 管理页面 → 管理 → 设备管理 → 恢复出厂设置）+ 图片 URL

### 6.6 SSE 流式查询（核心验证）

```bash
# 第一步：发起流式查询
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Aolynk CB304n 的指示灯怎么解读？", "is_stream": true}'
# 返回 session_id: "012d5606-63f6-497c-90ee-5a9959ba5574"

# 第二步：连接 SSE 流
curl -N http://localhost:8001/stream/012d5606-63f6-497c-90ee-5a9959ba5574
```

**SSE 事件流完整链路**：
```
event: ready          ← 连接建立
event: progress ×14   ← 7 个节点逐一完成（确认问题产品 → 三路并行搜索 → 倒排融合 → 重排序 → 生成答案）
event: delta ×80+     ← LLM 流式增量输出（"A" → "ol" → "yn" → "k CB304n 的指示灯..."）
event: final          ← 完整答案 + image_urls
event: progress       ← status: "completed"
```

✅ 答案准确描述了 4 个指示灯（Cable / POWER / LAN / WLAN），内容来自上传的 PDF 手册

### 6.7 多轮对话验证

```bash
# 用代词"它"追问
curl -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"query": "那它的默认登录密码是什么？", "session_id": "012d5606-63f6-497c-90ee-5a9959ba5574", "is_stream": false}'
```
✅ `rewritten_query`: "**Aolynk CB304n** 的默认登录密码是什么？"（"它"被正确改写）
✅ 答案：默认密码 admin，含登录步骤

### 6.8 MongoDB 历史记录

```bash
curl http://localhost:8001/history/012d5606-63f6-497c-90ee-5a9959ba5574 | python3 -m json.tool
```
✅ 4 条记录完整（2 轮 user + 2 轮 assistant），含 rewritten_query / item_names / image_urls


## 五、本日成果小结

### 5.1 完成内容

✅ **Bug 修复**：`seld` → `self`，助手答案成功写入 MongoDB

✅ **多轮对话验证**：两轮对话端到端测试通过，上下文管理正确工作

✅ **import_service.py**：3 个接口（/upload、/status、/health）完整可用

✅ **两个服务并行运行**：import_service（8000）+ query_service（8001）

### 5.2 项目进度

- ✅ 导入流程：7 节点 + 主图（Day 04~05）
- ✅ 检索流程：7 节点 + 主图（Day 06~07）
- ✅ FastAPI 查询服务 + SSE 流式输出（Day 08）
- ✅ 对话历史完善 + import_service.py（Day 09）
- ✅ **全流程联调**：上传 PDF → 导入 → 提问 → 流式回答，端到端验证通过

### 5.3 技术要点

1. **多轮对话核心**：第二轮提问时，LLM 通过 history 理解代词（"它"），自动改写为完整问题（rewritten_query）
2. **import_service 设计**：上传 → 本地保存 → MinIO 备份 → 后台 LangGraph 任务，前端通过轮询 /status 获取进度
3. **两个独立 FastAPI 服务**：import_service（8000）和 query_service（8001）各自独立运行
4. **Swagger 文档**：FastAPI 自动生成 `/docs`（Swagger UI）和 `/redoc`（ReDoc）

---

---
### 6.9 验证清单汇总

| # | 验证项 | 结果 |
|---|--------|------|
| 1 | 中间件运行（6 容器） | ✅ |
| 2 | 导入服务启动（:8000） | ✅ |
| 3 | 查询服务启动（:8001） | ✅ |
| 4 | PDF 上传 | ✅ |
| 5 | 导入进度跟踪（7 节点） | ✅ |
| 6 | Milvus 幂等写入 | ✅ |
| 7 | 非流式查询 | ✅ |
| 8 | SSE 流式查询（ready→progress→delta→final） | ✅ |
| 9 | 多轮对话（代词改写） | ✅ |
| 10 | MongoDB 历史记录 | ✅ |

---

## 七、下一步计划

1. 前端页面开发（chat.html + import.html）
2. 对应原教程 13 后半部分（前端交互）
3. 多文档测试（CC系列集中器 / CS2610DNW）
