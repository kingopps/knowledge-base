# 掌柜智库项目(RAG)实战

## 9. 检索数据节点实现与测试

### 9.6 Rerank重排序(node_rerank)

#### 节点作用

该节点使用 Reranker 模型对 RRF 融合结果和网络搜索结果进行精排，并通过断崖检测算法实现动态 TopK 截断。

#### 步骤分解

1）把 RRF 得到的切片集合和MCP搜索结果进行合并

2）利用 Reranker 模型对文档进行打分、重排

3）根据相关性性评分，用动态 TopK 算法进行截取。

**动态TopK**：与固定的 TopN 排名最大的区别就是不会定死录取名次。而是通过一个分数断崖落差把好差区分，选择优势明显的前 N 名。比如前 5 名分别为 95、93、89、77、71。明显前三名断崖领先后两名所以就只取前三名，避免低分文档混入候选。



#### 重排序介绍

##### 为什么需要重排序？

RRF 融合虽然合并了多路检索结果，但存在局限性：

<img src="images/为什么需要Rerank.jpg" style="zoom:67%;" />

##### 重排序的作用

- 使用专门的相关性模型进行精排
- 统一评估所有来源的文档（本地 + 网络）
- 过滤低质量文档，提高答案生成质量



#### 代码实现

##### 单元测试

```python
if __name__ == "__main__":

    logger.info("开始测试: 重排序节点 (RerankNode)")

    mock_state = {
        "rewritten_query": "怎么测这块主板的短路问题？",
        "rrf_chunks": [
            {"chunk_id": "local_1", "title": "主板维修手册",
             "content": "主板短路通常表现为通电后风扇转一下就停，可以使用万用表的蜂鸣档测量。"},
            {"chunk_id": "local_2", "title": "闲聊",
             "content": "今天中午去吃猪脚饭吧，这块主板外观很漂亮。"},
        ],
        "web_search_docs": [
            {"url": "https://example.com/repair", "title": "短路查修指南",
             "snippet": "主板通电前先打各主供电电感对地阻值，阻值偏低就是短路。"},
            {"url": "https://example.com/news", "title": "科技新闻",
             "snippet": "苹果发布新款手机，A系列芯片性能提升20%。"},
        ],
    }

    logger.info("【输入状态】:")
    logger.info(f"  查询: {mock_state['rewritten_query']}")
    logger.info(f"  本地文档: {len(mock_state['rrf_chunks'])} 篇")
    logger.info(f"  网络文档: {len(mock_state['web_search_docs'])} 篇")

    node_rerank = NodeRerank()
    result = node_rerank(mock_state)

    logger.info("【重排序结果】:")
    for i, doc in enumerate(result["reranked_docs"], 1):
        score = doc.get('score')
        score_str = f"{score:.4f}" if score is not None else "N/A"
        logger.info(f"[{i}] score={score_str} | {doc['source']:5} | {doc['content'][:50]}...")

    logger.info("测试完成")
```

 ##### 主流程定义

```python
from typing import List, Dict, Any

from app.lm.reranker_http_utils import rerank_documents
from app.query_process.agent.node_base import NodeBase
from app.core.logger import logger
from app.query_process.agent.state import QueryGraphState


# -----------------------------
# Rerank / TopK 全局常量
# -----------------------------
# 动态 TopK 硬上限：最多取前 N 条（<=10）
RERANK_MAX_TOPK: int = 10
# 最小 TopK：至少保留前 N 条（>=1，且 <= RERANK_MAX_TOPK）
RERANK_MIN_TOPK: int = 3 #总数最少条数

# 断崖阈值（绝对，判断高分文档）
RERANK_GAP_ABS: float = 0.5
# 断崖阈值（相对，判断低分文档）
RERANK_GAP_RATIO: float = 0.25


class NodeRerank(NodeBase):
    """
    节点功能：使用 Cross-Encoder 模型对 RRF 后的结果进行精确打分重排。
    流程: 合并多源文档 → Reranker 计算相关性 → 断崖检测动态截断
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_rerank"

    def process(self, state: QueryGraphState) -> QueryGraphState:

        """
        执行重排序
        :param state: 需包含 rrf_chunks、web_search_docs、rewritten_query
        :return: 更新后的 state，包含 reranked_docs
        """

        # 1. 获取 query
        user_query = state.get('rewritten_query', '') or state.get('original_query', '')

        # 2. 合并多源文档
        merged_multi_docs: List[Dict[str, Any]] = self._merge_multi_source_docs(state)

        # 3. Rerank 精排(精排打分)
        reranked_docs: List[Dict[str, Any]] = self._rerank_merged_docs(user_query, merged_multi_docs)

        # 4. 动态 Top_K 截取(断崖检测)
        cutoff_docs = self._cliff_cutoff(reranked_docs)

        state['reranked_docs'] = cutoff_docs

        return state
```

