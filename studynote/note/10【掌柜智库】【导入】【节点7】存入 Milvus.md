# 掌柜智库项目(RAG)实战

## 5. 导入数据节点实现与测试

### 5.7 存入 Milvus (node_import_milvus)

**文件**: `app/import_process/node_import_milvus.py`

#### **节点作用**

数据加载流程的终点，负责将处理好的结构化数据（切片内容、元数据、向量）持久化存储到向量数据库中，构建可供即时查询的索引。

#### **实现思路**

1.  **幂等性设计**: 在插入新数据前，根据 `item_name` 或文件 ID 清理旧数据，防止重复导入导致的数据污染。
2.  **Schema 适配**: 严格按照 Milvus 集合的 Schema 定义（主键、Dense字段、Sparse字段、JSON元数据字段）组织数据，确保插入成功率。
3.  **混合索引构建**: 确保存入的数据能够支持 Milvus 的 Hybrid Search（Dense + Sparse 加权），最大化检索效果。



#### 1. 单元测试

您可以在 `node_import_milvus.py` 文件底部直接运行以下测试代码：

```python
if __name__ == "__main__":

    import os
    # 获取项目所在路径
    from app.import_process.agent.state import create_default_state
    from app.utils.path_util import PROJECT_ROOT


    # 组装文件的绝对路径
    chunks_path = PROJECT_ROOT / "output/hak180产品安全手册/chunks_with_vector.json"
    # 读取切片
    chunks_json = chunks_path.read_text(encoding="utf-8")
    # 将json字符串chunks转成列表
    chunks = json.loads(chunks_json)
    # 当前节点图状态初始值
    init_state = create_default_state(
        task_id="task_001",
        chunks=chunks
    )

    # 执行节点的业务调用
    node_import_milvus = NodeImportMilvus()
    final_state = node_import_milvus(init_state)
```

#### 2. 主流程定义

定义 `node_import_milvus` ，串联各个步骤。

```python
import json
from typing import Dict, Any, List

from pymilvus import DataType

from app.clients.milvus_utils import get_milvus_client
from app.conf.milvus_config import milvus_config
from app.core.logger import logger
from app.import_process.agent.node_base import NodeBase
from app.import_process.agent.state import ImportGraphState
from app.utils.milvus_utils import escape_milvus_string


class NodeImportMilvus(NodeBase):
    """
    节点: 导入向量库 (node_import_milvus)
    为什么叫这个名字: 将处理好的向量数据写入 Milvus 数据库。
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_import_milvus"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        LangGraph核心节点：Milvus切片数据入库主流程
        执行流程（串行执行，一步一校验，保证数据一致性）：
            1. 输入校验：验证切片有效性、向量字段完整性，提取向量维度
            2. 环境准备：连接Milvus，集合不存在则自动创建Schema+索引
            3. 幂等清理：删除同item_name旧数据，避免重复存储
            4. 批量插入：预处理数据后批量入库，回填Milvus自增chunk_id
            5. 状态更新：将回填了chunk_id的切片更新回全局状态，供下游使用

        异常处理：
            任一步骤失败抛出ValueError，终止节点执行，保证数据不脏写

        必要参数：task_id、chunks
        更新参数：chunks字段回填chunk_id

        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        # 步骤1：输入数据有效性校验
        chunks_json_data, vector_dimension = self._step_1_check_input(state)

        # 步骤2：Milvus客户端连接+集合准备（自动建表）
        client = self._step_2_prepare_collection(vector_dimension)

        # 步骤3：幂等性处理 - 清理同item_name旧数据
        self._step_3_clean_old_data(client, chunks_json_data)

        # 步骤4：批量插入数据+主键chunk_id回填
        updated_chunks = self._step_4_insert_data(client, chunks_json_data)

        # 步骤5：更新全局状态，将回填后的切片回传下游
        state["chunks"] = updated_chunks


        return state

```

#### 3. 步骤 1: 检查输入

**功能**: 验证 `chunks` 是否存在，并提取 `dense_vector` 维度和 `item_name`。

