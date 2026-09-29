# processor/import_processor/nodes/node_item_name_recognition.py
import json
import logging
from typing import Tuple, Dict, List

from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI
from pymilvus import DataType

from config.lm_config import lm_config
from config.milvus_config import milvus_config
from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.prompt.item_name_recognition import ITEM_NAME_RECOGNITION_TEMPLATE, \
    ITEM_NAME_RECOGNITION_SYSTEM_PROMPT
from processor.import_processor.state import ImportGraphState
from utils.embedding_utils import generate_embeddings
from utils.milvus_utils import get_milvus_client, escape_milvus_string

class NodeItemNameRecognition(BaseNode):
    """
    主体识别节点：主体识别与标签提取
    """

    name = "node_item_name_recognition"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        """
        LangGraph 核心节点：商品主体名称识别
        流程总览：
            1. 提取输入
            2. 构建大模型上下文
            3. 调用大模型识别商品名称
            4. 回填商品名称到状态和切片
            5. 生成商品名称的稠密/稀疏向量
            6. 将数据存入Milvus向量数据库

        必要参数：task_id、file_title, chunks
        更新参数：item_name

        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        # 步骤1：提取并校验输入
        file_title, chunks = self._step_1_get_inputs(state)

        # 步骤2：构建大模型识别的上下文
        context = self._step_2_build_context(chunks)

        # 步骤3：调用大模型识别商品名称
        item_name = self._step_3_call_llm(file_title, context)

        # 步骤4：回填商品名称到状态和切片
        self._step_4_update_chunks(state, chunks, item_name)

        # 步骤5：为商品名称生成稠密/稀疏向量
        dense_vector, sparse_vector = self._step_5_generate_vectors(item_name)

        # 步骤6：将数据存入Milvus向量数据库
        self._step_6_save_to_milvus(state, file_title, item_name, dense_vector, sparse_vector)

        # 打印识别结果
        self.logger.info(f"--- 识别完成: {item_name} ---")

        return state

    def _step_1_get_inputs(self, state: ImportGraphState) -> Tuple[str, List[Dict]]:
        """
        步骤 1: 接收并校验流程输入
        依赖的状态数据（上游节点产出）：
            - state["file_title"]: 上游提取的文件标题
            - state["chunks"]: 文本切片列表
        返回值：
            Tuple[str, List[Dict]]: (处理后的文件标题, 校验后的文本切片列表)
        """

        # 1、参数校验
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title", message="文件标题不能为空", expected_type=str)

        chunks = state.get("chunks")
        if not chunks:
            raise StateFieldError(field_name="chunks", message="chunks不能为空", expected_type=list)

        if not isinstance(chunks, list):
            raise StateFieldError(field_name="chunks", message="chunks数据类型不正确", expected_type=list)

        return file_title, chunks

    def _step_2_build_context(self, chunks: List[Dict]) -> str:
        """
        步骤 2: 构造大模型商品名称识别的标准化上下文
        核心作用：
            1. 限制切片数量：仅取前k个切片，避免上下文过长
            2. 限制字符长度：总上下文字符限制，适配大模型输入上限
            3. 格式化内容：带序号的结构化格式，提升大模型识别精度
        """

        parts: List[str] = []
        total_chars = 0
        for idx, chunk in enumerate(chunks[:self.config.item_name_chunk_k], start=1):

            # 1. 提取前k的切片，避免上下文过长
            chunk_title = chunk.get("title").strip()
            chunk_content = chunk.get("content").strip()

            # 2. 格式化切片
            piece = f"【切片{idx}】\n标题{chunk_title}\n内容：{chunk_content}"
            parts.append(piece)

            # 3. 计算累计的字符数
            total_chars += len(piece)

            # 4. 判断是否需要继续累加
            if total_chars > self.config.item_name_chunk_size:
                self.logger.warning(f"累计字符数{total_chars}已超过限制{self.config.item_name_chunk_size}，停止累加")
                break

        # 5. 使用换行符对切分后的片段进行连接
        context = "\n\n".join(parts).strip()

        # 6. 对返回结果进行二次截断
        final_context = context[:self.config.item_name_chunk_size]

        return final_context

    def _step_3_call_llm(self, file_title: str, context: str) -> str:
        """
        步骤 3: 调用大模型实现商品名称/型号精准识别
        核心特性：
            - 提示词解耦：通过模板文件加载，无需硬编码
            - 异常兜底：大模型返回空/调用异常时返回file_title，保证流程不中断
        返回值：
            str: 清洗后的商品名称（异常/空值时返回原始file_title）
        """

        # 1. 上下文为空，返回file_title
        if not context:
            return file_title

        # 2. 大模型调用
        try:
            # 2.1 加载提示词模板
            prompt = ITEM_NAME_RECOGNITION_TEMPLATE.format(
                file_title=file_title,
                context=context
            )
            # 2.2 初始化大模型客户端
            llm = ChatOpenAI(
                model=lm_config.llm_model,
                api_key=lm_config.api_key,
                base_url=lm_config.base_url,
                temperature=lm_config.llm_temperature,
                extra_body={"enable_thinking": False}
            )

            # 2.3 创建消息对象
            messages = [
                SystemMessage(content=ITEM_NAME_RECOGNITION_SYSTEM_PROMPT),
                HumanMessage(content=prompt)
            ]

            # 2.4 模型调用
            response = llm.invoke(messages)
            item_name = response.content

            # 2.5 数据清洗
            item_name = (item_name.replace(" ", "")
                         .replace("\n", "")
                         .replace("\t", "")
                         .replace("\r", ""))

            # 2.6 如果返回空字符串
            if not item_name:
                return file_title

            return item_name

        except Exception as e:
            self.logger.error(f"大模型调用异常：{e}")
            return file_title

    def _step_4_update_chunks(self, state: ImportGraphState, chunks: List[Dict[str, str]], item_name: str):
        """
        步骤 4: 回填商品名称到流程状态和所有文本切片
        设计思路：
            所有切片关联同一商品名称，保证后续向量入库、检索时的维度一致性
        """

        state["item_name"] = item_name

        for chunk in chunks:
            chunk["item_name"] = item_name

        state["chunks"] = chunks

    def _step_5_generate_vectors(self, item_name: str) -> Tuple[List, Dict]:
        """
        步骤 5: 为商品名称生成稠密 + 稀疏双向量（Milvus 向量检索核心）
        本项目：DashScope text-embedding-v4 API（output_type=dense&sparse）
        返回值：
            Tuple[List, Dict]: (稠密向量列表，稀疏向量字典)
        """

        # 1. 空值时直接返回空向量
        if not item_name:
            return None, None

        # 2. 使用向量模型生成稠密向量和稀疏向量
        vectors = generate_embeddings([item_name])
        return vectors["dense"][0], vectors["sparse"][0]

    def _step_6_save_to_milvus(self, state: ImportGraphState, file_title: str, item_name: str, dense_vector,
                               sparse_vector):
        """
        步骤 6: 将商品名称、文件标题、双向量持久化到 Milvus 向量数据库
        核心逻辑：
            1. 客户端获取：获取单例 Milvus 客户端，连接失败则跳过
            2. 集合初始化：无集合则创建（定义 Schema+索引），有集合则直接使用
            3. 幂等性处理：删除同名文件数据，避免重复存储
            4. 数据插入：构造符合 Schema 的数据，非空向量才添加
        """

        # 1. 获取 Milvus 客户端
        milvus_client = get_milvus_client()
        if not milvus_client:
            # 降级处理
            self.logger.warning("Milvus 连接失败，跳过设备名称保存")
            return
        try:
            # 2. 集合初始化
            collection_name = milvus_config.item_name_collection

            # 判断集合是否已经被创建
            if not milvus_client.has_collection(collection_name):
                self._create_item_name_collection(collection_name, milvus_client)

            # 3. 幂等性处理：删除同名文件数据，避免重复存储
            escaped_title = escape_milvus_string(file_title)
            milvus_client.delete(collection_name=collection_name, filter=f"file_title=='{escaped_title}'")

            # 4. 数据插入：构造符合 Schema 的数据，非空向量才添加
            data = {
                "file_title": file_title,
                "item_name": item_name
            }

            if dense_vector is not None:
                data["dense_vector"] = dense_vector
            if sparse_vector is not None:
                data["sparse_vector"] = sparse_vector

            milvus_client.insert(collection_name=collection_name, data=data)

        except Exception as e:
            # 降级处理
            self.logger.warning(f"数据存入Milvus失败，跳过设备名称保存，错误原因:{str(e)}")

    def _create_item_name_collection(self, collection_name, milvus_client):

        # 1. 创建schema
        schema = milvus_client.create_schema(auto_id=True, enable_dynamic_field=True)

        # 2. 创建字段
        # 添加主键字段（INT64类型，自增）
        schema.add_field(
            field_name="pk",
            datatype=DataType.INT64,
            is_primary=True,
            auto_id=True
        )

        # 添加文件标题字段（VARCHAR类型，最大长度100）
        schema.add_field(
            field_name="file_title",
            datatype=DataType.VARCHAR,
            max_length=100
        )

        # 添加商品名称字段（VARCHAR类型，最大长度100）
        schema.add_field(
            field_name="item_name",
            datatype=DataType.VARCHAR,
            max_length=100
        )

        # 添加稠密向量字段（FLOAT_VECTOR类型，1024维，text-embedding-v4 维度）
        schema.add_field(
            field_name="dense_vector",
            datatype=DataType.FLOAT_VECTOR,
            dim=1024
        )

        # 添加稀疏向量字段（SPARSE_FLOAT_VECTOR类型，变长）
        schema.add_field(
            field_name="sparse_vector",
            datatype=DataType.SPARSE_FLOAT_VECTOR
        )

        # 3. 构建索引参数（提升向量检索性能）
        index_params = milvus_client.prepare_index_params()
        # 为稠密向量创建索引（IVF_FLAT：兼容性好，适合小数据量）
        index_params.add_index(
            field_name="dense_vector",
            index_name="dense_vector_index",
            index_type="IVF_FLAT",
            metric_type="COSINE",
            params={"nlist": 128}
        )

        # 为稀疏向量创建索引（SPARSE_INVERTED_INDEX：稀疏向量专用索引）
        index_params.add_index(
            field_name="sparse_vector",
            index_name="sparse_vector_index",
            index_type="SPARSE_INVERTED_INDEX",
            metric_type="IP",
            params={
                "inverted_index_algo": "DAAT_MAXSCORE",
                "normalize": True,
                "quantization": "none"
            })

        # 4. 创建集合（Schema + 索引）
        milvus_client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params
        )

if __name__ == "__main__":

    setup_logging()

    json_path = "/home/ubuntu/project/ZGzhiku/code/knowledge_base/output/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册/chunks.json"
    with open(json_path, "r", encoding="utf-8") as f:
        chunks_json = f.read()

    chunks = json.loads(chunks_json)

    init_state = {
        "task_id": "task_test_005",
        "chunks": chunks,
        "file_title": "Aolynk CB304n Cable网桥 用户手册-5W100-整本手册"
    }

    # 执行核心处理流程
    node_item_name_recognition = NodeItemNameRecognition()
    result = node_item_name_recognition(init_state)

    logging.getLogger().info(json.dumps({
        "item_name": result.get("item_name"),
        "chunks_count": len(result.get("chunks", [])),
    }, ensure_ascii=False, indent=4))