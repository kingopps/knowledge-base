# 【掌柜智库】Day 05 学习日记：组装导入主图（LangGraph 编排节点1~7）

> 📅 日期：2026-09-21
> 🎯 今日目标：把节点1~7 用 LangGraph 编排成完整导入流水线，端到端跑通 PDF → Milvus
> 🏆 结果：✅ 7 节点全部 PASS，32 Chunks 入库，项目 30% 里程碑达成
> 📚 对应笔记：11【掌柜智库】

---

## 一、现状盘点：意外之喜

开工前先盘点 `code/knowledge_base/processor/import_processor/`，发现 **main_graph.py 已经存在**——之前某个阶段已从原始课程代码整体 copy 过来，图编排逻辑可以直接用：

- `KBImportWorkflow` 类：`graph` 惰性加载（首次访问才 compile）
- `build_graph()`：注册 7 个节点 + 1 条条件边 + 6 条顺序边
- `route_after_entry()`：根据 `md_path` 与 `is_pdf` 两个状态标志路由到 pdf / md / END
- `run()`：支持 invoke / stream 两种模式

对接检查全部通过：

| 检查项 | 结果 |
|--------|------|
| import 路径与现有节点匹配（含 node_enrty 拼写） | ✅ |
| state.py 的 ImportGraphState 含全部所需字段 | ✅ |
| pyproject.toml 已有 langgraph>=1.1.10 | ✅ |
| `__main__` 测试块 | ❌ Windows 路径 + 缺 task_id（踩坑20，KeyError 必现） |

## 二、图编排代码理解（重点）

LangGraph 的本质 = **共享字典（state）驱动的状态机**：

| API | 作用 | 本项目对应 |
|-----|------|-----------|
| `StateGraph(ImportGraphState)` | 声明图，状态类型即契约 | build_graph() |
| `add_node("名字", 节点实例)` | 注册节点，执行时调 `__call__` | 7 次 |
| `set_entry_point("node_entry")` | 入口 | |
| `add_conditional_edges(源, 路由函数, 映射)` | 按路由函数返回值选下一节点 | pdf / md / END 三条出路 |
| `add_edge(A, B)` | 无条件顺序边 | 6 条 |

三个机制级收获：

1. **惰性加载**：`graph` 是 `@property`，首次访问才 `compile()`，避免 import 时开销
2. **状态增量合并**：节点 `process()` 返回的 dict 只合并对应键进全局状态，所以每个节点可以只返回部分字段
3. **BaseNode.`__call__` = 切面**：LangGraph 调用 `节点(state)` → `__call__` 统一处理日志、任务追踪（add_running_task/add_done_task）、异常包装（ImportProcessError），业务代码只写 `process()`——模板方法模式

## 三、代码修改记录（main_graph.py，共 2 处）

1. 文件顶部补 `import json`
2. `__main__` 测试块重写：补 `task_id`（踩坑20）、Windows 路径 → Linux 真实路径、`final_state` 直接打印 → `json.dumps` 精简摘要

精简输出的原因：final_state 含 32 个 chunk，每个带 1024 维 dense 向量 + sparse 向量，直接打印会刷屏上万行。

完整代码与运行命令见复现指南 **6.6 节**。

## 四、第一次运行：被中断，但很有学习价值

现象：跑约 1.5 分钟后，看到 node_md_img 反复打印 `请求被限速，等待47.09秒...`，误以为卡死，Ctrl+C 中断。

复盘：三个现象全部正常——

1. **30 条 `图片xxx未在 MD 文档中找到` WARNING**：MinerU 的 images/ 目录含全部切图（约 60 张），MD 正文只引用其中一部分（约 30 张；页眉/装饰图/重复切图不引用）。节点3 跳过未引用图片，符合 Day 04 单测预期
2. **限速 sleep**：qwen3-vl-flash 限速 15 次/分钟，节点3 内置滑动窗口限流器自动 `time.sleep()`。日志中 `当前60s窗口内请求次数为15` 是硬证据。约 30 张图 × 2s/张 + 限速等待 ≈ 3~5 分钟
3. **中断有无危害：零副作用**
   - 中断点在 `_step_3_generate_summaries`（VLM 摘要阶段），MinIO 上传与 `_new.md` 写入尚未开始
   - `KeyboardInterrupt` 继承自 `BaseException` 而非 `Exception`，不会被 `BaseNode.__call__` 的 `except Exception` 包装成 ImportProcessError，进程干净退出
   - 即使某节点写了部分数据，节点7 按 file_title 幂等清理（先删后插）保证最终一致

