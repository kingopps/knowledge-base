# config/reranker_config.py
# 适配本项目全 API 方案：使用 DashScope gte-rerank API

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class RerankerConfig:
    text_rerank_api_key: str      # DashScope API Key
    text_rerank_model: str        # 重排序模型名称（gte-rerank）
    text_rerank_instruct: str     # 指令前缀（gte-rerank 支持，空串表示不使用）

reranker_config = RerankerConfig(
    text_rerank_api_key=os.getenv("OPENAI_API_KEY"),
    text_rerank_model=os.getenv("RERANK_MODEL", "gte-rerank"),
    text_rerank_instruct=os.getenv("TEXT_RERANK_INSTRUCT", "")
)