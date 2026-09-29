"""
导入流程的API接口定义
"""
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File
from starlette.middleware.cors import CORSMiddleware

from config.minio_config import minio_config
from processor.import_processor.main_graph import KBImportWorkflow
from tool.logger import logger
from utils.minio_utils import get_minio_client
from utils.task_utils import (
    add_running_task, add_done_task, update_task_status,
    get_task_status, get_done_task_list, get_running_task_list
)

from fastapi import HTTPException
from starlette.responses import FileResponse

# 1. 创建应用
app = FastAPI(
    title="掌柜智库-导入API",
    description="此文档是掌柜智库导入流程的API接口说明"
)

# 2. 跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. 静态页面路由
@app.get("/import.html")
async def import_page():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    html_path = current_dir_parent_path / "page" / "import.html"
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
    return FileResponse(html_path)


# 后台任务函数
def run_graph_task(task_id: str, file_dir: str, import_file_path: str):
    """
    LangGraph全流程执行后台任务
    """
    try:
        # 1. 更新任务状态为处理中
        update_task_status(task_id, "processing")

        # 2. 初始化LangGraph状态
        init_state = {
            "task_id": task_id,
            "file_dir": file_dir,
            "import_file_path": import_file_path,
        }

        # 3. 流式执行LangGraph全流程
        workflow = KBImportWorkflow()
        for event in workflow.run(init_state, stream=True):
            for node_name, node_result in event.items():
                # 将完成的节点名加入已完成列表
                add_done_task(task_id, node_name)

        # 4. 全流程完成
        update_task_status(task_id, "completed")

    except Exception as e:
        update_task_status(task_id, "failed")
        logger.error(f"[{task_id}] LangGraph全流程执行失败: {e}", exc_info=True)

# 上传接口
@app.post("/upload", summary="文件上传接口")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    文件上传核心接口
    """
    # 1. 构建本地存储根目录
    data_based_root_dir = os.getenv("DATA_BASED_ROOT_DIR")
    if not data_based_root_dir:
        data_based_root_dir = "./output/import"
    
    data_dir = os.path.join(data_based_root_dir, datetime.now().strftime("%Y%m%d"))
    task_ids = []

    # 2. 遍历处理每个上传的文件
    for file in files:
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)
        logger.info(f"[{task_id}] 开始处理上传文件: {file.filename}")

        # 3. 标记上传阶段为运行中
        add_running_task(task_id, "upload_file")

        # 4. 构建本地目录
        file_dir = os.path.join(data_dir, task_id)
        os.makedirs(file_dir, exist_ok=True)
        import_file_path = os.path.join(file_dir, file.filename)

        # 5. 保存文件到本地
        with open(import_file_path, "wb") as file_buffer:
            shutil.copyfileobj(file.file, file_buffer)
        logger.info(f"[{task_id}] 文件已保存至: {import_file_path}")

        # 6. 上传至MinIO（持久化备份）
        minio_object_name = f"pdf_files/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        try:
            minio_client = get_minio_client()
            minio_bucket_name = minio_config.bucket_name
            minio_client.fput_object(
                bucket_name=minio_bucket_name,
                object_name=minio_object_name,
                file_path=import_file_path,
                content_type=file.content_type
            )
            logger.info(f"[{task_id}] 文件已上传至MinIO: {minio_object_name}")
        except Exception as e:
            logger.warning(f"[{task_id}] MinIO上传失败，继续本地处理: {e}", exc_info=True)

        # 7. 标记上传完成
        add_done_task(task_id, "upload_file")

        # 8. 启动后台任务
        background_tasks.add_task(run_graph_task, task_id, file_dir, import_file_path)
        logger.info(f"[{task_id}] LangGraph后台任务已启动")

    # 9. 返回结果
    logger.info(f"上传处理完毕，共 {len(files)} 个文件，task_ids: {task_ids}")
    return {
        "code": 200,
        "message": f"文件上传成功, total: {len(files)}",
        "task_ids": task_ids
    }

@app.get("/status/{task_id}", summary="任务状态查询")
async def get_task_progress(task_id: str):
    """
    任务状态查询接口
    """
    task_status_info: Dict[str, Any] = {
        "code": 200,
        "task_id": task_id,
        "status": get_task_status(task_id),
        "done_list": get_done_task_list(task_id),
        "running_list": get_running_task_list(task_id)
    }
    logger.info(f"[{task_id}] 状态查询: {task_status_info['status']}")
    return task_status_info

@app.get("/health")
async def health():
    """健康检查"""
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