##### 合并RFF和网搜文档 

```python
    def _merge_multi_source_docs(self, state: QueryGraphState) -> List[Dict[str, Any]]:
        """合并本地 RRF 结果和网络搜索结果为统一格式"""

        final_docs = []

        # 1. 获取本地 RRF 的文档
        for rrf_doc in (state.get('rrf_chunks') or []):

            if not isinstance(rrf_doc, dict):
                continue

            format_rrf_doc = {
                "content": rrf_doc.get('content'),
                "title": rrf_doc.get('title'),
                "chunk_id": rrf_doc.get('chunk_id'),
                "url": "",
                "source": "local"
            }
            final_docs.append(format_rrf_doc)

        # 2. 获取 web 远程的文档
        for web_doc in (state.get('web_search_docs') or []):
            if not isinstance(web_doc, dict):
                continue

            format_web_doc = {
                "content": web_doc.get('snippet'),
                "title": web_doc.get('title'),
                "chunk_id": None,
                "url": web_doc.get('url'),
                "source": "web"
            }
            final_docs.append(format_web_doc)

        logger.info(f"收集到准备进行 Rerank 精排的文档 {len(final_docs)}")

        return final_docs
```

##### 配置Rerank模型

安装 dashscope 的 sdk

```bash
uv add dashscope
```

在`.env`文件，添加以下配置：

```ini
# ===================== 重排序模型配置 =====================
TEXT_RERANK_MODEL=qwen3-rerank
TEXT_RERANK_INSTRUCT=针对给定的查询，检索能够解答该查询的相关段落
```

加载配置参数：`app/conf/reranker_config.py`

定义工具方法：`app/lm/reranker_http_utils.py`

##### Reranker 计算得分

```python
    def _rerank_merged_docs(self, user_query: str, merged_multi_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """使用 Reranker 模型对文档进行精排"""
        if not merged_multi_docs:
            return []


        try:

            contents = [doc.get("content") for doc in merged_multi_docs]
            rerank_scores = rerank_documents(user_query, contents)

            scored_docs = [{**doc, "score": score} for doc, score in zip(merged_multi_docs, rerank_scores)]
            # 等同如下写法
            # scored_docs = []
            # for doc, score in zip(merged_multi_docs, rerank_scores):
            #     scored_docs.append({
            #         "content": doc.get("content"),
            #         "title": doc.get("title"),
            #         "chunk_id": doc.get("chunk_id"),
            #         "url": doc.get("url"),
            #         "source": doc.get("source"),
            #         "score": float(score),
            #     })


            sorted_score_docs = sorted(
                scored_docs,
                key=lambda x: x["score"],
                reverse=True
            )

            return sorted_score_docs

        except Exception as e:
            logger.error(f"Rerank 重排序失败: {str(e)}")
            return [{**merged_multi_docs, "score": None}]
```

##### 断崖检测算法

重排序后需要决定保留多少文档。传统做法是固定 TopK，但这不够灵活：

