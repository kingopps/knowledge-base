# 掌柜智库项目(RAG)实战

## 6. 导入web服务集成和测试

本章节介绍如何将上述实现的 LangGraph 知识库导入流程集成到 FastAPI Web 服务中，并提供可视化界面供用户上传文件和查看导入进度。

### 6.1 FastAPI 基础讲解

FastAPI 是一个现代、快速（高性能）的 Web 框架，用于构建 APIs with Python 3.7+。

#### 1. 为什么选择 FastAPI？

*   **极速性能**：基于 **Starlette** (负责路由和异步) 和 **Pydantic** (负责数据验证)，性能在 Python web 框架中名列前茅。
*   **开发快**：简捷的语法减少了约 40% 的代码量，自动补全支持极佳。
*   **原生异步**：完美支持 `async` / `await`，轻松应对高并发场景。
*   **交互式文档**：启动服务后，访问 `/docs` 即可获得自动生成的 Swagger UI 接口文档，直接在浏览器调试接口。

#### 2. 核心概念与代码示例

##### 示例 1：安装和快速体验

安装 FastAPI 很简单，这里我们使用 **pip** 命令来安装。

```bash
uv add fastapi
```

另外我们还需要一个 ASGI 服务器，生产环境可以使用 Uvicorn 或者 Hypercorn：

```bash
uv add "uvicorn[standard]"
```

运行第一个 FastAPI 应用

创建一个名为 main.py 的文件，添加以下代码：

```python
from fastapi import FastAPI

# 创建一个 FastAPI 应用实例
app = FastAPI()

@app.get("/", summary="第一个测试")
def read_root():
    return {"Hello": "World"}
```

在命令行中运行以下命令以启动应用：

```bash
#如果 main.py在根目录下，则执行
uvicorn main:app --reload
或者
uv run uvicorn main:app --reload

#如果放在 test/fastapi 目录下，则执行
uvicorn test.fastapi.main:app --reload
或者
uv run uvicorn test.fastapi.main:app --reload

```

现在，打开浏览器并访问 **http://127.0.0.1:8000**，你应该能够看到返回的 JSON 响应。

**代码解析：**

- `from fastapi import FastAPI`： 这行代码从< code>fastapi 模块中导入了 `FastAPI` 类。`FastAPI` 类是 FastAPI 框架的核心，用于创建 FastAPI 应用程序实例。
- `app = FastAPI()`：这行代码创建了一个 FastAPI 应用实例。
- `@app.get("/")`： 这是一个装饰器，用于告诉 FastAPI 哪个 URL 应该触发下面的函数，并且指定了 HTTP 方法为 GET。在这个例子中，它指定了根 URL（即网站的主页）。
- `def read_root():`： 这是定义了一个名为 `read_root` 的函数，它将被调用当用户使用 GET 方法访问根 URL 时。
- `return {"Hello": "World"}`： 这行代码是 `read_root` 函数的返回值。当用户使用 GET 方法访问根 URL 时，这个 JSON 对象将被发送回用户的浏览器或 API 客户端。

默认情况下，你可以通过访问 **http://127.0.0.1:8000/docs** 来打开 Swagger UI 风格的文档：

<img src="images/image-20260126150221641-17694799119601.png" alt="image-20260126150221641" style="zoom: 33%;" />

##### **示例 2: 最简单的 API 与 参数解析**

展示如何定义 GET 请求，以及如何自动解析路径参数和查询参数。

```python
# 访问 http://127.0.0.1:8000/items/5?q=somequery
# item_id: 路径参数 (自动转为 int)
# q: 查询参数 (可选，默认 None)
@app.get("/items/{item_id}", summary="获取指定参数")
async def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "q": q}


# 接收? skip=? & limit = ?
@app.get("/items/", summary="分页")
def read_item(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}
```

函数接受两个参数：

- **item_id** --是路径参数，指定为整数类型。
- **q** -- 是查询参数，指定为字符串类型或空（None）。

FastAPI 提供了内置的交互式 API 文档，使开发者能够轻松了解和测试 API 的各个端点。

这个文档是自动生成的，基于 OpenAPI 规范，支持 Swagger UI 和 ReDoc 两种交互式界面。

通过 FastAPI 的交互式 API 文档，开发者能够更轻松地理解和使用 API，提高开发效率

在运行 FastAPI 应用时，Uvicorn 同时启动了交互式 API 文档服务。



使用以下方式启动可以进行断点调试：

```python
if __name__ == "__main__":
    """服务启动入口：本地开发环境直接运行"""
    logger.info("File Import Service 服务启动中...")
    # 启动uvicorn服务，绑定本地IP和8000端口，关闭自动重载（生产环境建议用workers多进程）
    uvicorn.run(
        app=app,
        host="127.0.0.1",  # 仅本地访问，生产环境改为0.0.0.0（允许所有IP访问）
        port=8000  # 服务端口
    )
```

类型检查和错误提示：展示如何定义数据结构，FastAPI 会自动进行类型检查和错误提示。