```python


    def _step_1_check_input(self, state: Dict[str, Any]) -> tuple[List[Dict[str, Any]], int]:
        """
        步骤1：输入数据有效性校验
        核心校验项：
            1. chunks非空且为列表类型
            2. 切片包含dense_vector核心字段
            3. 提取向量维度，为集合创建/索引构建提供依据
        参数：
            state: Dict[str, Any] - 流程状态对象，包含上游传入的chunks数据
        返回：
            tuple - (校验通过的切片列表, 稠密向量维度)
        异常：
            任一校验项不通过，抛出ValueError终止入库流程，避免脏数据处理

        """

        # 校验1：chunks非空
        chunks = state.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            raise ValueError("核心参数chunks为空或非列表类型")

        # 校验2：切片包含dense_vector字段
        first_chunk = chunks[0]
        if 'dense_vector' not in first_chunk:
            raise ValueError("错误: 数据中缺失dense_vector字段")

        # 校验3：切片包含 sparse_vector 字段
        if 'sparse_vector' not in first_chunk:
            raise ValueError("错误: 数据中缺失sparse_vector字段")

        # 提取向量维度和商品名称，用于后续集合创建/日志展示
        vector_dimension = len(first_chunk['dense_vector'])
        item_name = first_chunk.get('item_name', '未知商品名')
        logger.info(f"Milvus入库校验通过，待入库切片数：{len(chunks)} | 向量维度：{vector_dimension} | 商品名称：{item_name}")

        return chunks, vector_dimension

```

#### 4. 步骤 2: 准备集合 

**功能**: 获取 Milvus 客户端，如果集合不存在则创建。

```python

    def _step_2_prepare_collection(self, vector_dimension: int):
        """
        步骤2：Milvus客户端连接+集合准备
        核心逻辑：
            1. 获取Milvus单例客户端，验证连接有效性
            2. 集合不存在则自动创建（Schema+索引），存在则直接复用
        参数：
            vector_dimension: int - 稠密向量维度（步骤1提取）
        返回：
            MilvusClient - 已连接、集合准备完成的客户端实例
        异常：
            客户端获取失败/集合名称未配置，抛出ValueError终止流程
        """

        # 1、从环境变量读取 Milvus 核心配置，与 MilvusConfig 配置类保持一致
        collection_name = milvus_config.chunks_collection
        # 从配置文件读取切片集合名称，与配置解耦，便于环境切换

        # 2、配置缺失校验：配置为空则跳过 Milvus 存储，记录警告
        if not collection_name:
            logger.error("Milvus集合名称未配置：CHUNKS_COLLECTION_NAME为空")
            raise ValueError("未配置CHUNKS_COLLECTION集合名称")

        # 3、获取 Milvus 单例客户端，连接失败则直接返回
        client = get_milvus_client()
        if not client:
            logger.error("Milvus客户端获取失败：get_milvus_client()返回空，连接可能异常")
            raise ValueError("Milvus 连接失败：get_milvus_client() 返回空")

        # 4. 集合不存在则自动创建
        if not client.has_collection(collection_name=collection_name):

            logger.info(f"Milvus集合{collection_name}不存在，开始自动创建Schema和索引")
            self._create_collection(client, collection_name, vector_dimension)
        else:
            logger.info(f"Milvus集合{collection_name}已存在，直接复用")

        return client


    def _create_collection(self, client, collection_name: str, vector_dimension: int):
        """
        辅助函数：Milvus集合+索引自动创建
        核心逻辑：
            1. 定义集合Schema：包含业务字段+双向量字段，自增主键chunk_id
            2. 构建向量索引：稠密向量用AUTOINDEX（Milvus自动选最优索引），稀疏向量用专用索引
        参数：
            client - MilvusClient实例（已连接）
            collection_name: str - 要创建的集合名称
            vector_dimension: int - 稠密向量维度（与向量化模型保持一致）
        """
        # 1. 创建Schema：自增主键+支持动态字段，适配灵活的业务扩展
        schema = client.create_schema(auto_id=True, enable_dynamic_fields=True)

        # 2. 新增字段：业务字段+主键+双向量字段，字段类型/长度适配业务场景
        schema.add_field(field_name="chunk_id", datatype=DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=65535)  # 切片内容
        schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=65535)  # 切片标题
        schema.add_field(field_name="parent_title", datatype=DataType.VARCHAR, max_length=65535)  # 父标题
        schema.add_field(field_name="part", datatype=DataType.INT8)  # 分片编号
        schema.add_field(field_name="file_title", datatype=DataType.VARCHAR, max_length=65535)  # 源文件标题
        schema.add_field(field_name="item_name", datatype=DataType.VARCHAR, max_length=65535)  # 商品名称（幂等性依据）
        schema.add_field(field_name="sparse_vector", datatype=DataType.SPARSE_FLOAT_VECTOR)  # 稀疏向量
        schema.add_field(field_name="dense_vector", datatype=DataType.FLOAT_VECTOR, dim=vector_dimension)  # 稠密向量

        # 3. 构建索引参数：为向量字段创建索引，提升检索性能
        index_params = client.prepare_index_params()
        # 稠密向量索引：AUTOINDEX自动选最优索引类型+余弦相似度（语义检索常用）
        index_params.add_index(
            field_name="dense_vector",
            index_name="dense_vector_index",
            index_type="AUTOINDEX",
            metric_type="COSINE"
        )
        # 稀疏向量索引：专用SPARSE_INVERTED_INDEX+内积（IP），适配稀疏向量检索
        index_params.add_index(
            field_name="sparse_vector",
            index_name="sparse_inverted_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={"inverted_index_algo": "DAAT_MAXSCORE", "normalize": True, "quantization": "none"}
        )

        # 4. 创建集合：Schema+索引参数结合，一次性完成初始化
        client.create_collection(collection_name=collection_name, schema=schema, index_params=index_params)
        logger.info(f"Milvus集合创建成功：{collection_name}，向量维度：{vector_dimension}")
```



