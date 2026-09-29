/home/ubuntu/project/ZGzhiku/study/dairy/day07.md
# 【掌柜智库】Day 07 学习日记：检索流程节点测试与端到端验证

> 📅 日期：2026-09-23
> 🎯 今日目标：完成检索流程剩余 4 个节点测试 + 主图端到端验证
> ✅ 完成情况：100%（7 个节点全部通过 + 端到端成功）

---

## 一、今日任务清单

| 序号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 1 | node_item_name_confirm 节点测试 | ✅ 完成 | 商品名提取 + Milvus 匹配 |
| 2 | node_rrf 节点测试 | ✅ 完成 | RRF 融合排序算法验证 |
| 3 | node_rerank 节点测试 | ✅ 完成 | 踩坑：gte-rerank 已下线 |
| 4 | node_answer_output 节点测试 | ✅ 完成 | LLM 答案生成 + 图片提取 |
| 5 | main_graph 端到端测试 | ✅ 完成 | 7 节点串联成功 |

---

## 二、node_item_name_confirm 测试

### 2.1 测试命令

```bash
cd ~/project/ZGzhiku/code/knowledge_base
uv run python -m processor.query_processor.nodes.node_item_name_confirm
```

### 2.2 测试结果

**测试数据**：`original_query = "怎么调节转印温度？"`

**关键日志**：
- MongoDB 连接成功，读取历史记录
- LLM 调用成功（HTTP 200，耗时 284ms）
- 未提取到商品名（问题中没有明确商品名）
- 走分支C（拒识）：返回 "未找到相关产品，请提供准确的商品品牌、型号和名称。"

**结论**：✅ 通过，三路分支逻辑正常（确认/反问/拒识）

---

## 三、node_rrf 测试

### 3.1 测试命令

```bash
uv run python -m processor.query_processor.nodes.node_rrf   
```

### 3.2 测试结果

**Mock 数据**：
- 向量检索：chunk_1, chunk_2, chunk_3
- HyDE 检索：chunk_1, chunk_4, chunk_2

**RRF 融合结果**：

| 排名 | chunk_id | 出现位置 | 说明 |
|------|----------|---------|------|
| 1 | chunk_1 | 向量#1 + HyDE#1 | 两路都出现，分数累加 |
| 2 | chunk_2 | 向量#2 + HyDE#3 | 两路都出现，分数累加 |
| 3 | chunk_4 | 仅 HyDE#2 | 只出现一次 |
| 4 | chunk_3 | 仅向量#3 | 只出现一次 |

**结论**：✅ 通过，RRF 算法正确——多路重复出现的文档排名更高

---

## 四、node_rerank 测试（踩坑记录）

### 4.1 首次测试失败

**测试命令**：

```bash
uv run python -m processor.query_processor.nodes.node_rerank
```

**报错信息**：
RuntimeError: DashScope qwen3 rerank API 调用失败: 403, 响应消息：Access denied.


**根因分析**：
- `.env` 中配置 `RERANK_MODEL=gte-rerank`
- DashScope 已下线 `gte-rerank` 模型，返回 403 权限拒绝

### 4.2 修复方案

**修改 `.env`**：

```ini
# 原配置
RERANK_MODEL=gte-rerank

# 修改为
RERANK_MODEL=gte-rerank-v2
```

### 4.3 修复后测试结果

**API 响应**（HTTP 200）：

| 文档 | 内容摘要 | 相关性分数 | 说明 |
|------|---------|-----------|------|
| 文档1 | "主板短路通常表现为..." | **0.878** | 高度相关 |
| 文档3 | "主板通电前先打各主供电..." | 0.492 | 中度相关 |
| 文档2 | "今天中午去吃猪脚饭..." | 0.173 | 无关 |
| 文档4 | "苹果发布新款手机..." | **0.006** | 完全无关 |

**断崖检测**：保留前 2 条（0.878 + 0.492），截断后 2 条

**结论**：✅ 通过，gte-rerank-v2 精排打分 + 断崖检测截断正常

---

## 五、node_answer_output 测试

### 5.1 测试命令

