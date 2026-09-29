# 掌柜智库项目日记 · Day 04 —— 导入流程节点 1~7 完整实现

> 📅 记录日期：2026-09-20 ~ 2026-09-21
> 🖥️ 服务器：腾讯云轻量应用服务器 4核8G，Ubuntu 22.04 LTS
> 👤 操作用户：`ubuntu`（普通用户）为主，root 仅在装系统软件时临时使用
> 📁 服务器代码：`/home/ubuntu/project/ZGzhiku/code/knowledge_base`
> 🎯 今日目标：重建 processor/ 基础设施 + 实现节点1~节点7（PDF→MD→图片→切分→主体识别→向量化→Milvus入库）
> ✅ 完成状态：**100% 达成**，节点 1~7 全部通过测试，kb_item_names + kb_chunks 集合已建且数据入库

---

## 📊 项目整体进度

### 掌柜智库（RAG 知识库问答系统）—— 10 天完成计划

| 阶段 | 任务 | 状态 | 完成日期 | 备注 |
|------|------|------|---------|------|
| **Day 01** | 环境准备：服务器基础 + Docker + 三大中间件 | ✅ 已完成 | 2026-09-04 | 见 day01.md |
| **Day 02** | Python 环境搭建：uv + 依赖 + 项目骨架代码 | ✅ 已完成 | 2026-09-04 | 见 day02.md |
| **Day 03** | 配置文件 + .env + 中间件连接测试 | ✅ 提前完成 | 2026-09-04 | 与 Day 02 合并完成 |
| **Day 04** | 数据导入：节点1入口节点 → 节点7存入Milvus | ✅ **已完成** | 2026-09-21 | 本文档 |
| **Day 05** | 组装导入主图（LangGraph 编排节点1~7） | ⏳ 待开始 | - | - |
| **Day 06~07** | 检索链路 7 节点 | ⏳ 待开始 | - | - |
| **Day 08~09** | 重排序 + 答案生成 + SSE + 对话历史 | ⏳ 待开始 | - | - |
| **Day 10** | Web 服务 + 全流程联调 | ⏳ 待开始 | - | - |

### 今日成果速览

| 节点 | 功能 | 耗时 | 验证结果 |
|------|------|------|---------|
| 节点1 NodeEntry | 文件后缀判断路由 | 10 分钟 | ✅ 3 用例全 PASS |
| 节点2 NodePDFToMD | MinerU PDF 转 MD（异步轮询） | 45 秒/文件 | ✅ 输出 `_result.zip` + 解压目录 + MD 文件 |
| 节点3 NodeMDImg | VLM 图片摘要 + MinIO 上传替换 | 2 分钟（5 张图） | ✅ 输出 `_new.md`，图片路径替换为 MinIO URL |
| 节点4 NodeDocumentSplit | 标题切分 + 超长递归切 + 过短合并 | 毫秒级 | ✅ 733 行 → 33 个 Chunk |
| 节点5 NodeItemNameRecognition | LLM 识别商品名 + 双向量生成 + Milvus 入库 | 5 秒 | ✅ 识别 `AolynkCB304nCable网桥`，`kb_item_names` 集合已建 |
| 节点6 NodeBGEEmbedding | DashScope 双向量 API（dense+sparse） | 30 秒 | ✅ 33 chunk 全部含 dense(1024维) + sparse |
| 节点7 NodeImportMilvus | kb_chunks 建表 + 幂等插入 + chunk_id 回填 | 5 秒 | ✅ Attu 可见 `kb_chunks` 集合 33 条数据 |

---

## 目录

