"""
查询流程的接口定义
"""
import uuid
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from pydantic import BaseModel, Field
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse, StreamingResponse

from processor.query_processor.main_graph import KBQueryWorkflow
from utils.mongo_history_utils import clear_history, get_recent_messages
from utils.sse_utils import create_sse_queue, SSEEvent, push_to_session, sse_generator
from utils.task_utils import update_task_status, TASK_STATUS_PROCESSING, get_task_result, TASK_STATUS_COMPLETED, \
    TASK_STATUS_FAILED
from tool.logger import logger

# 1. 创建应用
app = FastAPI(
    title="掌柜智库-查询API",
    description="此文档是掌柜智库查询流程的API接口说明"
)

# 2. 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许的源
    allow_credentials=True,  # 允许携带cookie
    allow_methods=["*"],  # 允许的请求方法
    allow_headers=["*"],  # 允许的请求头
)

# 3. 静态页面路由（暂时注释，等创建 page 目录后启用）
@app.get("/chat.html")  # 对外访问地址
async def chat():
    current_dir_parent_path = Path(__file__).absolute().parent.parent
    html_path = current_dir_parent_path / "page" / "chat.html"
    # 如果不存在，抛出404异常
    if not html_path.exists():
        raise HTTPException(status_code=404, detail=f"没有查询到页面，地址为：{html_path}")
    return FileResponse(html_path)

# 定义接口接收的数据结构
class QueryRequest(BaseModel):
    """查询请求数据结构"""
    query: str = Field(..., description="查询内容")  # ...必须填写
    session_id: str = Field(None, description="会话ID")
    is_stream: bool = Field(False, description="是否流式返回")

@app.post("/query")
async def query(background_tasks: BackgroundTasks, request: QueryRequest):
    """
    查询接口：支持流式和非流式两种模式
    
    流式模式：
    - 立即返回 session_id
    - 通过 /stream/{session_id} 接口接收 SSE 事件流
    
    非流式模式：
    - 同步等待处理完成
    - 直接返回完整答案
    """
    user_query = request.query
    session_id = request.session_id if request.session_id else str(uuid.uuid4())
    is_stream = request.is_stream

    if is_stream:
        # 流式模式：创建 SSE 队列
        create_sse_queue(session_id)
    
    # 更新任务状态为处理中
    update_task_status(session_id, TASK_STATUS_PROCESSING, is_stream)

    logger.info(f"开始处理流程... 是否流式: {is_stream}, query: {user_query}, session_id: {session_id}")

    if is_stream:
        # 流式模式：后台任务处理，立即返回
        background_tasks.add_task(run_query_graph, session_id, user_query, is_stream)
        logger.info("流式模式：返回 session_id，等待 /stream 接口连接")
        return {
            "message": "结果正在处理中...",
            "session_id": session_id
        }
    else:
        # 非流式模式：同步等待完成
        run_query_graph(session_id, user_query, is_stream)
        answer = get_task_result(session_id, "answer", "")
        return {
            "message": "处理完成！",
            "session_id": session_id,
            "answer": answer,
            "done_list": []
        }

def run_query_graph(session_id: str, user_query: str, is_stream: bool = True):
    """
    执行查询流程图
    
    :param session_id: 会话ID
    :param user_query: 用户问题
    :param is_stream: 是否流式输出
    """
    logger.info(f"开始流程图处理... {session_id} {user_query} {is_stream}")

    init_state = {
        "original_query": user_query,
        "session_id": session_id,
        "is_stream": is_stream
    }

    try:
        workflow = KBQueryWorkflow()
        for chunk in workflow.run(init_state, stream=is_stream):
            logger.debug(chunk)
        update_task_status(session_id, TASK_STATUS_COMPLETED, is_stream)
    except Exception as e:
        logger.error(f"流程执行异常: {e}", exc_info=True)
        update_task_status(session_id, TASK_STATUS_FAILED, is_stream)
        if is_stream:
            push_to_session(session_id, SSEEvent.ERROR, {"error": str(e)})

@app.get("/stream/{session_id}")
async def stream(session_id: str, request: Request):
    """
    SSE 流式输出接口
    
    前端通过 EventSource 连接此接口，实时接收：
    - ready: 连接建立
    - progress: 节点进度（done_list/running_list）
    - delta: LLM 流式增量输出
    - final: 最终完整答案 + 图片URL
    - error: 错误信息
    """
    logger.info(f"调用流式 /stream/{session_id}")
    
    return StreamingResponse(
        sse_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 禁用缓冲
        }
    )

@app.get("/history/{session_id}")
async def get_history(session_id: str, limit: int = 50):
    """
    查询当前会话历史记录
    """
    try:
        records = get_recent_messages(session_id, limit=limit)
        items = []
        for r in records:
            items.append({
                "_id": str(r.get("_id")) if r.get("_id") is not None else "",
                "session_id": r.get("session_id", ""),
                "role": r.get("role", ""),
                "text": r.get("text", ""),
                "rewritten_query": r.get("rewritten_query", ""),
                "item_names": r.get("item_names", []),
                "image_urls": r.get("image_urls", []),
                "ts": r.get("ts")
            })
        return {"session_id": session_id, "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"history error: {e}")

@app.delete("/history/{session_id}")
async def clear_chat_history(session_id: str):
    """
    清空指定会话的历史记录
    """
    count = clear_history(session_id)
    return {"message": "历史会话已清空", "deleted_count": count}

@app.get("/health")
async def health():
    """
    健康检查接口
    """
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)