💡 教训：**判断"卡死"前先看节点内置限速日志**，限速等待是保护机制在工作。

## 五、第二次运行：完整成功 🎉

```text
21:15:45  node_document_split 完成：32 Chunks（chunks.json 备份成功）
21:15:46  node_item_name_recognition 完成：识别 AolynkCB304nCable网桥
21:15:51  node_bge_embedding 完成（32 chunks 双向量，5 秒）
21:15:51  node_import_milvus 完成（幂等清理 + 插入）
最终 JSON 摘要：
{
"file_title": "Aolynk CB304n Cable网桥 用户手册-5W100-整本手册",
"item_name": "AolynkCB304nCable网桥",
"chunks_count": 32,
"first_chunk_has_dense": true,
"first_chunk_has_sparse": true
}
```

运行命令：

```bash
cd ~/project/ZGzhiku/code/knowledge_base
uv run python -m processor.import_processor.main_graph
```

两个细节：

- **chunks_count=32 ≠ 之前单测的 33**：节点3 的 VLM 图片摘要写入 MD 后正文变化 → 标题层级与段落长度变化 → 三层切分结果随之变化。**Chunk 数不是固定值**，由内容 + 切分参数共同决定
- **item_name 被去空格**：LLM 识别为 `AolynkCB304nCable网桥`（无空格），节点5 兜底时才用完整文件名，均正常

## 六、验证插曲：row_count 33 vs 实际 32

跑完后 `get_collection_stats()` 显示 kb_chunks 为 33 条，但本轮插入 32 条。

**原理：row_count 是统计快照，不是实时存活行**——已删行在 compaction（后台压缩合并）前仍被计入；新插入行在 growing segment 可能未被计入；统计本身有缓存延迟。检索真正生效的是查询结果。

真实判据用 query 拉实际行，并用 item_name 新旧值区分新旧数据（旧单测数据 item_name 为带空格完整文件名，新数据为 LLM 识别的无空格值）：

```bash

cd ~/project/ZGzhiku/code/knowledge_base && uv run python -c "
from collections import Counter
from utils.milvus_utils import get_milvus_client
client = get_milvus_client()
rows = client.query(collection_name='kb_chunks', filter='chunk_id >= 0',
output_fields=['chunk_id', 'item_name', 'file_title'], limit=200)
print('实际存活行数:', len(rows))
print('item_name 分布:', dict(Counter(r['item_name'] for r in rows)))
"
```

判读：情况 A（32 条、全是新 item_name）→ 数据正确，仅统计滞后；情况 B（33 条含 1 条旧 item_name）→ 有漏删，按 file_title/item_name 手动清理。

## 七、收获清单

| # | 收获 |
|---|------|
| 1 | "能 copy 直接 copy"再次生效：主图编排逻辑从原始代码零改动，只适配测试块 |
| 2 | LangGraph 状态机编排三件套：注册节点实例 + 条件边路由 + 状态增量合并 |
| 3 | API 限速是常态：限流等待要内建到节点里，学会读限速日志再判断卡死 |
| 4 | row_count ≠ 实时存活行，验收用 query 不用 stats |
| 5 | KeyboardInterrupt 非 Exception，不走 BaseNode 异常包装；流水线重跑靠幂等兜底 |

## 八、下一步（Day 06~07）

检索链路 7 节点（对应笔记12~18），原始代码在 `study/original_code/processor/query_processor/`：

- 向量检索 / HyDE 检索：**大改**（本地 BGE-M3 → DashScope text-embedding-v4 API + Milvus 混合检索）
- Rerank：**大改**（本地 BGE-Reranker → gte-rerank API）
- RRF 融合 / 答案生成 / 商品名确认：基本直接 copy 微调