```python
from pydantic import BaseModel

# 定义数据模型
class Item(BaseModel):
    name: str
    price: float
    is_offer: bool = None

# POST 请求接收 JSON 数据
@app.post("/items/", summary="类型检查")
def create_item(item: Item):
    # item 已经是验证过的 Item 对象
    # 如果客户端传来的 price 是字符串 "abc"，FastAPI 会自动报错
    return {"name": item.name, "price": item.price, "is_offer": item.is_offer}


数据验证的幕后英雄
#用户输入错误数据
#    ↓
#FastAPI 接收请求
#    ↓
#交给 Pydantic 验证  ← Pydantic 登场！
#    ↓
#Pydantic 发现类型不匹配
#    ↓
#生成详细的错误信息
#    ↓
#FastAPI 把错误信息返回给用户

pydantic 的三大功劳：
功劳 1：自动类型检查
功劳 2：自动生成错误信息
功劳 3：自动类型转换（智能功能）

```

##### **示例 3: 响应JSON**数据

常见的响应形式：

```python
# 1、路由处理函数返回一个 Pydantic 模型实例，FastAPI 将自动将其转换为 JSON 格式，并作为响应发送给客户端：
@app.post("/items/return", summary="返回 Pydantic 模型实例")
def create_item(item: Item):
    return item


#2、使用 RedirectResponse 实现重定向，将客户端重定向到 /items/ 路由。
from fastapi.responses import RedirectResponse

@app.get("/redirect", summary="请求重定向")
def redirect():
    return RedirectResponse(url="/items/")

#3、使用 HTTPException 抛出异常，返回自定义的状态码和详细信息。
#以下实例在 item_id 为 42 会返回 404 状态码：
from fastapi import HTTPException

@app.delete("/items/{item_id}", summary="抛出异常")
def read_item(item_id: int):
    if item_id == 42:
        raise HTTPException(status_code=404, detail="Item 找不到")
    return {"item_id": item_id}
```

FastAPI 从 `fastapi.responses` 中提供了多种响应类，覆盖不同的使用场景，下面按「常用程度」整理，每个都附简单示例：

1. JSONResponse（最常用）

   - **作用**：返回 JSON 格式的数据（FastAPI 默认的响应类型）；

   - **场景**：接口返回普通数据（列表、字典、状态信息等）；

   - 示例

     ```python
     from fastapi.responses import JSONResponse
     
     @app.get("/api/user")
     def get_user():
         # 等价于直接 return {"name": "张三", "age": 20}（FastAPI 自动转 JSONResponse）
         return JSONResponse(
             content={"name": "张三", "age": 20},
             status_code=200,  # 可选，默认 200
             headers={"X-Custom-Header": "custom-value"}  # 可选，自定义响应头
         )
     ```

2. FileResponse（文件专用）

   - **作用**：返回文件（支持大文件、静态文件、下载文件）；

   - **场景**：返回 HTML / 图片 / 视频 / Excel 等文件；

   - 关键参数

     - `path`：文件路径（必填）；
     - `filename`：下载时显示的文件名（可选）；
     - `media_type`：手动指定 MIME 类型（比如 `media_type="application/pdf"`）；

   - 示例:

     ```python
     from fastapi.responses import FileResponse
     
     @app.get("/download/excel")
     def download_excel():
         excel_path = "./data/report.xlsx"
         # 返回文件并指定下载文件名
         return FileResponse(
             path=excel_path,
             filename="月度报表.xlsx",
             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
         )
     ```

3. HTMLResponse

   - **作用**：返回 HTML 字符串（直接渲染页面）；

   - **场景**：动态生成 HTML 内容（比如拼接变量到 HTML 中）；

   - 示例:

     ```python
     from fastapi.responses import HTMLResponse
     
     @app.get("/hello")
     def hello(name: str = "游客"):
         html_content = f"""
         <html>
             <body>
                 <h1>你好，{name}！</h1>
             </body>
         </html>
         """
         return HTMLResponse(content=html_content, status_code=200)
     ```

     > 注意：如果是返回静态 HTML 文件，优先用 `FileResponse`；动态生成 HTML 用 `HTMLResponse`。

     

4. PlainTextResponse

   - **作用**：返回纯文本格式的数据（非 JSON、非 HTML）；

   - **场景**：返回简单的文本提示、日志内容等；

   - 示例：

     ```python
     from fastapi.responses import PlainTextResponse
     
     @app.get("/text")
     def get_text():
         return PlainTextResponse(content="这是纯文本响应", status_code=200)
     ```

5. RedirectResponse

   - **作用**：实现页面重定向；

   - **场景**：登录成功后跳转到首页、旧接口重定向到新接口等；

   - 示例:

     ```python
     from fastapi.responses import RedirectResponse
     
     @app.get("/old-path")
     def redirect_old_path():
         # 重定向到 /new-path，状态码 307 表示临时重定向
         return RedirectResponse(url="/new-path", status_code=307)
     
     @app.get("/new-path")
     def new_path():
         return {"message": "这是新接口"}
     ```

