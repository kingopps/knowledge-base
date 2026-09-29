# /home/ubuntu/project/ZGzhiku/code/knowledge_base/test/test_multi_doc_import.py
"""
测试多文档导入：验证文件是否成功入库到 Milvus
"""
from utils.milvus_utils import get_milvus_client
from config.milvus_config import milvus_config

def check_imported_files():
    """检查已导入的文件"""
    client = get_milvus_client()
    
    # 1. 检查集合是否存在
    collections = client.list_collections()
    print(f"✅ Milvus 集合列表: {collections}")
    
    if milvus_config.chunks_collection not in collections:
        print(f"❌ 集合 {milvus_config.chunks_collection} 不存在")
        return
    
    # 2. 查询集合中的文件
    res = client.query(
        collection_name=milvus_config.chunks_collection,
        output_fields=["file_title", "chunk_id"],
        limit=1000
    )
    
    # 3. 统计每个文件的 chunk 数量
    file_chunks = {}
    for item in res:
        title = item.get("file_title", "unknown")
        file_chunks[title] = file_chunks.get(title, 0) + 1
    
    print(f"\n📊 已导入文件统计（共 {len(file_chunks)} 个文件，{len(res)} 个 chunks）:")
    for title, count in sorted(file_chunks.items()):
        print(f"  - {title}: {count} chunks")
    
    # 4. 检查 item_name 集合
    if milvus_config.item_name_collection in collections:
        item_res = client.query(
            collection_name=milvus_config.item_name_collection,
            output_fields=["item_name"],
            limit=100
        )
        print(f"\n📋 商品名称列表（共 {len(item_res)} 个）:")
        for item in item_res:
            print(f"  - {item.get('item_name', 'unknown')}")

if __name__ == "__main__":
    check_imported_files()