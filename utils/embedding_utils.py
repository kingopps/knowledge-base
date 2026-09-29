# utils/embedding_utils.py

"""
向量化工具：使用 DashScope text-embedding-v4 API 生成稠密+稀疏双向量

与原始代码的差异：
- 原始：本地 BGE-M3 模型
- 本项目：DashScope text-embedding-v4 API（output_type=dense&sparse）

返回格式与原始代码保持一致：
{
    "dense":  [ [0.1, 0.2, ...], ... ],   # List[List[float]]，每个文本一个稠密向量
    "sparse": [ {7149: 0.829, ...}, ... ] # List[Dict[int, float]]，每个文本一个稀疏向量
}
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv(override=True)

def generate_embeddings(texts):
    """
    为文本列表生成稠密+稀疏双向量

    :param texts: 要生成嵌入的文本列表（单次最多10条）
    :return: {"dense": [...], "sparse": [...]}
    """

    # 1. 从环境变量获取 API 配置
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
    dimension = int(os.getenv("EMBEDDING_DIM", "1024"))

    # 2. DashScope 原生 API 端点（sparse 向量只能通过原生 API 获取）
    #    从兼容模式 URL 推导出原生 API URL：
    #    https://dashscope.aliyuncs.com/compatible-mode/v1
    #    → https://dashscope.aliyuncs.com/api/v1
    native_base = base_url.replace("/compatible-mode/v1", "/api/v1")
    url = f"{native_base}/services/embeddings/text-embedding/text-embedding"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # 3. 构造请求体
    #    output_type="dense&sparse" 同时返回稠密和稀疏向量
    #    text_type="document" 表示这是待入库的文档文本（检索时 query 用 "query"）
    data = {
        "model": model,
        "input": {
            "texts": texts
        },
        "parameters": {
            "text_type": "document",
            "dimension": dimension,
            "output_type": "dense&sparse"
        }
    }

    # 4. 发送请求
    response = requests.post(url, headers=headers, json=data, timeout=60)
    if response.status_code != 200:
        raise RuntimeError(
            f"Embedding API 调用失败，状态码: {response.status_code}, "
            f"响应: {response.text}"
        )

    result = response.json()
    embeddings = result["output"]["embeddings"]

    # 5. 提取稠密向量和稀疏向量
    dense_vectors = []
    sparse_vectors = []

    for item in embeddings:
        # 稠密向量：直接是 List[float]
        dense_vectors.append(item["embedding"])

        # 稀疏向量：DashScope 返回 [{"index": 7149, "value": 0.829}, ...]
        # 需要转成 Milvus 需要的 {7149: 0.829, ...} 字典格式
        sparse_dict = {}
        for sparse_item in item.get("sparse_embedding", []):
            sparse_dict[sparse_item["index"]] = sparse_item["value"]
        sparse_vectors.append(sparse_dict)

    return {
        "dense": dense_vectors,
        "sparse": sparse_vectors
    }

if __name__ == "__main__":
    # 快速测试
    result = generate_embeddings(["这是一段测试文本", "Hello World"])
    print(f"稠密向量维度: {len(result['dense'][0])}")
    print(f"稠密向量前5个值: {result['dense'][0][:5]}")
    print(f"稀疏向量: {result['sparse'][0]}")