6. StreamingResponse（流式响应）

   - **作用**：返回流式数据（逐块传输，不一次性加载到内存）；

   - **场景**：返回大文件、LLM 流式输出（比如 ChatGPT 逐字回复）、实时日志流等；

   - 示例（LLM 流式输出）：【测试：`curl http://localhost:8000/stream`】

     ```python
     from fastapi.responses import StreamingResponse
     import asyncio
     
     async def generate_stream():
         # 模拟流式输出（逐字返回）
         words = ["你", "好", "，", "这", "是", "流", "式", "响", "应"]
         for word in words:
             await asyncio.sleep(0.5)
             yield word.encode("utf-8")  # 流式输出需返回字节流
     
     @app.get("/stream")
     async def stream_response():
         return StreamingResponse(generate_stream(), media_type="text/plain")
     ```

   

7. Response（基础响应类）

   - **作用**：所有响应类的父类，用于自定义任意格式的响应；

   - **场景**：需要高度定制响应（比如自定义 MIME 类型、响应体格式）；

   - 示例：

     ```python
     from fastapi.responses import Response
     
     @app.get("/custom")
     def custom_response():
         # 返回二进制数据，指定自定义 MIME 类型
         return Response(
             content=b"custom binary data",
             media_type="application/octet-stream",
             status_code=200)
         
     ```

总结

1. `FileResponse` 是 FastAPI 专门用于**返回文件**的响应类，支持流式传输，适合静态文件 / 下载场景；
2. FastAPI 核心响应类型按场景分类：
   - 常规数据：`JSONResponse`（默认）；
   - 文件：`FileResponse`；
   - 动态 HTML：`HTMLResponse`；
   - 纯文本：`PlainTextResponse`；
   - 重定向：`RedirectResponse`；
   - 流式数据：`StreamingResponse`；
   - 自定义响应：`Response`（父类）；
3. 选择响应类型的核心原则：**匹配返回数据的格式和业务场景**（比如静态文件用 `FileResponse`，流式输出用 `StreamingResponse`）。

##### **示例 4: 静态资源托管**

托管静态资源，如HTML 页面、图片、css等

**验证是否成功：**在当前文件所在目录中创建一个`static`目录， 在`static`目录下放一个测试文件（如 `image.png`），创建 `mount_static.py` 并启动服务，访问 http://localhost:8000/static/image.png 应该能正常访问

`mount_static.py` 内容如下：

```python
# test/import/fastapi/mount_static.py

from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi import FastAPI, Request

app = FastAPI()

# 当前文件目录
BASE_DIR = Path(__file__).parent
print("当前文件目录：", BASE_DIR)
static_dir = BASE_DIR / "static"

# 挂载静态文件
# 第一个参数：所有以 /static 开头的请求都交给这个模块处理
# 第二个参数：指定静态文件的存放目录
# 第三个参数：给挂载点起个名字（路由的名字）
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
# 用户访问：http://localhost:8000/static/image.png
#      ↓
# FastAPI 看到 "/static" 开头
#      ↓
# 交给 StaticFiles 处理
#      ↓
# StaticFiles 去 {static_dir} 找文件
#      ↓
# 返回给用户

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# uv run uvicorn test.import.fastapi.mount_static:app --reload
```

##### 示例 5：跨域配置 

在上一步的 `static` 目录中创建一个前端页面 `front.html`，使用上一部的静态资源托管的方式访问，前端页面运行在 `8000` 端口 http://127.0.0.1:8000/static/frontend.html

```
<!DOCTYPE html>
<html>
<body>
    <h1>跨域测试</h1>
    <p>后端：http://localhost:8001/api/data</p>
    <button onclick="test()">点我请求</button>
    <pre id="r"></pre>

    <script>
        async function test() {
            const r = document.getElementById('r');
            try {
                const res = await fetch('http://localhost:8001/api/data');
                const data = await res.json();
                r.innerText = '✅ 成功：' + JSON.stringify(data);
            } catch (e) {
                r.innerText = '❌ 失败：' + e.message;
            }
        }
    </script>
</body>
</html>

```

创建一个后端服务 `backend_cors.py`，启动程序使其运行在 `8001` 端口

```python
# test/import/fastapi/backend_cors.py

from fastapi import FastAPI

import uvicorn
from starlette.middleware.cors import CORSMiddleware

app = FastAPI()

# ⚠️ 注意：这里先故意不配置 CORS！测试不跨域的效果
# ✅ 配置 CORS（允许跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源（开发环境方便测试）
    allow_credentials=True, # 允许携带 Cookie
    allow_methods=["*"],  # 允许所有 HTTP 方法（GET, POST, PUT, DELETE 等）
    allow_headers=["*"],  # 允许所有请求头
)

@app.get("/api/data")
async def get_data():
    return {"message": "这是后端数据", "status": "success"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)

# uv run uvicorn test.import.fastapi.backend_cors:app --reload --port 8001
```

通过前端的**“点我请求”**按钮访问后端，屏蔽掉跨域部分的代码，运行效果如下：

![image-20260401042318014](images/image-20260401042318014.png)

放开跨域部分的代码运行效果如下：

![image-20260401042410241](images/image-20260401042410241.png)



##### 示例 6：同步和异步

**下载文件**

同步方式下载文件：

```python
# test/import/fastapi/同步1.py

import time

def download_file(name):
    print(f"开始下载：{name}")
    time.sleep(2)  # 模拟下载耗时 2 秒
    print(f"下载完成：{name}")

download_file("文件 1")

```

异步方式下载文件：