```bash
uv run python -m processor.query_processor.nodes.node_answer_output
```

### 5.2 测试结果

**Mock 数据**：HAK 180 烫金机操作问题 + 3 条模拟文档（含 Markdown 图片）

**关键日志**：
- Prompt 组装成功（参考内容 + 历史对话 + 商品名 + 问题）
- LLM 生成答案（HTTP 200，耗时约 4 秒，710 字符）
- 图片提取：从 3 个文档中提取了 3 张唯一图片 URL
  - 文档[0] 正文发现 2 张 Markdown 图片
  - 文档[1] 字段发现 1 张图片 URL
- MongoDB 历史记录写入成功

**结论**：✅ 通过，答案生成 + 图片提取 + 历史写入正常

**备注**：`_step_4_write_history` 方法参数名 `seld` 应为 `self`，但不影响运行（Python 中 self 只是约定俗成的参数名）

---

## 六、main_graph 端到端测试

### 6.1 测试前修改

**修改 `__main__` 测试块**：

```python
init_state = {
"session_id": "test_query_001",
"original_query": "Aolynk CB304n 网桥怎么恢复出厂设置？",
"is_stream": False  # 新增
}


### 6.2 测试命令

```bash
uv run python -m processor.query_processor.main_graph
```

### 6.3 测试结果

**执行流程**：

node_item_name_confirm  → ✅ 确认商品名 Aolynk
node_search_embedding   → ✅ 向量检索
node_search_embedding_hyde → ✅ HyDE 检索
node_web_search_mcp     → ✅ 网络搜索
node_rrf                → ✅ RRF 融合排序
node_rerank             → ✅ gte-rerank-v2 重排
node_answer_output      → ✅ LLM 生成答案


**最终输出**：成功生成 Aolynk 网桥恢复出厂设置的答案

**结论**：✅ 通过，7 节点串联成功，检索流程完整链路验证通过

---

## 七、踩坑总结

### 坑 38：gte-rerank 模型已下线

**现象**：
RuntimeError: DashScope qwen3 rerank API 调用失败: 403, 响应消息：Access denied.


**原因**：DashScope 已下线 `gte-rerank` 模型

**解决方案**：`.env` 中 `RERANK_MODEL=gte-rerank` 改为 `RERANK_MODEL=gte-rerank-v2`

### 坑 39：main_graph 缺 is_stream 字段

**现象**：节点内部 `state.get("is_stream")` 返回 None

**原因**：`__main__` 测试块未设置 `is_stream` 字段

**解决方案**：`init_state` 补 `"is_stream": False`

---

## 八、本日成果小结

### 8.1 完成内容

✅ **node_item_name_confirm**：LLM 提取商品名 + Milvus 匹配 + 三路分支（确认/反问/拒识）

✅ **node_rrf**：RRF 融合排序算法验证通过，多路重复文档排名更高

✅ **node_rerank**：gte-rerank-v2 精排打分 + 断崖检测截断

✅ **node_answer_output**：Prompt 组装 + LLM 答案生成 + 图片提取 + MongoDB 写入

✅ **main_graph 端到端**：7 节点串联，Aolynk 网桥问题成功生成答案

### 8.2 项目进度

**至此，检索流程全部 7 个节点 + 主图编排全部验证通过！**

- ✅ 导入流程：7 节点 + 主图（Day 04~05）
- ✅ 检索流程：7 节点 + 主图（Day 06~07）
- ⏳ 下一步：Day 08~09 SSE 流式输出 + 对话历史完善 → Day 10 FastAPI Web 服务 + 全流程联调

### 8.3 技术要点

1. **RRF 算法**：`分数 = 权重 / (k + 排名)`，多路重复出现的文档分数累加，排名更高
2. **断崖检测**：相邻分数差距超过阈值时截断，避免低质量文档影响答案
3. **模型版本**：DashScope 模型会迭代更新，需关注官方公告（gte-rerank → gte-rerank-v2）

---

## 九、明日计划

1. SSE 流式输出实现（让答案像 ChatGPT 一样逐字输出）
2. 对话历史完善（多轮对话上下文管理）
3. FastAPI Web 服务框架搭建


