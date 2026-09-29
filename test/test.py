cd ~/project/ZGzhiku/code/knowledge_base
uv run python -c "
import dashscope
from dotenv import load_dotenv
import os

load_dotenv()
dashscope.api_key = os.getenv('OPENAI_API_KEY')

# 测试 gte-rerank 模型
resp = dashscope.TextReRank.call(
    model='gte-rerank-v2',
    query='测试',
    documents=['文档1', '文档2'],
    top_n=2,
    return_documents=False
)

print(f'状态码: {resp.status_code}')
print(f'响应: {resp}')
"