```python
# test/import/fastapi/异步1.py
import asyncio


async def download_file(name):
    print(f"开始下载：{name}")
    await asyncio.sleep(2)  # 模拟下载耗时 2 秒
    print(f"下载完成：{name}")

asyncio.run(download_file("文件 1"))
```

**并发下载 3 个文件**

同步方式：

```python
# test/import/fastapi/同步1.py
import time

def download_file(name):
    print(f"开始下载：{name}")
    time.sleep(2)  # 模拟下载耗时 2 秒
    print(f"下载完成：{name}")

# 逐个下载
time_begin = time.time()
download_file("文件 1")
download_file("文件 2")
download_file("文件 3")
time_end = time.time()

# 总耗时：6 秒（2+2+2）
print(f"总耗时：{time_end - time_begin} 秒")

```

异步方式：

```python
# test/import/fastapi/异步2.py

import asyncio
import time


async def download_file(name):
    print(f"开始下载：{name}")
    await asyncio.sleep(2)  # 模拟下载耗时 2 秒
    print(f"下载完成：{name}")

async def main():
    # 三个任务同时开始！
    await asyncio.gather(
        download_file("文件 1"),
        download_file("文件 2"),
        download_file("文件 3")
    )

time_begin = time.time()
asyncio.run(main())
time_end = time.time()

# 总耗时：约 2 秒（同时进行）
print(f"总耗时：{time_end - time_begin} 秒")
```

**协程对象和运行协程：**

```python
import asyncio

# 1. 定义【异步函数】
async def my_task():
    await asyncio.sleep(1) #
    return "完成"

# 2. 调用异步函数时，返回的是【协程对象】
coroutine = my_task()  # 这是一个协程（还没执行）

# 3. 用 asyncio 来【运行协程】
asyncio.run(coroutine)  # 启动协程，得到结果

```

> **协程（Coroutine）** 是一种**轻量级的用户态线程**，也叫微线程，它是 Python 中实现**异步编程**的核心机制。
>
> 简单来说：
>
> 协程是**可以暂停执行、后续再恢复执行**的函数，它在单线程内实现多任务的并发切换，不需要操作系统参与调度，开销远小于线程 / 进程。
>
> 1. **本质**：单线程内的**协作式多任务**（任务主动让出执行权，而非被操作系统强制抢占）
>
> 2. 特点：
>
>    - 无需创建线程 / 进程，资源消耗极低
>    - 由程序自身控制切换，没有线程切换的开销
>    - 遇到 I/O 操作（网络请求、文件读写、数据库查询）时自动暂停，不阻塞主线程
>
>    
>
> 3. **适用场景**：高并发 I/O 密集型任务（爬虫、API 接口、WebSocket 等）

**FastAPI中的同步和异步**

创建文件：`test/import/fastapi/async_sync.py`

**场景 1：**简单返回数据（两种方式都可以）

```python
# \test\import\fastapi\async_sync.py

from fastapi import FastAPI

app = FastAPI()

# ✅ 异步版本
@app.get("/simple-async")
async def simple_async():
    return {"message": "Hello"}

# ✅ 同步版本（更简洁）
@app.get("/simple-sync")
def simple_sync():
    return {"message": "Hello"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# uv run uvicorn test.import.fastapi.async_sync:app --reload
```

**场景 2：**需要等待某个操作（必须用 async）

```python
# \test\import\fastapi\async.py

import asyncio

from fastapi import FastAPI

app = FastAPI()

# ✅ 正确：异步函数可以用 await
@app.get("/fetch-data")
async def fetch_data():
    # 模拟耗时操作（如查数据库）
    await asyncio.sleep(1) # 让出CPU
    return {"data": "完成"}

# ❌ 错误：同步函数不能用 await
@app.get("/fetch-data")
def fetch_data():  # 少了 async
    await asyncio.sleep(1)  # SyntaxError!
    return {"data": "完成"}

# ⚠️ 勉强能用但不好：同步函数做耗时操作会阻塞
@app.get("/fetch-data-bad")
def fetch_data_bad():
    import time
    time.sleep(1)  # 阻塞整个线程
    return {"data": "完成"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# uv run uvicorn test.import.fastapi.async:app --reload

```

**💡 FastAPI 中的最佳实践**
推荐：默认用 async

```python
from fastapi import FastAPI

app = FastAPI()

# ✅ 推荐：即使现在不需要 await，以后可能需要
@app.get("/users/{user_id}")
async def get_user(user_id: int):
    # 现在很简单
    return {"user_id": user_id}
    
    # 以后如果要查数据库，直接加 await 就行
    # user = await db.query(user_id)
    # return user

```

##### **示例 6: 后台任务 **

创建文件：`test/import/fastapi/bg_task.py`

展示如何在返回响应后继续执行耗时操作（如发送邮件、处理数据），避免阻塞用户。

```python
# \test\import\fastapi\bg_task.py
from fastapi import BackgroundTasks, FastAPI
import time

app = FastAPI()

# 定义一个模拟的耗时任务
def write_log(message: str):

    while True:
        print("正在执行任务..." + message)
        time.sleep(1)

@app.post("/send-task/{email}")
async def send_task(email: str, background_tasks: BackgroundTasks):
    # 1. 添加任务到后台队列
    background_tasks.add_task(write_log, f"发送通知： {email}")
    # 2. 立即返回响应给用户，不需要等待 write_log 执行完毕
    return {"message": "通知任务已发送"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# uv run uvicorn test.import.fastapi.bg_task:app --reload
```

