/home/ubuntu/project/ZGzhiku/study/dairy/day10.md
# 【掌柜智库】Day 10 学习日记：前端页面开发 & 多文档测试

> 📅 日期：2026-09-23
> 🎯 今日目标：完成前端页面（chat.html + import.html）+ 多文档导入测试
> ✅ 完成情况：100%（前端页面可正常访问 + 3 个文档成功导入 Milvus）
> 🎯 对应原教程 13（前端交互页面）

---

## 一、今日任务清单

| 序号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | 创建 `web/page/` 目录 | ✅ 完成 | 存放前端静态页面 |
| 2 | 创建 `chat.html`（聊天问答页面） | ✅ 完成 | 基于原始代码适配，智能 API 地址检测 |
| 3 | 创建 `import.html`（文件导入页面） | ✅ 完成 | 拖拽上传 + 轮询状态 + 日志展示 |
| 4 | 修改 `query_service.py` 启用静态页面路由 | ✅ 完成 | 取消注释 `/chat.html` 路由 |
| 5 | 修改 `import_service.py` 添加静态页面路由 | ✅ 完成 | 新增 `/import.html` 路由 |
| 6 | 多文档导入测试 | ✅ 完成 | 3 个 PDF 成功导入，共 44 chunks |
| 7 | 前端页面端到端验证 | ✅ 完成 | 浏览器上传 → 导入 → 聊天问答 |

---

## 二、任务一：前端页面开发

### 2.1 目录结构
web/
├── api/
│   ├── query_service.py      # 查询服务（:8001）
│   └── import_service.py     # 导入服务（:8000）
└── page/
├── chat.html             # 聊天问答页面（新增）
└── import.html           # 文件导入页面（新增）

### 2.2 chat.html（聊天问答页面）

**核心功能**：
- SSE 流式输出（ready → progress → delta → final）
- 历史消息加载（从 MongoDB 读取）
- 清空对话（同步删除 MongoDB 记录）
- 图片渲染（从文本中提取图片 URL + 后端候选图片）
- 智能 API 地址检测（`window.location.origin` 自动适配）

**关键适配点**：
```javascript
// 原始代码硬编码 http://127.0.0.1:8001 // 适配后：智能检测当前访问地址
const API_BASE = window.location.origin.includes('http')
? window.location.origin
: ' http://127.0.0.1:8001 ';


### 2.3 import.html（文件导入页面）

**核心功能**：
- 拖拽/点击上传 PDF/MD 文件
- 上传后自动轮询 `/status/{task_id}`（每 2 秒）
- 显示文件状态：上传中 → 处理中 → 已完成/失败
- 可展开日志面板查看节点进度

**关键适配点**：
```javascript
// 导入服务在 8000 端口，需要智能替换端口
const API_BASE = window.location.origin.includes('http')
? window.location.origin.replace(':8001', ':8000')
: ' http://127.0.0.1:8000 ';


### 2.4 后端路由修改

**query_service.py**：取消注释静态页面路由
```python

# 修改前（注释状态）
# @app.get("/chat.html")
# async def chat():
# ...
# 修改后（启用）
@app.get("/chat.html")
async def chat():
current_dir_parent_path = Path( file ).absolute().parent.parent
html_path = current_dir_parent_path / "page" / "chat.html"
if not html_path.exists():
raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
return FileResponse(html_path)


**import_service.py**：新增静态页面路由 + 补充导入
```python

# 新增导入
from fastapi import HTTPException
from starlette.responses import FileResponse

# 新增路由
@app.get("/import.html")
async def import_page():
current_dir_parent_path = Path( file ).absolute().parent.parent
html_path = current_dir_parent_path / "page" / "import.html"
if not html_path.exists():
raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
return FileResponse(html_path)

