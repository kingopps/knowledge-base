# processor/query_processor/nodes/node_web_search_mcp.py
import asyncio
import json

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from config.bailian_mcp_config import mcp_config
from processor.query_processor.base import NodeBase
from processor.query_processor.state import QueryGraphState
from tool.logger import logger
from utils.json_format_utils import serialize_json
from utils.task_utils import add_done_task


class NodeWebSearchMcp(NodeBase):
    """
    节点功能，调用外部搜索引擎补充信息
    """

    # 覆盖基类的 name 属性，标识节点名称
    name: str = "node_web_search_mcp"

    def process(self, state: QueryGraphState) -> QueryGraphState:
        """
        节点逻辑
        :param state: 工作流状态对象
        :return: 更新后的状态对象
        """

        query = state.get("rewritten_query")
        result = asyncio.run(self._mcp_call(query))
        web_docs = []
        if result:
            json_str = result.content[0].text
            pages = json.loads(json_str).get("pages")
            for item in pages:
                snippet = item.get("snippet")
                url = item.get("url")
                title = item.get("title")

                web_docs.append({"title": title, "url": url, "snippet": snippet})

        add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
        if web_docs:
            return {"web_search_docs": web_docs}
        return {}


    async def _mcp_call(self, query: str):
        import httpx2
        headers = {"Authorization": f"Bearer {mcp_config.api_key}"}
        http_client = httpx2.AsyncClient(headers=headers, timeout=60)
        async with streamable_http_client(
            url=mcp_config.mcp_base_url,
            http_client=http_client,
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    name="bailian_web_search",
                    arguments={"query": query, "count": 5},
                )
                return result




if __name__ == "__main__":

    init_state = {
        "session_id": "test_web_search_mcp_001",
        "is_stream": False,
        "rewritten_query": "Aolynk CB304n 网桥怎么恢复出厂设置？"
    }

    # 执行节点的业务调用
    node_web_search_mcp = NodeWebSearchMcp()
    result = node_web_search_mcp(init_state)
    logger.info(serialize_json(result, indent=4))