##### **示例 7: 文件上传**

展示如何接收上传的文件，这是本项目最常用的功能。

```python
# test/import/fastapi/upload.py
from fastapi import FastAPI, File,UploadFile,HTTPException
from fastapi.responses import JSONResponse
import os

app = FastAPI()

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.post("/upload",summary="单个文件上传接口")
async def upload(
    file: UploadFile = File(
    ..., # 必填参数
    description="需要上传的文件（支持图片/文档等)",
    alias="upload_file", #前端参数的别名，默认文件名是file
    media_type="application/octet-stream"), #接受任何类型的文件（图片、文档、视频等）
    remark:str = None #可选参数
):

    try:
        # 1. 校验文件类型（示例：只允许上传图片）
        ALLOWED_TYPES = ["image/jpeg", "image/png", "image/gif"]
        if file.content_type not in ALLOWED_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"仅支持上传{ALLOWED_TYPES}类型的文件，当前文件类型：{file.content_type}")

        file_path = os.path.join(UPLOAD_FOLDER, file.filename)
        CHUNK_SIZE = 1024 * 1024  # 1MB分块
        with open(file_path, "wb") as f:
            # 分块读取大文件（避免内存溢出）
            while True:
                chunk = await file.read(CHUNK_SIZE)  # 每次读1MB
                if not chunk:
                    break
                f.write(chunk)
            """
            await的必要性：file.read()是异步函数，必须用await才能拿到文件内容，否则程序报错；
            分块读取的核心：给read()传一个字节数（如 1MB），循环读取 + 写入，避免大文件占满内存；
            用法选择：小文件可以用await file.read()一次性读取，大文件必须分块读取；
            """
        return JSONResponse(
            status_code=200,
            content={
                "code": 0,
                "msg": "文件上传成功",
                "data": {
                    "filename": file.filename,
                    "content_type": file.content_type,
                    "file_size": f"{file.size} 字节",  # 文件大小
                    "save_path": file_path,
                    "remark": remark or "无备注"
                }
            }
        )
    except Exception as e:
        # 异常捕获：返回友好的错误信息
        raise HTTPException(
            status_code=500,
            detail=f"文件上传失败：{str(e)}"
        )

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
```

`File()`的参数和`Form()`/`Query()`逻辑一致，核心常用配置如下：

|     参数      |                             作用                             |                示例                 |
| :-----------: | :----------------------------------------------------------: | :---------------------------------: |
|     `...`     |      表示**必填项**（必须传文件，不传则返回 422 错误）       |             `File(...)`             |
|    `None`     |            表示**可选项**（不传文件也能调用接口）            |            `File(None)`             |
| `description` |   接口文档中显示的描述（提升可读性，FastAPI 自动生成文档）   | `File(..., description="上传图片")` |
|    `alias`    | 前端传参的别名（比如前端用`file_upload`传，后端用`file`接收） |  `File(..., alias="file_upload")`   |
| `media_type`  |            限定文件的 MIME 类型（比如只允许图片）            |  `File(..., media_type="image/*")`  |
| `min_length`  |     限制文件内容最小字节数（很少用，一般在校验逻辑里做）     |    `File(..., min_length=1024)`     |
| `max_length`  | 限制文件内容最大字节数（比如限制 5MB：`max_length=5*1024*1024`） |   `File(..., max_length=5242880)`   |

### 6.2 web服务实现过程

**文件位置**:`app/import_process/api/file_import_service.py`

本节将展示完整的 Web 服务实现代码。该服务基于 FastAPI 构建，提供了文件上传、后台任务调度、状态查询以及静态页面服务功能。

#### 1. 依赖库 

在运行本服务前，请确保安装以下 Python 依赖库：

```bash
uv add install fastapi uvicorn python-dotenv minio python-multipart 
```

#### 2. 代码实现详解

我们将 `app/import_process/api/file_import_service.py` 的实现拆分为 6 个核心部分进行讲解，以便理解每个模块的作用。

##### (1) 引入依赖与环境配置

首先，导入必要的系统库、FastAPI 组件以及我们的工具类 (`minio_utils`, `task_utils`, `main_graph`)。同时加载 `.env` 环境变量。

```python
import os
import shutil
import uuid
from typing import List, Dict, Any
from datetime import datetime
import uvicorn
# 第三方库
from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
# 项目内部工具/配置/客户端
from app.clients.minio_utils import get_minio_client
from app.utils.path_util import PROJECT_ROOT
from app.utils.task_utils import (
    add_running_task,
    add_done_task,
    get_done_task_list,
    get_running_task_list,
    update_task_status,
    get_task_status,
)
from app.import_process.agent.state import get_default_state
from app.import_process.agent.main_graph import kb_import_app  # LangGraph全流程编译实例
from app.core.logger import logger  # 项目统一日志工具
```

##### (2) 应用初始化与跨域配置

初始化 FastAPI 应用，并配置 CORS（跨域资源共享）以允许前端调用。