> 固定 TopK=5 的问题：
>
> - 情况 1：前 3 篇高度相关，后 2 篇噪声
>
>   得分: [0.95, 0.92, 0.88, 0.12, 0.08]
>
>   ​                                  ↑
>
>   ​                        应该在这里截断
>
> - 情况 2：前 7 篇都相关
>
>   得分: [0.95, 0.91, 0.87, 0.83, 0.79, 0.75, 0.71]
>
>   ​                                                   ↑
>
>   ​                                  固定截断会丢失有价值内容

**断崖检测的思路：** 寻找得分"断崖式下跌"的位置，在那里截断。

> 断崖检测示例：
>
> 得分: [0.95, 0.92, 0.88, 0.12, 0.08]
> 差值:      0.03   0.04   0.76   0.04
>                                          ↑
>                                 断崖！在此截断
>
> 结果: 保留前 3 篇

**为什么需要两个阈值？**

> 场景 1：高分区间断崖
>
> -   得分: [0.95, 0.92, 0.40, ...]
> -   abs_gap = 0.52 > gap_abs=0.5  ✓ 触发截断
>
> 场景 2：低分区间断崖
>
> -   得分: [0.30, 0.28, 0.08, ...]
> -   abs_gap = 0.20 < gap_abs=0.5  ✗
> -   rel_gap = 0.20/0.28 = 0.71 > gap_ratio=0.25  ✓ 触发截断

**断崖检测公式：**

```python
# 相邻得分差
abs_gap = current_score - next_score

# 相对下降比例
rel_gap = abs_gap / (abs(current_score) + 1e-6)

# 满足任一条件即为断崖
if abs_gap >= gap_abs or rel_gap >= gap_ratio:
    cutoff_pos = i + 1
```

参数说明：

- `gap_abs`：绝对差值阈值（默认 0.5）
- `gap_ratio`：相对比例阈值（默认 0.25）
- `min_top_k`：最少保留数量（默认 3）
- `max_top_k`：最多保留数量（默认 10）

##### 断崖检测动态截断

```python
    def _cliff_cutoff(self, ranked_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """断崖检测截断：相邻得分差距超过阈值时截断。"""
        if not ranked_docs:
            return []

        upper_bound = min(RERANK_MAX_TOPK, len(ranked_docs))
        lower_bound = min(RERANK_MIN_TOPK, upper_bound)

        # 默认值：取满硬上限（最多10条）
        cutoff_pos = upper_bound

        # 遍历范围：从min_topk-1到max_topk-2（索引从0开始），检测相邻两个文档的分数差
        # 例：min_topk=3，max_topk=10 → 遍历i=2,3,4,5,6,7,8（对应第3~9条文档，检测与下一条的差距）
        for idx in range(lower_bound - 1, upper_bound - 1):
            current_score = ranked_docs[idx].get("score")
            next_score = ranked_docs[idx + 1].get("score")

            if current_score is None or next_score is None:
                continue

            # 计算相邻文档的分数绝对差距（因已降序，gap≥0）
            abs_gap = current_score - next_score
            # 计算相对差距：绝对差距 / 当前文档分数（+1e-6避免除数为0/极小值，防止程序报错）
            # 1e-6 是 Python 中科学计数法的写法，等价于 0.000001（10 的负 6 次方，也就是百万分之一）。
            rel_gap = abs_gap / (abs(current_score) + 1e-6)

            # 触发断崖截断条件：绝对差距≥绝对阈值 OR 相对差距≥相对阈值
            # 满足任一条件，说明下一条文档相关性骤降，截断在当前位置
            if abs_gap >= RERANK_GAP_ABS or rel_gap >= RERANK_GAP_RATIO:
                # 最终取前i+1条（索引转实际数量，如i=2 → 取前3条）
                cutoff_pos = idx + 1
                logger.debug(f"断崖检测: 位置 {idx + 1}, abs_gap={abs_gap:.4f}, rel_gap={rel_gap:.4f}")
                break

        return ranked_docs[:cutoff_pos]
```

#### 总结

##### 节点功能概览



<img src="images/rerank节点功能概览.jpg" style="zoom:67%;" />

##### 节点交互图

<img src="images/rerank节点交互.jpg" style="zoom:67%;" />