> **IVF_FLAT 和 AUTOINDEX** 
>
> 1. IVF_FLAT - 手动指定索引类型
>
> 特点：
> ✅ 明确控制：你知道用的是什么索引
> ✅ 可 tuning：可以调整 nlist 等参数优化性能
> ❌ 需要经验：要自己判断适合什么索引
> ❌ 固定不变：数据量变化后可能不是最优
>
> 2. AUTOINDEX - 自动选择最优索引
>
> 特点：
> ✅ 智能选择：Milvus 根据数据量、维度自动选最优
> ✅ 自适应：数据量变化时自动升级索引策略
> ✅ 省心：不需要懂索引原理也能用好
> ❌ 黑盒：你不知道具体用的是什么
> ❌ 不可控：无法手动调优
>
> 
>
> 3. Milvus 的 AUTOINDEX 如何选择？
>
> - Milvus 会根据以下因素自动选择：
>
> ```python
> # 伪代码展示 AUTOINDEX 的决策逻辑
> if 数据量 < 10 万:
>     使用 FLAT 索引  # 精确搜索，速度也够快
> elif 数据量 < 1000 万:
>     使用 IVF_FLAT  # 近似搜索，精度高速度快
> elif 数据量 < 1 亿:
>     使用 IVF_PQ  # 压缩存储，节省内存
> else:
>     使用 HNSW  # 超大规模最优
> ```
>
> 
>
> 4. 哪个更好？
>
> - 推荐 AUTOINDEX 的场景 ✅
>   - 快速原型开发：先跑通业务，再优化
>   - 数据量不确定：不知道未来会有多少数据
>   - 团队无专家：没有人专门研究向量索引
>   - 中小规模：数据量 < 1000 万
>
> - 推荐 IVF_FLAT 的场景 ✅
>   - 生产环境优化：已经知道数据特征
>   - 性能敏感：需要极致优化检索速度
>   - 有专业团队：有人能 tuning 参数
>   - 特殊需求：需要精确控制内存/速度比



#### 5. 步骤 3: 清理旧数据 

**功能**: 根据 `item_name` 删除已存在的切片，确保幂等性。

```python

    def _step_3_clean_old_data(self, client, chunks_json_data: List[Dict[str, Any]]):
        """
        步骤3：幂等性处理 - 基于item_name清理旧数据
        核心设计：
            插入新数据前删除同item_name的所有旧切片，确保多次执行仅保留最新数据
            支持多item_name批量清理，自动去重避免重复操作
        参数：
            client - MilvusClient实例
            chunks_json_data: List[Dict[str, Any]] - 待入库的切片列表
        """
        # 提取并去重item_name，避免重复清理同一商品数据
        item_names = sorted({
            str(x.get("item_name", "")).strip()
            for x in chunks_json_data or []
            if str(x.get("item_name", "")).strip()
        })
        # 无有效item_name则跳过清理
        if not item_names:
            logger.warning("Milvus幂等性清理跳过：切片中无有效item_name")
            return
        # 多item_name提示日志
        if len(item_names) > 1:
            logger.warning(f"Milvus幂等性清理：本次检测到多个item_name，将逐个清理：{item_names}")

        # 遍历item_name，逐个清理旧数据
        for i_name in item_names:
            self._clear_chunks_by_item_name(client, i_name)

    def _clear_chunks_by_item_name(self, client, item_name: str):
        """
        内部核心函数：根据item_name删除Milvus中的旧切片数据
        参数：
            client - MilvusClient实例
            item_name: str - 要清理的商品名称
        异常：
            清理失败抛出ValueError，终止整个入库流程（保证幂等性）
        """

        try:
            # 1. 商品名称安全转义，避免filter表达式报错
            safe_item_name = escape_milvus_string(item_name)
            filter_expr = f'item_name == "{safe_item_name}"'

            # 2. 执行删除操作
            client.delete(collection_name=milvus_config.chunks_collection, filter=filter_expr)
            logger.info(f"Milvus幂等性清理完成：成功删除item_name={item_name}的旧数据")

        except Exception as e:
            logger.error(f"Milvus幂等性清理失败：item_name={item_name} | 错误：{str(e)}", exc_info=True)
            raise ValueError(f"幂等清理失败（item_name={item_name}）: {e}")
```