```python
# 初始化FastAPI应用实例
# 标题和描述会在Swagger文档(http://ip:port/docs)中展示
app = FastAPI(
    title="File Import Service",
    description="Web service for uploading files to Knowledge Base (PDF/MD → 解析 → 切分 → 向量化 → Milvus/KG入库)"
)

# 跨域中间件配置：解决前端调用后端接口的跨域限制
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有前端域名访问（生产环境建议指定具体域名）
    allow_credentials=True,  # 允许携带Cookie等认证信息
    allow_methods=["*"],  # 允许所有HTTP方法（GET/POST/PUT/DELETE等）
    allow_headers=["*"],  # 允许所有请求头
)

# --------------------------
# 静态页面路由：返回文件导入前端页面import.html
# 访问地址：http://localhost:8000/import.html
# --------------------------
@app.get("/import.html", response_class=FileResponse)
async def get_import_page():
    """返回文件导入前端页面：import.html"""
    # 拼接HTML文件绝对路径，基于项目根目录定位
    html_abs_path = PROJECT_ROOT / "app/import_process/page/import.html"
    # 日志记录页面访问的文件路径，方便排查文件不存在问题
    logger.info(f"前端页面访问，文件绝对路径：{html_abs_path}")

    # 校验文件是否存在，不存在则抛出404异常
    if not os.path.exists(html_abs_path):
        logger.error(f"前端页面文件不存在，路径：{html_abs_path}")
        raise HTTPException(status_code=404, detail="import.html page not found")

    # 以FileResponse返回HTML文件，浏览器自动渲染
    return FileResponse(
        path=html_abs_path,
        media_type="text/html"  # 显式指定媒体类型为HTML，确保浏览器正确解析
    )
```

##### (3) 后台任务逻辑

这是连接 Web 服务与 LangGraph 的桥梁。`run_graph_task` 函数会在后台运行（不阻塞 HTTP 响应），它监听图的执行事件，并实时更新任务状态。

```python
# --------------------------
# 后台任务：LangGraph全流程执行
# 独立于主请求线程，由BackgroundTasks触发，避免阻塞接口响应
# --------------------------
def run_graph_task(task_id: str, local_dir: str, local_file_path: str):
    """
    LangGraph全流程执行后台任务
    核心流程：初始化状态 → 流式执行图节点 → 实时更新任务状态 → 异常捕获
    任务状态更新：pending → processing → completed/failed
    节点进度更新：每完成一个节点，将节点名加入done_list，供前端轮询查看

    :param task_id: 全局唯一任务ID，关联单个文件的全流程处理
    :param local_dir: 该任务的本地文件存储目录（含临时文件/解析结果）
    :param local_file_path: 上传文件的本地绝对路径
    """
    try:
        # 1. 更新任务全局状态为：处理中
        update_task_status(task_id, "processing")
        logger.info(f"[{task_id}] 开始执行LangGraph全流程，本地文件路径：{local_file_path}")

        # 2. 初始化LangGraph状态：加载默认状态 + 注入当前任务的核心参数
        init_state = get_default_state()
        init_state["task_id"] = task_id  # 任务ID关联
        init_state["local_dir"] = local_dir  # 任务本地目录
        init_state["local_file_path"] = local_file_path  # 上传文件本地路径

        # 3. 流式执行LangGraph全流程（stream模式：实时获取每个节点的执行结果）
        for event in KBImportWorkflow.create_and_run(init_state, stream=True):
        #for event in kb_import_app.stream(init_state):
            for node_name, node_result in event.items():
                # 记录每个节点完成的日志，包含任务ID和节点名，方便追踪执行顺序
                logger.info(f"[{task_id}] LangGraph节点执行完成：{node_name}")
                # 将完成的节点名加入【已完成列表】，前端轮询/status/{task_id}可实时获取
                add_done_task(task_id, node_name)

        # 4. 全流程执行完成，更新任务全局状态为：已完成
        update_task_status(task_id, "completed")
        logger.info(f"[{task_id}] LangGraph全流程执行完毕，任务完成")

    except Exception as e:
        # 5. 捕获全流程异常，更新任务全局状态为：失败，并记录错误日志（含堆栈）
        update_task_status(task_id, "failed")
        logger.error(f"[{task_id}] LangGraph全流程执行失败，异常信息：{str(e)}", exc_info=True)
```

##### (4) 文件上传接口 (/upload)

处理文件上传请求。它负责：

1. 生成全局唯一的 `task_id`。
2. 将文件保存到本地临时目录。
3. 上传文件到 MinIO 对象存储。
4. 启动后台任务 (`run_graph_task`) 开始处理。