- [一、开工前检查：processor/ 被删除后的重建](#一开工前检查processor-被删除后的重建)
- [二、基础设施重建（6 个文件）](#二基础设施重建6-个文件)
- [三、节点2：PDF 转 Markdown（MinerU 异步轮询）](#三节点2pdf-转-markdownmineru-异步轮询)
- [四、节点3：图片处理（VLM + MinIO）](#四节点3图片处理vlm--minio)
- [五、节点4：文档切分（标题优先 + 递归切）](#五节点4文档切分标题优先--递归切)
- [六、节点5：主体识别（LLM + 双向量 + Milvus）](#六节点5主体识别llm--双向量--milvus)
- [七、节点6：切片向量化（DashScope 双向量 API）](#七节点6切片向量化dashscope-双向量-api)
- [八、节点7：存入 Milvus（kb_chunks 集合）](#八节点7存入-milvuskb_chunks-集合)
- [九、踩坑记录（8 个新坑）](#九踩坑记录8-个新坑)
- [十、架构发现与决策](#十架构发现与决策)
- [十一、知识收获（小白进阶）](#十一知识收获小白进阶)
- [十二、明日计划](#十二明日计划)

---

## 一、开工前检查：processor/ 被删除后的重建

用户删除了 `processor/` 文件夹，但保留了 `config/`、`tool/`、`utils/` 中的部分工具文件。开工前先盘点现状：

| 目录/文件 | 状态 | 说明 |
|----------|------|------|
| `.env` | ✅ 完好 | 全 API 方案配置齐全 |
| `pyproject.toml` | ✅ 完好 | 依赖齐全 |
| `.venv/` | ✅ 完好 | 虚拟环境已存在 |
| `config/` | ✅ 完好 | 含 lm_config / milvus_config / minio_config |
| `tool/logger.py` | ✅ 完好 | 全局彩色日志 |
| `processor/` | ❌ **已删除** | 需要重建 |
| `utils/task_utils.py` | ✅ 完好 | 任务追踪 |
| `utils/sse_utils.py` | ✅ 完好 | SSE 推送 |
| `utils/minio_utils.py` | ✅ 完好 | MinIO 客户端单例 |
| `utils/milvus_utils.py` | ✅ 完好 | Milvus 客户端 + 混合检索 |
| `utils/embedding_utils.py` | ✅ 完好 | DashScope 原生 API 双向量生成 |

**决策**：基础设施文件全部按原始代码风格重建（用 `config/` 和 `tool/logger`），不再引入新的配置单例体系——避免双配置源混淆。

---

## 二、基础设施重建（6 个文件）

按 day02 确立的 BaseNode 模板方法模式，重建以下文件：

### 2.1 目录结构

```bash
cd /home/ubuntu/project/ZGzhiku/code/knowledge_base

mkdir -p processor/import_processor/nodes
mkdir -p processor/import_processor/prompt
touch processor/__init__.py
touch processor/import_processor/__init__.py
touch processor/import_processor/nodes/__init__.py
touch processor/import_processor/prompt/__init__.py
```

### 2.2 6 个核心文件

| 文件 | 作用 | 关键设计 |
|------|------|---------|
| `processor/import_processor/exceptions.py` | 自定义异常类 | ImportProcessError 基类 + 10 个子类（StateFieldError / ConfigurationError / PdfConversionError 等） |
| `processor/import_processor/import_config.py` | 配置单例（读取 .env） | 与 `config/` 包并存，供 BaseNode 使用 |
| `processor/import_processor/state.py` | TypedDict 状态定义 | GRAPH_DEFAULT_STATE + get_default_state() 返回 deepcopy |
| `processor/import_processor/base.py` | 节点基类 BaseNode | ABC + `__call__` 统一日志/任务追踪/异常包装；setup_logging() |
| `processor/import_processor/nodes/node_enrty.py` | 节点1 入口节点 | **文件名保持 enrty 拼写**（原始代码如此，测试文件按此 import） |
| `processor/import_processor/prompt/item_name_recognition.py` | 商品名识别提示词 | System Prompt + User Template |

### 2.3 BaseNode 模板方法模式

```python
class BaseNode(ABC):
    name: str = "base_node"

    def __call__(self, state: T) -> T:
        try:
            self.logger.info(f"--- {self.name} 开始啦 ---")
            add_running_task(state["task_id"], self.name)
            result = self.process(state)           # 子类只写 process()
            add_done_task(state["task_id"], self.name)
            self.logger.info(f"--- {self.name} 完成啦 ---")
            return result
        except Exception as e:
            raise ImportProcessError(...)

    @abstractmethod
    def process(self, state: T) -> T: ...
```

> 💡 子类只管写 `process()` 方法，日志、任务追踪、异常包装全由基类的 `__call__` 统一处理——这叫"环绕切面"，是 LangGraph 节点的最佳实践。

---

## 三、节点2：PDF 转 Markdown（MinerU 异步轮询）

### 3.1 核心流程

```
本地PDF → ①POST 申请上传链接 → ②PUT 上传 → ③轮询任务状态（每3秒） → ④下载 ZIP → ⑤解压取 full.md
```

### 3.2 MinerU API 两段式调用

**第一段**：`POST /file-urls/batch` 申请上传凭证（返回 batch_id + 预签名 URL）

```python
data = {"files": [{"name": "xxx.pdf"}], "model_version": "vlm"}
# 返回：{"batch_id": "xxx", "file_urls": ["https://signed-url..."]}
```

**第二段**：直接 `PUT` 到预签名 URL（不带 Token）上传文件

```python
with open(pdf_path, 'rb') as f:
    requests.put(signed_url, data=f)
```

> 💡 预签名 URL 是 AWS S3 / 阿里云 OSS 通用模式：服务端生成带时效的一次性上传凭证，客户端直连存储，不经过服务端转发——安全性高（凭证有时效）、服务端压力小。

### 3.3 轮询状态机

| MinerU 返回的 state | 含义 | 处理 |
|---------------------|------|------|
| `waiting-file` | 文件刚上传，还在排队 | sleep 3s 继续 |
| `processing` | 正在解析 | sleep 3s 继续 |
| `done` | ✅ 完成 | 返回 `full_zip_url` |
| `failed` | ❌ 失败 | 抛 `PdfConversionError(err_msg)` |
| 超时 600s | 轮询太久 | 抛 `TimeoutError` |

### 3.4 实际运行结果

```
2026-09-21 16:17:00 - 上传文件成功!
2026-09-21 16:17:01 - [任务轮询] 处理中...... 已耗时: 0s，状态：waiting-file
2026-09-21 16:17:04 - [任务轮询] 解析完成, 总耗时: 3s
2026-09-21 16:17:05 - [ZIP下载] 下载成功 → 解压完成 → full.md 重命名为 xxx.md
2026-09-21 16:17:05 - --- node_pdf_to_md 完成啦 ---
```

**产出**：`output/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册/` 目录，含 MD 文件 + `images/` 图片目录。

### 3.5 运行方式约定

```bash
# ✅ 正确：用 -m 模块方式运行（Python 自动把当前目录加 sys.path）
uv run python -m processor.import_processor.nodes.node_pdf_to_md

# ❌ 错误：直接 python xxx.py（sys.path 不含项目根，绝对 import 找不到 processor 包）
uv run python processor/import_processor/nodes/node_pdf_to_md.py
```

---

## 四、节点3：图片处理（VLM + MinIO）

### 4.1 核心流程

```
扫描 MD 中图片引用 → VLM(qwen3-vl-flash) 生成中文摘要 → 上传 MinIO → 替换路径为 MinIO URL
```

### 4.2 图片引用格式问题（重要！）

MinerU 转换 PDF 时，图片在 MD 中可能是 **两种格式**：

```markdown
<!-- 格式1：标准 Markdown（课程预期） -->
![描述](images/xxx.jpg)

<!-- 格式2：HTML <img> 标签（MinerU 实际输出） -->
<img src="images/xxx.jpg"/>
```

**原始代码只匹配格式1**，导致图片全被报"未在 MD 中找到"。修复方法：`_find_image_in_md` 和 `_process_md_file` 同时匹配两种格式：

```python
# Markdown 格式正则
md_pattern = re.compile(r"!\[.*?\]\(.*?" + re.escape(image_file) + r".*?\)")
# HTML 格式正则（新增）
html_pattern = re.compile(
    r'<img\s+[^>]*?src=".*?' + re.escape(image_file) + r'.*?"[^>]*/?>',
    re.IGNORECASE
)
```

### 4.3 速率限制（滑动窗口算法）

DashScope API 有 QPM（每分钟请求数）限制，本项目 `requests_per_minute=15`：

```python
def _apply_api_rate_limit(self, request_times, max_requests, window_seconds=60):
    current_time = time.time()
    # 清理窗口内过期请求
    while request_times and current_time - request_times[0] >= window_seconds:
        request_times.popleft()
    # 窗口已满 → 等待
    if len(request_times) >= max_requests:
        sleep_duration = window_seconds - (current_time - request_times[0])
        if sleep_duration > 0:
            time.sleep(sleep_duration)
    request_times.append(current_time)
```

5 张图 + QPM=15 → 不会触发等待，15 张以上才需要等。

### 4.4 实际运行结果

```
2026-09-21 16:40:16 - node_md_img 请求成功，当前60s窗口内请求次数为1
... (5 次，每 3 秒一次，httpx 显示 POST 200 OK)
2026-09-21 16:42:22 - --- node_md_img 完成啦 ---
# _new.md 已生成，图片路径替换为 http://服务器IP:9000/knowledge-base/images/AolynkCB304nCable网桥用户手册-5W100-整本手册/xxx.jpg
```

### 4.5 MinIO 控制台访问

| 项 | 值 |
|---|---|
| **控制台地址** | `http://服务器IP:9001`（**不是 localhost！**） |
| **账号** | `minioadmin` |
| **密码** | `minioadmin123` |
| **桶名** | `knowledge-base` |
| **API 端口** | 9000（代码用） |

---

## 五、节点4：文档切分（标题优先 + 递归切）

### 5.1 切分策略（三层）

```
第一层：按 MD 标题初切（# ## ###）→ 82 章节
第二层：超长章节递归切分（RecursiveCharacterTextSplitter）→ 85 初始子 Chunk
第三层：过短章节合并（同父标题 + <500字）→ 33 最终 Chunk
```

### 5.2 关键配置

```python
max_content_length: int = 2000   # 单个 Chunk 最大长度
min_content_length: int = 500    # 过短合并阈值
overlap_sentences: int = 1       # 句子重叠
```

### 5.3 LangChain 递归分割器

```python
splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,
    chunk_overlap=0,
    separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
)
```

**工作原理**：从粗到细依次尝试分隔符——先用空行切，还超长就用换行切，再超长用句号切...直到最后空格硬切。

### 5.4 代码块识别

MD 代码块里的 `#` 开头注释**不是标题**。用 `in_code_block` 标志位跳过代码块内的 `#`：

```python
code_block_marker_match = re.match(r'^(`{3,}|~{3,})$', stripped_line)
if code_block_marker_match:
    if not in_code_block:
        in_code_block = True
        code_block_start_marker = marker
    elif stripped_line == code_block_start_marker:
        in_code_block = False
        code_block_start_marker = None
```

### 5.5 实际运行结果

```
--- 文档粗切完成，共82个章节，标题数81，文本共733行
--- 超长章节切分：## 附录 – 产品术语 → 4个子Chunk
--- 步骤4-1：超长章节切分完成，共生成85个初始子Chunk
--- 步骤4-2：过短章节合并完成，最终33个Chunk
步骤6：Chunk结果备份成功，路径：.../chunks.json
```

**产出**：`output/.../chunks.json`（33 个 Chunk，每个含 title / content / parent_title / part / file_title）。

---

## 六、节点5：主体识别（LLM + 双向量 + Milvus）

### 6.1 核心流程

```
提取前3个Chunk → LLM(qwen-flash) 识别商品名 → 回填到每个Chunk → 
DashScope API 生成 dense(1024维) + sparse(稀疏) 双向量 → 存入 Milvus kb_item_names 集合
```

### 6.2 双向量方案说明

| 向量类型 | DashScope API | Milvus 字段 | 索引类型 | 度量方式 |
|---------|--------------|------------|---------|---------|
| 稠密 | text-embedding-v4 原生 API (output_type=dense&sparse) | dense_vector | IVF_FLAT | COSINE |
| 稀疏 | 同上 | sparse_vector | SPARSE_INVERTED_INDEX | IP (L2归一化后等价COSINE) |

> 💡 原始代码用本地 BGE-M3 生成双向量。本项目改为 DashScope 原生 API 生成双向量——**保留了混合检索架构，但去掉了 torch/FlagEmbedding 等 GB 级依赖**，服务器 4核8G 就能跑。

### 6.3 Milvus 集合 Schema（kb_item_names）

| 字段 | 类型 | 说明 |
|------|------|------|
| pk | INT64 (auto_id) | 自增主键 |
| file_title | VARCHAR(100) | 文件标题（**max_length=100，超长文件名会报错**） |
| item_name | VARCHAR(100) | 商品名称 |
| dense_vector | FLOAT_VECTOR(1024) | 稠密向量 |
| sparse_vector | SPARSE_FLOAT_VECTOR | 稀疏向量 |

### 6.4 幂等性设计

```python
if not milvus_client.has_collection(collection_name):   # 没有才创建
    self._create_item_name_collection(...)
milvus_client.delete(filter=f"file_title=='{escaped_title}'")  # 先删旧数据
milvus_client.insert(data=data)                                 # 再插新数据
```

同一份文件重复导入不会产生重复数据。

### 6.5 实际运行结果

```
2026-09-21 19:14:11 - HTTP Request: POST https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions "HTTP/1.1 200 OK"
2026-09-21 19:14:14 - --- 识别完成: AolynkCB304nCable网桥 ---
2026-09-21 19:14:14 - --- node_item_name_recognition 完成啦 ---
```

**Milvus 数据验证**：

```bash
uv run python -c "
from utils.milvus_utils import get_milvus_client
client = get_milvus_client()
print(client.query(collection_name='kb_item_names', filter=\"file_title like '%Aolynk%'\", output_fields=['file_title', 'item_name']))
"
# 输出: data: [{'pk': 468847145679404438, 'file_title': 'Aolynk CB304n Cable网桥 用户手册-5W100-整本手册', 'item_name': 'AolynkCB304nCable网桥'}]
```

### 6.6 LLM 兜底设计

```python
def _step_3_call_llm(self, file_title, context):
    if not context:
        return file_title          # 无上下文 → 直接用文件名
    try:
        llm = ChatOpenAI(model=lm_config.llm_model, ...)
        response = llm.invoke(messages)
        item_name = response.content.replace(" ", "").replace("\n", "")
        if not item_name:
            return file_title      # LLM 返回空 → 用文件名
        return item_name
    except Exception as e:
        logger.error(f"大模型调用异常：{e}")
        return file_title          # 调用失败 → 用文件名
```

**三级兜底保证主流程永不中断**——商品名识别只是辅助，识别不出来也照样入库（用文件名顶替）。

---

## 七、节点6：切片向量化（DashScope 双向量 API）

> 📁 `processor/import_processor/nodes/node_bge_embedding.py`　⏱️ 30 秒　✅ 33 chunk 全部含 dense(1024维) + sparse

**与原始代码差异**：本地 BGE-M3 + FlagEmbedding → DashScope text-embedding-v4 API（`output_type="dense&sparse"`），去掉 torch 等 GB 级依赖，4核8G CPU 零压力。

**核心三步**：
1. 输入校验：chunks 非空且为 list（否则抛 `StateFieldError`）
2. 批量向量化（`batch_size=6`，避免超 DashScope 单次 10 条上限）：文本构造 `f"{item_name}\n{content}"`（商品名前置增强语义）→ 调 `generate_embeddings()` 拿 dense+sparse → 绑定回 chunk
3. 状态更新：带向量的 chunks 回传 state

**`__main__` 关键修改**：路径改 Linux + 加 `task_id="task_test_006"` + 用 `file_title` 兜底给每个 chunk 补 `item_name`（真实流程由节点5 LLM 识别）。

**运行**：`cd /home/ubuntu/project/ZGzhiku/code/knowledge_base && uv run python -m processor.import_processor.nodes.node_bge_embedding`

输出：`chunks_count=33, dense_vector_dim=1024, sparse_vector_keys_count=48`

---

## 八、节点7：存入 Milvus（kb_chunks 集合）

> 📁 `processor/import_processor/nodes/node_import_milvus.py`　⏱️ 5 秒　✅ Attu 可见 33 条数据

**五步串行流程（一步一校验）**：
1. 输入校验：chunks + `dense_vector` + `sparse_vector` 字段完整 + 提取向量维度
2. 集合准备：`kb_chunks` 不存在则自动建 Schema + 索引
3. 幂等清理：按 `file_title` 删旧数据（`escape_milvus_string` 转义防 filter 解析失败）
4. 批量插入：`client.insert()` + 回填 Milvus 自增 `chunk_id`
5. 状态更新：回填后的 chunks 回传 state

**kb_chunks Schema（9 字段）**：

| 字段 | 类型 | 说明 |
|------|------|------|
| chunk_id | INT64, pk, auto_id | 自增主键 |
| content | VARCHAR(65535) | 切片内容 |
| title / parent_title | VARCHAR(100) | 切片标题 / 父标题 |
| part | INT8 | 分片编号（默认 0） |
| file_title | VARCHAR(100) | 源文件标题（幂等性依据） |
| item_name | VARCHAR(100) | 商品名称 |
| sparse_vector | SPARSE_FLOAT_VECTOR | 稀疏向量 |
| dense_vector | FLOAT_VECTOR, dim=1024 | 稠密向量 |

**索引设计**：dense_vector → AUTOINDEX + COSINE（语义检索）；sparse_vector → SPARSE_INVERTED_INDEX + IP（稀疏专用，`DAAT_MAXSCORE` 算法）

**`__main__` 关键修改**：路径改 Linux + 加 `task_id="task_test_007"` + 内联调 `generate_embeddings()`（用 chunks.json 模拟节点6 输出，batch_size=3 保守避限流）+ 兜底 `if "part" not in item: item["part"] = 0`。

**运行**：`cd /home/ubuntu/project/ZGzhiku/code/knowledge_base && uv run python -m processor.import_processor.nodes.node_import_milvus`

输出：`chunks_inserted=33, collection_name=kb_chunks`（chunk_id 自增回填首末两条）

Attu 验证：浏览器 `http://服务器IP:7000` → 连接 `standalone:19530` → Collections 可见 `kb_chunks`（33 Rows）。

---

## 九、踩坑记录（8 个新坑）

### ❌ 踩坑1：`ModuleNotFoundError: No module named 'processor'`

**现象**：`uv run python processor/import_processor/nodes/node_pdf_to_md.py` 报找不到 processor 包。

**原因**：直接运行 `python xxx.py` 时，Python 把**脚本所在目录**（`processor/import_processor/nodes/`）加入 `sys.path`，而不是项目根目录。绝对导入 `from processor.xxx import` 当然找不到。

**解决**：用 `python -m` 模块方式运行：
```bash
uv run python -m processor.import_processor.nodes.node_pdf_to_md
```
`-m` 告诉 Python "把当前目录作为包根"，自动把项目根加入 `sys.path`。

### ❌ 踩坑2：`KeyError: 'task_id'`

**现象**：节点运行时 `base.py` 第 74 行 `add_running_task(state["task_id"], self.name)` 抛 KeyError。

**原因**：`__main__` 测试块的 `init_state` 里缺 `task_id` 字段。BaseNode 的 `__call__` 方法硬读 `state["task_id"]`，不管 `task_utils` 是否会用到。

**解决**：**所有节点的 `__main__` 测试块**必须包含 `task_id`：
```python
init_state = {
    "task_id": "task_test_002",   # ← 必须有！
    "pdf_path": "...",
    ...
}
```

### ❌ 踩坑3：原始代码的 `__main__` 用 Windows 路径

**现象**：复制原始代码的 `__main__` 块后，`init_state["pdf_path"] = r"D:\output\..."` 在 Linux 上找不到文件。

**原因**：原始作者本地是 Windows，测试路径是本地路径，直接搬到 Linux 服务器上当然找不到。

**解决**：所有 `__main__` 块的文件路径**必须改成服务器上的真实路径**（`/home/ubuntu/project/ZGzhiku/code/knowledge_base/doc/xxx.pdf`）。

### ❌ 踩坑4：图片在 MD 中找不到

**现象**：节点3 日志显示"图片 xxx.jpg 未在 MD 文档中找到"，所有图片都被跳过，`_new.md` 不生成。

**原因**：MinerU 转 MD 时用了 **HTML `<img src="..."/>` 标签**，而不是标准 Markdown `![]()` 格式。原始代码的正则只匹配 Markdown 格式。

**解决**：`_find_image_in_md` 和 `_process_md_file` 同时匹配两种格式：
```python
# 新增 HTML 格式正则
html_pattern = re.compile(r'<img\s+[^>]*?src=".*?' + re.escape(file) + r'.*?"[^>]*/?>', re.IGNORECASE)
```

### ❌ 踩坑5：MinIO 控制台 localhost vs 服务器 IP

**现象**：服务器上代码能连 MinIO（`localhost:9000`），但从本地浏览器打不开控制台。

**原因**：`.env` 里 `MINIO_ENDPOINT=localhost:9000` 是**服务器本地**的地址。浏览器在本地电脑，`localhost` 指的是本地电脑，不是服务器。

**解决**：浏览器访问时用**服务器公网 IP**：`http://服务器IP:9001`（控制台端口 9001，不是 API 端口 9000）。

### ❌ 踩坑6：误判 config/tool 包不存在

**现象**：LS 工具返回异常导致误判"项目没有 config/ 和 tool/ 包"，差点改 milvus_utils.py 的 import。

**原因**：Glob/LS 工具偶发返回异常路径（Windows 风格的反斜杠），用 Read 直接按已知路径读才能确认。

**解决**：遇到 LS 返回异常时，**用 Glob 限定 pattern 或 Read 直接读已知路径**验证，不要急于下结论改代码。

---

## 十、架构发现与决策

### 8.1 双配置体系并存

项目现在有两套配置体系，都读同一个 `.env`，值完全一致，混用不报错：

| 体系 | 文件 | 使用者 |
|------|------|--------|
| 原始代码风格 | `config/lm_config.py`、`config/milvus_config.py`、`config/minio_config.py` + `tool/logger.py` | `milvus_utils.py`、节点5 往后 |
| 本项目单例 | `import_config.py` 的 `get_config()` | 节点1~4（BaseNode 强依赖） |

**决策**：节点5 往后贴近原始代码风格写（用 `lm_config` / `milvus_config`），不再回改已跑通的节点1~4。

### 8.2 DashScope text-embedding-v4 双向量

原始代码用本地 BGE-M3 生成稠密+稀疏双向量。本项目发现 DashScope **原生 API**（不是 OpenAI 兼容模式）支持 `output_type="dense&sparse"`，可以云端生成双向量。

```python
# DashScope 原生 API 端点（不是 compatible-mode/v1）
url = "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding"
```

**好处**：保留了混合检索架构（稠密+稀疏加权融合），但去掉了 torch/FlagEmbedding 等 GB 级依赖。4核8G 服务器零压力。

### 8.3 文件命名约定

| 约定 | 说明 | 原因 |
|------|------|------|
| `node_enrty.py`（enrty 不是 entry） | 节点1 文件名 | 原始代码拼写，测试文件按此 import，不能改 |
| 输出 `_new.md` 而非覆盖 | 节点3 处理后的 MD | 保留原始 MD 方便对比调试 |
| chunks.json 备份 | 节点4 切分结果 | 与 MD 同目录，方便后续节点读取 |

---

## 十一、知识收获（小白进阶）

| 知识点 | 一句话总结 |
|--------|-----------|
| `python -m` vs `python xxx.py` | `-m` 把当前目录当包根，绝对 import 能找到兄弟包；直接跑脚本只会把脚本目录加 sys.path |
| 预签名 URL | 服务端生成带时效的一次性上传凭证，客户端直连存储，安全且解压服务端压力 |
| 异步轮询 | 云端 AI 任务通用模式——提交任务 → 隔几秒问一次好了没 → 避免长连接超时 |
| 正则 HTML 标签匹配 | `<img\s+[^>]*?src="..."[^>]*/?>` + `re.IGNORECASE`，兼容自闭合和属性顺序 |
| 滑动窗口限速 | 双端队列维护请求时间戳，窗口内超上限则等待，API 限流通用解法 |
| LangChain RecursiveCharacterTextSplitter | 从粗到细依次尝试分隔符（段落→换行→句号→空格），超长文本智能切分 |
| LangGraph 增量合并 | 节点返回 dict（不是整个 state），返回的键自动合并进全局状态 |
| Milvus 混合检索 | 稠密+稀疏双向量分别检索 → WeightedRanker 加权融合 → 比纯稠密更准 |
| 双向量 API 方案 | DashScope 原生 API 支持云端生成 dense&sparse，保留混合检索架构但零本地依赖 |

---

## 十二、明日计划

| 顺序 | 任务 | 对应笔记 | 要点 |
|------|------|---------|------|
| 1 | 组装导入主图 | 笔记03/11 | LangGraph 编排节点1~7 + 条件路由（pdf 分支走节点2~7，md 分支跳过节点2） |
| 2 | 端到端导入测试 | - | 一个 PDF 从头跑到 Attu 可见 `kb_chunks` 数据 = **项目 30% 里程碑** 🎯 |
| 3 | 检索链路 7 节点 | 笔记12~18 | 向量检索 → HyDE → 网络搜索 → RRF 融合 → Rerank |

---

## 💪 给其他小白的话

1. **原始代码是"骨架"，不是"成品"**——`__main__` 测试块的路径、task_id 必须按你的服务器环境改，直接复制必踩坑。
2. **遇到"找不到模块"先想 sys.path**——`python -m` 是包内模块运行的标准做法，别用 `sys.path.insert` 这种 hack。
3. **正则匹配要考虑多种格式**——MinerU 输出 `<img>` 而不是 `![]()` 格式，这种"同一功能的不同实现"在真实项目里天天遇到。
4. **先验证工具函数，再写节点**——单独跑 `embedding_utils.py` 测 DashScope API 是否通，比节点跑到一半才报错省时间。
5. **保留原始代码的文件命名**——`node_enrty.py` 的拼写虽然奇怪，但测试文件和后续 import 都按这个名字写了，改了全局崩。