> 列表推导式拆解
>
> ```python
> item_names = sorted({
>     str(x.get("item_name", "")).strip()
>     for x in chunks_json_data or []
>     if str(x.get("item_name", "")).strip()
> })
> ```
>
> 分解动作：
>
> - `for x in chunks_json_data or []` 遍历 `chunks_json_data` 列表中的每个元素。如果这个列表是 `None`，就用空列表 `[]` 代替，避免报错。
> - `x.get("item_name", "")` 从每个元素（字典）中获取 `item_name` 这个键的值。如果找不到这个键，就返回空字符串 ""。
> - `str(...)` 确保拿到的值转换成字符串类型。
> - `.strip()` 去掉字符串开头和结尾的空格（比如 " 空调 " 变成 "空调"）。
> - `if str(x.get("item_name", "")).strip()` 这是一个过滤条件：只保留那些处理后不是空字符串的项目名称。
> - `{...}` 使用集合（`set`）来存储结果，自动去重。比如有两个 "空调"，只会保留一个。
> - `sorted(...)` 对去重后的集合进行排序，返回一个有序的列表。



#### 6. 步骤 4: 插入数据

**功能**: 移除临时 `chunk_id`，批量插入数据，并回填生成的 ID。

```python
    def _step_4_insert_data(self, client, chunks_json_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        步骤4：批量插入切片数据到Milvus+主键回填
        核心逻辑：
            1. 批量插入数据：提升入库效率，减少Milvus连接次数
            2. 回填chunk_id：将Milvus生成的自增主键回填到切片，供下游业务使用
        参数：
            client - MilvusClient实例
            chunks_json_data: List[Dict[str, Any]] - 待入库的切片列表
        返回：
            List[Dict[str, Any]] - 回填了chunk_id的切片列表
        """
        # 1. 预处理数据：移除手动chunk_id，避免与Milvus自增主键冲突
        data_to_insert = []
        for item in chunks_json_data:
            item_copy = item.copy()

            # 补充 part 字段
            if "part" not in item_copy:
                item_copy["part"] = 0

            # 添加到待插入列表
            data_to_insert.append(item_copy)

        logger.info(f"Milvus数据插入：准备{len(data_to_insert)}条切片数据，开始批量插入")

        # 2. 执行批量插入
        insert_result = client.insert(collection_name=milvus_config.chunks_collection, data=data_to_insert)
        insert_count = insert_result.get('insert_count', 0)
        logger.info(f"Milvus数据插入完成：成功插入{insert_count}条数据，插入结果：{insert_result}")

        # 3. 主键回填：将Milvus生成的chunk_id回填到原始切片
        inserted_ids = insert_result.get('ids', [])
        if inserted_ids:
            logger.info(f"Milvus主键回填：开始将{len(inserted_ids)}个自增chunk_id回填到切片")
            for idx, item in enumerate(chunks_json_data):
                item['chunk_id'] = str(inserted_ids[idx])
            logger.info("Milvus主键回填完成：所有切片已绑定chunk_id")

        return chunks_json_data
```

### 5.8 进行主图调用测试

主图添加测试代码，进行流程完成测试！

```python
# test/test_workflow.py

import os

from app.import_process.agent.kb_import_workflow import KBImportWorkflow
from app.import_process.agent.state import create_default_state
from app.utils.path_util import PROJECT_ROOT
from app.core.logger import logger

# 测试完整流程

# 1. 测试文件路径
local_file = os.path.join("doc", "H3C LA2608室内无线网关 用户手册-6W100-整本手册.pdf")
local_file_path = os.path.join(PROJECT_ROOT, local_file)
# 2. 输出目录
local_dir = os.path.join(PROJECT_ROOT, "output")
# 3. 定义初始状态
initial_state = create_default_state(
    task_id="task_demo",
    local_file_path=local_file_path,
    local_dir=local_dir
)
# 4. 创建工作流实例
kb_import_app = KBImportWorkflow()

final_state = kb_import_app.run(initial_state)
logger.info(f"工作流执行完成！最终状态: {final_state}")
```