```python
# --------------------------
# 核心接口：文件上传接口
# 支持多文件上传，核心流程：接收文件 → 本地保存 → MinIO上传 → 启动后台任务
# 访问地址：http://localhost:8000/upload （POST请求，form-data格式传参）
# --------------------------
@app.post("/upload", summary="文件上传接口", description="支持多文件批量上传，自动触发知识库导入全流程")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    文件上传核心接口
    1. 接收前端上传的多文件（PDF/MD为主）
    2. 按「日期/任务ID」分层保存到本地输出目录，避免文件冲突
    3. 将文件上传至MinIO对象存储，做持久化保存
    4. 为每个文件生成唯一TaskID，启动独立的LangGraph后台处理任务
    5. 实时更新任务状态，供前端轮询监控进度

    :param background_tasks: FastAPI后台任务对象，用于异步执行LangGraph流程
    :param files: 前端上传的文件列表（form-data格式）
    :return: 包含上传结果和所有任务ID的JSON响应
    """
    # 1. 构建本地存储根目录：项目根目录/output/YYYYMMDD（按日期分层，方便管理）
    date_based_root_dir = os.path.join(PROJECT_ROOT / "output", datetime.now().strftime("%Y%m%d"))
    # 初始化任务ID列表，用于返回给前端（一个文件对应一个TaskID）
    task_ids = []

    # 2. 遍历处理每个上传的文件（多文件批量处理，各自独立生成TaskID）
    for file in files:
        # 生成全局唯一TaskID（UUID4），作为单个文件的全流程标识
        task_id = str(uuid.uuid4())
        task_ids.append(task_id)
        logger.info(f"[{task_id}] 开始处理上传文件，文件名：{file.filename}，文件类型：{file.content_type}")

        # 3. 标记「文件上传」阶段为「运行中」，前端轮询可查
        add_running_task(task_id, "upload_file")

        # 4. 构建该任务的本地独立目录：output/YYYYMMDD/TaskID，避免多文件重名冲突
        task_local_dir = os.path.join(date_based_root_dir, task_id)
        os.makedirs(task_local_dir, exist_ok=True)  # 目录不存在则创建，存在则不做处理
        # 构建上传文件的本地保存绝对路径
        local_file_abs_path = os.path.join(task_local_dir, file.filename)

        # 5. 将上传的文件保存到本地临时目录（后续MinIO上传/文件解析均基于此文件）
        with open(local_file_abs_path, "wb") as file_buffer:
            shutil.copyfileobj(file.file, file_buffer)
        logger.info(f"[{task_id}] 文件已保存至本地，路径：{local_file_abs_path}")

        # 6. 将本地文件上传至MinIO对象存储，做持久化保存
        # 从环境变量获取MinIO的PDF存储目录配置
        minio_pdf_base_dir = os.getenv("MINIO_PDF_DIR", "pdf_files")  # 缺省值：pdf_files
        # 构建MinIO中的文件对象名：配置目录/YYYYMMDD/文件名（按日期分层，和本地一致）
        minio_object_name = f"{minio_pdf_base_dir}/{datetime.now().strftime('%Y%m%d')}/{file.filename}"
        try:
            # 获取MinIO客户端实例
            minio_client = get_minio_client()
            if minio_client is None:
                # MinIO客户端获取失败，抛出500服务异常
                raise HTTPException(status_code=500,
                                    detail="MinIO service connection failed, please check MinIO config")
            # 从环境变量获取MinIO的桶名配置
            minio_bucket_name = os.getenv("MINIO_BUCKET_NAME", "kb-import-bucket")  # 缺省值：kb-import-bucket

            # 本地文件上传至MinIO（同名文件会自动覆盖，保证文件最新）
            minio_client.fput_object(
                bucket_name=minio_bucket_name,
                object_name=minio_object_name,
                file_path=local_file_abs_path,
                content_type=file.content_type  # 传递文件原始MIME类型
            )
            logger.info(f"[{task_id}] 文件已成功上传至MinIO，桶名：{minio_bucket_name}，对象名：{minio_object_name}")
        except Exception as e:
            # MinIO上传失败，记录警告日志（不中断后续流程，本地文件仍可继续处理）
            logger.warning(f"[{task_id}] 文件上传MinIO失败，将继续执行本地处理流程，异常信息：{str(e)}", exc_info=True)

        # 7. 标记「文件上传」阶段为「已完成」，前端轮询可查
        add_done_task(task_id, "upload_file")

        # 8. 将LangGraph全流程处理加入FastAPI后台任务（异步执行，不阻塞当前接口响应）
        background_tasks.add_task(run_graph_task, task_id, task_local_dir, local_file_abs_path)
        logger.info(f"[{task_id}] 已将LangGraph全流程加入后台任务，任务已启动")

    # 9. 所有文件处理完毕，返回上传成功信息和所有TaskID（前端基于TaskID轮询进度）
    logger.info(f"多文件上传处理完毕，共处理{len(files)}个文件，生成TaskID列表：{task_ids}")
    return {
        "code": 200,
        "message": f"Files uploaded successfully, total: {len(files)}",
        "task_ids": task_ids
    }
```

##### (5) 任务状态查询接口 (/status)

前端轮询此接口以获取进度。它直接从内存中读取由 `task_utils` 维护的任务状态。

