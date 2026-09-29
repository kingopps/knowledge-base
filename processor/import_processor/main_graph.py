"""
导入功能的主流程图
"""
import json
import logging

from langgraph.constants import END
from langgraph.graph import StateGraph

from processor.import_processor.base import setup_logging
from processor.import_processor.nodes.node_bge_embedding import NodeBGEEmbedding
from processor.import_processor.nodes.node_document_split import NodeDocumentSplit
from processor.import_processor.nodes.node_enrty import NodeEntry
from processor.import_processor.nodes.node_import_milvus import NodeImportMilvus
from processor.import_processor.nodes.node_item_name_recognition import NodeItemNameRecognition
from processor.import_processor.nodes.node_md_img import NodeMDImg
from processor.import_processor.nodes.node_pdf_to_md import NodePDFToMD
from processor.import_processor.state import ImportGraphState


class KBImportWorkflow:

    def __init__(self):
        """
        初始化工作流对象
        """
        self._compiled_graph = None


    @property
    def graph(self):
        """
        延迟加载（懒加载）：只在第一次使用工作流对象的时候编译图
        :return:
        """

        if self._compiled_graph is None:
            self._compiled_graph = self.build_graph()
        return self._compiled_graph


    def build_graph(self):

        # 1.初始化图（工作流）
        graph = StateGraph (ImportGraphState)

        # 2.在图中注册节点
        graph.add_node("node_entry", NodeEntry())#入口：判断文档类型
        graph.add_node("node_pdf_to_md", NodePDFToMD())#pdf转换为markdown
        graph.add_node("node_md_img", NodeMDImg())#解析文档中的图片的含义，并将其嵌入文档中
        graph.add_node("node_document_split", NodeDocumentSplit())#文档切分
        graph.add_node("node_item_name_recognition", NodeItemNameRecognition())#识别商品名称
        graph.add_node("node_bge_embedding", NodeBGEEmbedding())#将文本转成向量
        graph.add_node("node_import_milvus", NodeImportMilvus())#将向量和标量存入milvus

        # 3. 设置入口节点
        graph.set_entry_point("node_entry")
        # 4. 注册条件边
        graph.add_conditional_edges(
            "node_entry",
            self.route_after_entry,
            {
                #key：路由函数的返回值，value：节点的名字
                "node_pdf_to_md":"node_pdf_to_md",
                "node_md_img":"node_md_img",
                END:END
            }
        )

        # 5.注册顺序边
        graph.add_edge("node_pdf_to_md", "node_md_img")
        graph.add_edge("node_md_img", "node_document_split")
        graph.add_edge("node_document_split", "node_item_name_recognition")
        graph.add_edge("node_item_name_recognition", "node_bge_embedding")
        graph.add_edge("node_bge_embedding", "node_import_milvus")
        graph.add_edge("node_import_milvus", END)

        # 6. 编译工作流
        return graph.compile()

    @staticmethod
    def route_after_entry(state: ImportGraphState) -> str:

        if state.get("is_pdf_read_enabled"):
            return "node_pdf_to_md"

        elif state.get("is_md_read_enabled"):
            return "node_md_img"

        else:
            return END

    def run(self, state: ImportGraphState, stream: bool = False):

        if stream:
            # return self.graph.stream(state, stream_mode="values")
            return self.graph.stream(state)
        else:
            return self.graph.invoke(state)

if __name__ == "__main__":

    #激活全局日志
    setup_logging()

    # 初始化图状态（task_id 必填：BaseNode 的 __call__ 会硬读该字段）
    init_state = {
        "task_id": "task_test_main_graph",
        "import_file_path": "/home/ubuntu/project/ZGzhiku/code/knowledge_base/doc/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.pdf",
        "file_dir": "/home/ubuntu/project/ZGzhiku/code/knowledge_base/output"
    }
    workflow = KBImportWorkflow()
    final_state = workflow.run(init_state)

    # final_state 含 33 个 chunk（带向量数据），打印摘要避免刷屏
    result_chunks = final_state.get("chunks", [])
    logging.getLogger().info(json.dumps({
        "file_title": final_state.get("file_title"),
        "item_name": final_state.get("item_name"),
        "md_path": final_state.get("md_path"),
        "chunks_count": len(result_chunks),
        "first_chunk_has_dense": bool(result_chunks and "dense_vector" in result_chunks[0]),
        "first_chunk_has_sparse": bool(result_chunks and "sparse_vector" in result_chunks[0]),
    }, ensure_ascii=False, indent=4))

    # 打印编译后的图结构
    # logging.getLogger().info(workflow.graph.get_graph().draw_ascii())