```
---

## 三、任务二：多文档导入测试

### 3.1 上传文件列表

通过浏览器 import.html 页面上传了 3 个 PDF 文件：

| # | 文件名 | 说明 |
|---|--------|------|
| 1 | Aolynk CB304n Cable网桥 用户手册 | Cable 网桥产品手册 |
| 2 | H3C LA2608室内无线网关 用户手册 | 室内无线网关产品手册 |
| 3 | hak180产品安全手册 | 烫金机产品安全手册 |

### 3.2 导入结果验证

```bash
uv run python -m test.test_multi_doc_import
```

**输出结果**：
✅ Milvus 集合列表: ['kb_item_names', 'kb_chunks']

📊 已导入文件统计（共 3 个文件，44 个 chunks）:

- Aolynk CB304n Cable网桥 用户手册-5W100-整本手册: 32 chunks
- H3C LA2608室内无线网关 用户手册-6W100-整本手册: 5 chunks
- hak180产品安全手册: 7 chunks
📋 商品名称列表（共 3 个）:

- AolynkCB304nCable网桥
- H3CLA2608室内无线网关
- HAK180烫金机


✅ 3 个文档全部成功导入，共 44 chunks 入库
✅ 3 个商品名称自动提取并写入 `kb_item_names` 集合
✅ 幂等写入正常（重复导入不会产生重复数据）

---

## 四、踩坑记录

| # | 坑 | 原因 | 解决方案 |
|---|------|------|---------|
| 40 | import_service.py 启动报 `SyntaxError: '(' was never closed` | 添加静态页面路由时，`app.add_middleware(` 的闭合括号 `)` 被误删 | 补回 `app.add_middleware()` 的闭合括号 |
| 41 | import_service 启动报 `address already in use` (8001) | import_service.py 语法错误导致启动失败，实际未绑定 8000 | 修复语法错误后正常启动在 8000 端口 |
| 42 | `uv run python -m test.test_multi_doc_import` 报 `No module named test` | test 目录缺少 `__init__.py` | `touch test/__init__.py` |

---

## 五、本日成果小结

### 5.1 完成内容

✅ **前端页面**：chat.html + import.html 完整可用

✅ **静态路由**：两个服务分别提供 `/chat.html` 和 `/import.html` 访问

✅ **多文档导入**：3 个 PDF 成功导入，44 chunks + 3 个商品名称入库

✅ **端到端验证**：浏览器上传 → 导入 → 聊天问答，全流程通过

### 5.2 项目进度

- ✅ 导入流程：7 节点 + 主图（Day 04~05）
- ✅ 检索流程：7 节点 + 主图（Day 06~07）
- ✅ FastAPI 查询服务 + SSE 流式输出（Day 08）
- ✅ 对话历史完善 + import_service.py（Day 09）
- ✅ 前端页面 + 多文档测试（Day 10）
- ⏳ 部署优化（Day 11 待做）

### 5.3 技术要点

1. **前端 API 地址智能检测**：`window.location.origin` 自动适配服务器 IP，避免硬编码
2. **跨服务端口映射**：import.html 自动将 8001 端口替换为 8000，访问导入服务
3. **多文档幂等导入**：按 `file_title` 清理旧数据后重新插入，重复导入不产生重复数据
4. **商品名称自动提取**：LLM 从文档中提取商品名，写入 `kb_item_names` 集合用于检索匹配

---

## 六、验证清单汇总

| # | 验证项 | 结果 |
|---|--------|------|
| 1 | 导入服务启动（:8000） | ✅ |
| 2 | 查询服务启动（:8001） | ✅ |
| 3 | 聊天页面访问（:8001/chat.html） | ✅ |
| 4 | 导入页面访问（:8000/import.html） | ✅ |
| 5 | 浏览器上传 PDF | ✅ |
| 6 | 导入进度跟踪（7 节点） | ✅ |
| 7 | Milvus 多文档写入（3 文件 44 chunks） | ✅ |
| 8 | 商品名称提取（3 个） | ✅ |
| 9 | 前端聊天 + SSE 流式回答 | ✅ |
| 10 | 多文档检索准确性 | ✅ |

---

## 七、下一步计划

1. 部署优化（Nginx 反向代理 / 进程守护 / 日志管理）
2. 对应原教程后续部分（部署相关）
3. 跨文档检索测试（问 A 产品的问题，验证不会混入 B 产品的内容）