```python
# --------------------------
# 核心接口：任务状态查询接口
# 前端轮询此接口获取单个任务的处理进度和状态
# 访问地址：http://localhost:8000/status/{task_id} （GET请求）
# --------------------------
@app.get("/status/{task_id}", summary="任务状态查询", description="根据TaskID查询单个文件的处理进度和全局状态")
async def get_task_progress(task_id: str):
    """
    任务状态查询接口
    前端轮询此接口（如每秒1次），获取任务的实时处理进度
    返回数据均来自内存中的任务管理字典（task_utils.py），高性能无IO

    :param task_id: 全局唯一任务ID（由/upload接口返回）
    :return: 包含任务全局状态、已完成节点、运行中节点的JSON响应
    """
    # 构造任务状态返回体
    task_status_info: Dict[str, Any] = {
        "code": 200,
        "task_id": task_id,
        "status": get_task_status(task_id),  # 任务全局状态：pending/processing/completed/failed
        "done_list": get_done_task_list(task_id),  # 已完成的节点/阶段列表
        "running_list": get_running_task_list(task_id)  # 正在运行的节点/阶段列表
    }
    # 记录状态查询日志，方便追踪前端轮询情况
    logger.info(
        f"[{task_id}] 任务状态查询，当前状态：{task_status_info['status']}，已完成节点：{task_status_info['done_list']}")
    return task_status_info
```

##### (6) 启动入口

配置 Uvicorn 服务器启动参数。包含一段针对 Windows/PyCharm 环境下 `asyncio` 事件循环的兼容性补丁。

```python
# --------------------------
# 服务启动入口
# 直接运行此脚本即可启动FastAPI服务，无需额外执行uvicorn命令
# --------------------------
if __name__ == "__main__":
    """服务启动入口：本地开发环境直接运行"""
    logger.info("File Import Service 服务启动中...")
    # 启动uvicorn服务，绑定本地IP和8000端口，关闭自动重载（生产环境建议用workers多进程）
    uvicorn.run(
        app=app,
        host="127.0.0.1",  # 仅本地访问，生产环境改为0.0.0.0（允许所有IP访问）
        port=8000  # 服务端口
    )
```

#### 3. 接口与 Task 列表关系详解

本服务通过 `app.utils.task_utils` 模块维护了一个内存中的任务状态列表，实现了前后端的状态同步。

1.  **上传阶段 (`/upload`)**:
    *   请求到达时，生成 `task_id`。
    *   调用 `add_running_task(task_id, "upload_file")`：此时前端查询状态，会看到 "开始上传文件" 正在运行。
    *   文件上传 MinIO 成功后，调用 `add_done_task(task_id, "upload_file")`：此时前端会看到 "开始上传文件" 变为已完成。

2.  **处理阶段 (`run_graph_task`)**:
    *   后台任务启动，调用 `update_task_status(task_id, "processing")`：标记任务整体正在处理中。
    *   LangGraph 每执行完一个节点（如 PDF 转 Markdown），流式输出会捕获到事件。
    *   调用 `add_done_task(task_id, node_name)`：将该节点标记为已完成。前端轮询时，进度条或日志列表会相应更新。

3.  **完成阶段**:
    *   图执行结束，调用 `update_task_status(task_id, "completed")`。
    *   前端收到 completed 状态，提示用户导入成功。


### 6.3 页面导入配置

**文件位置**: `app/import_process/page/import.html`

这是一个简洁的原生 HTML/JS 页面，实现了以下功能：

1.  **文件拖拽/选择**：支持 PDF 和 MD 文件。
2.  **上传进度条**：显示文件上传到服务器的进度。
3.  **状态轮询**：上传成功后，通过 `setInterval` 每 2 秒请求一次 `/status` 接口。
4.  **日志展示**：根据后端返回的 `done_list` 和 `running_list`，动态渲染任务执行日志（如 "node_entry已完成", "node_pdf_to_md正在进行..."）。

### 6.4 服务启动与测试流程

#### 1. 启动服务

在项目根目录下（`knowledge_base`），运行以下命令：

```bash
# 方式一：直接运行 Python 模块
✅ 直接执行脚本中的 if __name__ == "__main__" 代码块
✅ 会启动内置的 uvicorn（第 233 行）
❌ 没有热重载：代码修改后需要手动重启
✅ 适合简单测试
python -m app.import_process.api.file_import_service

# 方式二：使用 uvicorn 命令
✅ 热重载：代码修改后自动重启
✅ 生产级 ASGI 服务器
✅ 支持多进程：--workers 4
✅ 开发环境首选
uv run uvicorn app.import_process.api.file_import_service:app --host 0.0.0.0 --port 8000 --reload
```

看到 `Application startup complete` 即表示启动成功。



前端页面：http://localhost:8000/import.html
API 文档：http://localhost:8000/docs
上传接口：http://localhost:8000/upload

#### 2. 页面测试

1.  打开浏览器访问：`http://127.0.0.1:8000/import.html`
2.  点击上传区域，选择一个测试文件（如 `doc/hak180产品安全手册.pdf`）。
3.  **观察页面交互**：
    *   状态变为 "上传中..." -> "处理中..."。
    *   点击 "日志（点击展开）"，可以看到节点逐个执行的过程。
    *   等待所有节点执行完毕，状态变为 "已完成" (绿色)。

#### 3. 验证结果

*   **MinIO**: 检查文件是否已上传到对应日期的 bucket 中。
*   **Milvus**: 使用 Attu 查看 `kb_chunks` 集合，确认是否新增了该文件的向量数据。

通过以上步骤，我们完成了从后端逻辑实现到 Web 服务集成，再到前端可视化操作的完整闭环！