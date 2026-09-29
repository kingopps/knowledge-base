# 掌柜智库项目日记 · Day 02 —— Python 环境搭建全过程

> 📅 记录日期：2026-09-04
> 🖥️ 服务器：腾讯云轻量应用服务器 4核8G，Ubuntu 22.04 LTS
> 👤 操作用户：`ubuntu`（普通用户）为主，root 仅在装系统软件时临时使用
> 📁 本地代码：`F:\Download\ai大模型\sgg项目\知识类\09Project实战\掌柜智库\05-初始代码\knowledge_base\knowledge_base`
> 📁 服务器代码：`/home/ubuntu/project/ZGzhiku/code/knowledge_base`
> 🎯 今日目标：Python 3.11 + uv 虚拟环境 + 依赖安装 + .env 配置 + 三大中间件连通验证 + DashScope API 打通
> ✅ 完成状态：**100% 达成**，还提前完成了 Day 03 全部内容和 Day 04 的节点1（入口节点）

---

## 📊 项目整体进度

### 掌柜智库（RAG 知识库问答系统）—— 10 天完成计划

| 阶段 | 任务 | 状态 | 完成日期 | 备注 |
|------|------|------|---------|------|
| **Day 01** | 环境准备：服务器基础 + Docker + 三大中间件 | ✅ 已完成 | 2026-09-04 | 见 day01.md |
| **Day 02** | Python 环境搭建：uv + 依赖 + 项目骨架代码 | ✅ **已完成** | 2026-09-04 | 本文档 |
| **Day 03** | 配置文件 + .env + 中间件连接测试 | ✅ **提前完成** | 2026-09-04 | 与 Day 02 合并完成 |
| **Day 04** | 数据导入：节点1入口节点已完成，PDF转MD待做 | 🔄 进行中 | - | 提前开工 🚀 |
| **Day 05** | 检索链路：问题改写 + HyDE + 向量检索 + RRF 融合 | ⏳ 待开始 | - | - |
| **Day 06** | 重排序：DashScope Rerank API + Top-K 筛选 | ⏳ 待开始 | - | - |
| **Day 07** | 答案生成：Prompt 组装 + LLM 调用 + SSE 流式输出 | ⏳ 待开始 | - | - |
| **Day 08** | 对话历史：MongoDB 存储 + 历史窗口裁剪 | ⏳ 待开始 | - | - |
| **Day 09** | Web 服务：FastAPI + 前后端联调测试 | ⏳ 待开始 | - | - |
| **Day 10** | 全流程测试 + 优化 + 项目总结 | ⏳ 待开始 | - | - |

### 今日成果速览

| 板块 | 状态 | 验证结果 |
|------|------|---------|
| Python 3.11 + uv 虚拟环境 | ✅ | `uv sync`：Resolved 68 packages |
| .env 服务器版配置 | ✅ | 全 API 方案，Key 正常加载（前缀 sk-ws-） |
| Milvus 向量库连通 | ✅ | localhost:19530 |
| MongoDB 连通 | ✅ | localhost:27017，ping 通过 |
| MinIO 连通 + 创建桶 | ✅ | localhost:9000，桶 `knowledge-base` 已创建 |
| DashScope API 真实调用 | ✅ | qwen-flash 成功回复（通义千问） |
| 入口节点 NodeEntry（提前量） | 🔄 | 代码已写好，单元测试待运行 |

---

## 目录

- [一、动手前的差异分析](#一动手前的差异分析重要)
- [二、完整执行步骤](#二完整执行步骤可复现)
- [三、踩坑记录（核心价值）](#三踩坑记录本文档核心价值)
- [四、Day 04 提前量：入口节点 NodeEntry](#四day-04-提前量入口节点-nodeentry)
- [五、最终检查清单](#五最终检查清单)
- [六、知识收获](#六知识收获小白进阶)
- [七、明日计划](#七明日计划day-04-正式)

---

## 一、动手前的差异分析（重要！）

本地初始代码是 **Windows + 本地 GPU 模型**方案，直接搬到服务器跑不了。动手前先盘点 6 个差异：

| # | 问题 | 影响 | 对策 |
|---|------|------|------|
| 1 | 服务器默认 Python 3.10，项目要求 ≥3.11 | 依赖装不上 | 安装 Python 3.11（uv 也能自动下载管理版本） |
| 2 | pyproject.toml 缺少 `pymilvus` | 无法连接 Milvus | `uv add pymilvus` |
| 3 | .env 是 Windows 路径 + CUDA + 本地 BGE 模型 | 服务器没有 GPU | 改用 DashScope 全 API 方案 |
| 4 | .env 里 MinIO 地址是 `192.168.100.100` | 连不上容器 | 改为 `localhost:9000` |
| 5 | 本地 `.venv` 是 Windows 版虚拟环境 | 服务器不可用 | 不上传，服务器上重建 |
| 6 | .env 第 48 行有乱码字符 `卸` | 可能解析出错 | 删除 |

> 💡 **方法论**：换运行环境前，先列出「这个环境有什么、那个环境没有什么」，比装到一半报错再回头查快得多。

---

## 二、完整执行步骤（可复现）

### Step 1：安装 Python 3.11 + uv（服务器，ubuntu 用户）

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# 安装 uv（Rust 写的极速包管理器，pip 的替代品，快 10-100 倍）
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc

uv --version   # 输出 uv 0.12.9 即成功
```

> 💡 uv 会自动下载并管理 Python 版本——即使系统没有 3.11，`uv sync` 时也能自动拉取对应版本，这是它比 pip 省心的地方。

### Step 2：上传项目代码（本地 PowerShell）

```powershell
# 先在服务器创建目录
ssh ubuntu@服务器IP "mkdir -p ~/project/ZGzhiku/code"

# 上传（注意：本地的 .venv 是 Windows 版，不要上传，或上传后删除）
scp -r "F:\Download\ai大模型\sgg项目\知识类\09Project实战\掌柜智库\05-初始代码\knowledge_base\knowledge_base" ubuntu@服务器IP:~/project/ZGzhiku/code/
```

上传后检查：`ls ~/project/ZGzhiku/code/knowledge_base/` 能看到 `processor/ test/ pyproject.toml .env` 等。

### Step 3：配置 uv 清华镜像 + 添加 pymilvus（服务器）

```bash
# 一行命令创建全局镜像配置（所有 uv 项目永久生效）
mkdir -p ~/.config/uv && printf '[[index]]\nurl = "https://pypi.tuna.tsinghua.edu.cn/simple"\ndefault = true\n' > ~/.config/uv/uv.toml

# 验证配置
cat ~/.config/uv/uv.toml

cd ~/project/ZGzhiku/code/knowledge_base && uv add pymilvus
```

### Step 4：创建服务器版 .env（最关键一步）

```bash
cd ~/project/ZGzhiku/code/knowledge_base
cp .env .env.bak        # 先备份原始文件！
nano .env               # 全部替换为下面的模板
```

.env 模板（**全 API 方案**，无需任何本地模型）：

```ini
# ===== DashScope API =====
OPENAI_API_KEY=sk-ws-xxxxxxxx（你的真实Key）
OPENAI_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_DEFAULT_MODEL=qwen-flash
LLM_DEFAULT_TEMPERATURE=0.1
VL_MODEL=qwen3-vl-flash
ITEM_MODEL=qwen-flash

# ===== Embedding =====
EMBEDDING_DIM=1024
EMBEDDING_MODEL=text-embedding-v4

# ===== Rerank =====
RERANK_MODEL=gte-rerank

# ===== Milvus =====
MILVUS_URL=http://localhost:19530
CHUNKS_COLLECTION=kb_chunks
ITEM_NAME_COLLECTION=kb_item_names
MILVUS_METRIC_TYPE=COSINE
MILVUS_MIN_COSINE_SCORE=0.75

# ===== MongoDB =====
MONGO_URL=mongodb://localhost:27017
MONGO_DB_NAME=kb001

# ===== MinIO =====
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_NAME=knowledge-base

# ===== 其他 =====
MD_ROOT_DIR=./temp-files/
MODEL=qwen-flash
MCP_DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse
```

⚠️ 两处必改：① `OPENAI_API_KEY` 换成真实 Key；② `MINIO_SECRET_KEY` 必须和容器实际密码一致（查法见踩坑5）。

### Step 5：同步依赖

```bash
uv sync
# 输出：Resolved 68 packages in 1ms / Checked 65 packages in 2ms（全部就位）
```

### Step 6：验证 .env 加载 + 三大中间件连通（一键脚本）

```bash
cd ~/project/ZGzhiku/code/knowledge_base && uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv(override=True)
print('Milvus :', os.getenv('MILVUS_URL'))
print('Mongo  :', os.getenv('MONGO_URL'))
print('MinIO  :', os.getenv('MINIO_ENDPOINT'))
print('Key前缀:', os.getenv('OPENAI_API_KEY','未设置')[:6])

from pymilvus import connections
connections.connect(host='localhost', port='19530')
print('✅ Milvus 连接成功'); connections.disconnect('default')

from pymongo import MongoClient
c = MongoClient(os.getenv('MONGO_URL'), serverSelectionTimeoutMS=3000)
c.admin.command('ping'); print('✅ MongoDB 连接成功'); c.close()

from minio import Minio
m = Minio(os.getenv('MINIO_ENDPOINT'), access_key=os.getenv('MINIO_ACCESS_KEY'),
          secret_key=os.getenv('MINIO_SECRET_KEY'), secure=False)
print('✅ MinIO 连接成功, 现有桶:', [b.name for b in m.list_buckets()] or '(空)')
"
```

### Step 7：DashScope 真实调用 + 创建 MinIO 桶

```bash
cd ~/project/ZGzhiku/code/knowledge_base && uv run python -c "
import os
from dotenv import load_dotenv
load_dotenv(override=True)
from openai import OpenAI
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'), base_url=os.getenv('OPENAI_API_BASE'))
resp = client.chat.completions.create(
    model=os.getenv('LLM_DEFAULT_MODEL'),
    messages=[{'role':'user','content':'用一句话回答：你是什么模型？'}]
)
print('✅ LLM 调用成功:', resp.choices[0].message.content)

from minio import Minio
m = Minio(os.getenv('MINIO_ENDPOINT'), access_key=os.getenv('MINIO_ACCESS_KEY'),
          secret_key=os.getenv('MINIO_SECRET_KEY'), secure=False)
bucket = os.getenv('MINIO_BUCKET_NAME')
if not m.bucket_exists(bucket):
    m.make_bucket(bucket); print(f'✅ 已创建桶: {bucket}')
else:
    print(f'✅ 桶已存在: {bucket}')
"
```

**实际输出**：`✅ LLM 调用成功: 我是通义千问（Qwen），是阿里巴巴集团旗下的通义实验室自主研发的超大规模语言模型。` + `✅ 已创建桶: knowledge-base`

---

## 三、踩坑记录（本文档核心价值）

### ❌ 踩坑1：apt update 报 Permission denied

```
E: Could not open lock file /var/lib/apt/lists/lock - open (13: Permission denied)
```
**原因**：ubuntu 是普通用户，装系统软件需要 root 权限。
**解决**：`sudo apt update`；需要连续执行多条系统命令时 `sudo -i` 切 root。
**判断技巧**：提示符 `$` = 普通用户，`#` = root。

### ❌ 踩坑2：root 和 ubuntu 是两个独立的"世界"（本日最大坑！）

**现象**：ubuntu 下 `uv --version` 报 `Command not found`，切到 root 却有 `uv 0.12.9`。
**原因**：uv 之前是在 root 身份下装的，安装在 `/root/.local/bin/`，ubuntu 用户的 PATH 里根本没有这个路径，而且 `/root` 目录普通用户无权访问。
**解决**：退回 ubuntu（`exit`），以 ubuntu 身份重新安装 uv，以后项目操作全部用 ubuntu。
**分工原则**（记住这张表，一劳永逸）：

| 操作 | 用什么身份 |
|------|-----------|
| 装系统软件（apt/docker） | root（`sudo -i` 或 `sudo xxx`） |
| 项目代码、uv、跑服务 | ubuntu |
| Docker 容器管理 | ubuntu（`sudo usermod -aG docker ubuntu` 后重登生效） |

### ❌ 踩坑3：~ 符号在不同用户下指向不同目录

**现象**：root 下 `cd ~/project/ZGzhiku/code/knowledge_base` 报 `No such file or directory`。
**原因**：`~` 不是固定路径！ubuntu 的 `~` = `/home/ubuntu`，root 的 `~` = `/root`。项目在 ubuntu 家目录里，root 用 `~` 当然找不到。
**解决**：回到 ubuntu 用户操作项目；或 root 下写绝对路径 `/home/ubuntu/project/...`。

### ❌ 踩坑4：uv add 极慢 → 配置清华镜像

**现象**：`uv add pymilvus` 卡住不动。
**原因**：默认走 PyPI 官方源（服务器在国外）。
**解决**：见 Step 3 的一行命令创建 `~/.config/uv/uv.toml`，速度提升 10 倍以上。
**注意**：`printf` 单行命令写入，避免多行粘贴错位（day01 踩坑4 的教训复用）。

### ❌ 踩坑5：docker inspect minio 报 no such object

**现象**：查 MinIO 密码时报 `error: no such object: minio`。
**原因**：容器名实际是 `zg-minio` 不是 `minio`。
**排查命令**：`docker ps -a --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"`（`-a` 显示所有容器含已停止的）。
**正确查密码**：
```bash
docker inspect zg-minio --format '{{.Config.Env}}' | tr ' ' '\n' | grep MINIO_ROOT
# 输出：MINIO_ROOT_USER=minioadmin / MINIO_ROOT_PASSWORD=minioadmin123
```
**对应关系**：容器里的 `MINIO_ROOT_USER/PASSWORD` = .env 里的 `MINIO_ACCESS_KEY/SECRET_KEY`。

### ❌ 踩坑6：uv add 第二次执行"没有输出"

**现象**：配置镜像后重跑 `uv add pymilvus`，秒完成且无任何输出，怀疑失败。
**真相**：第一次虽然慢，但已经装好了；第二次 uv 发现无新任务，直接静默通过。
**三种验证方法**：
```bash
grep pymilvus pyproject.toml        # ① 依赖声明里有
uv pip list | grep -i milvus        # ② 已装进虚拟环境
uv run python -c "import pymilvus; print(pymilvus.__version__)"   # ③ 能导入
```

### ❌ 踩坑7：config.py 读的变量名和 .env 不一致

**发现过程**：读初始代码 `config.py`，发现 `default_model` 读的是 `os.getenv("MODEL")`，而 .env 里写的是 `LLM_DEFAULT_MODEL` → 程序会拿到空字符串，后续调 LLM 必报错。
**解决**：`.env` 补一行 `MODEL=qwen-flash`。
**教训**：**拿到初始代码先通读配置加载逻辑，让 .env 适配代码，而不是凭感觉写 .env。**

### ❌ 踩坑8：EMBEDDING_DIM 维度问题

原 .env 写 1536（OpenAI 维度），但 DashScope `text-embedding-v4` 默认输出 **1024 维**（与课程 BGE-M3 一致）。维度不一致会导致将来建 Milvus 集合时字段定义对不上。
**解决**：`sed -i 's/^EMBEDDING_DIM=1536/EMBEDDING_DIM=1024/' .env`

### ❌ 踩坑9：FinalShell 粘贴多行文本显示错位

**现象**：粘贴验证脚本后输出里出现 `)rint(...)` 这种诡异内容。
**真相**：只是**显示错位**，实际执行的代码是完整的，结果正确。
**对策**：多行内容优先用 heredoc 写成文件再执行，或用 VS Code Remote-SSH 直接编辑。

### ⚠️ 提示10：PyMilvusDeprecationWarning 不是错误

```
PyMilvusDeprecationWarning: `connections.connect` is an ORM-style PyMilvus API and will be removed in PyMilvus 3.1.
```
这是"未来会弃用"的预告。课程代码用的就是 ORM 风格 API，照常写，等真正升级 pymilvus 再迁移到 `MilvusClient`。

---

## 四、Day 04 提前量：入口节点 NodeEntry

### 发现：初始代码的 node_enrty.py 是"占位实现"

不管传什么文件都硬编码返回 `is_md_read_enabled: True` —— 这是课程故意留白，留给我们写的第一个逻辑。

### 我的实现（已写入服务器）

```python
# processor/import_processor/nodes/node_enrty.py
class NodeEntry(BaseNode):
    name = "node_entry"

    def process(self, state: ImportGraphState):
        import_file_path = state.get("import_file_path", "").strip()
        if import_file_path.endswith(".pdf"):
            return {"is_pdf_read_enabled": True, "is_md_read_enabled": False}
        if import_file_path.endswith(".md"):
            return {"is_pdf_read_enabled": False, "is_md_read_enabled": True}
        return {"is_pdf_read_enabled": False, "is_md_read_enabled": False}
```

### 单元测试（test/test_node_entry.py）

3 个用例：`说明书.pdf → pdf=True`、`笔记.md → md=True`、`表格.docx → 全 False`。
运行：`uv run python test/test_node_entry.py`（⏳ 待执行）

### 顺带学到的 3 个知识点

1. **LangGraph 增量合并**：节点返回 dict（而不是整个 state），LangGraph 自动把返回的键合并进全局状态。
2. **抽象基类 ABC**：`BaseNode` 的 `@abstractmethod process` 强制所有子类必须实现 process，规范先行。
3. **`__call__` 魔术方法**：`node(state)` 自动触发 `__call__` → 统一打日志 + 调 process + 异常包装成 `ImportProcessError`。子类只管写业务，日志/异常基类全包。

---

## 五、最终检查清单

- ✅ Python 3.11 + uv 0.12.9（ubuntu 用户）
- ✅ uv 清华镜像配置（~/.config/uv/uv.toml）
- ✅ 项目代码上传至 /home/ubuntu/project/ZGzhiku/code/knowledge_base
- ✅ pymilvus 添加（共 68 个依赖就位）
- ✅ .env 服务器版（DashScope 全 API + localhost 三件套 + minioadmin123）
- ✅ .env.bak 备份留存
- ✅ Milvus / MongoDB / MinIO 三大中间件连通验证通过
- ✅ DashScope qwen-flash 真实调用成功
- ✅ MinIO 桶 knowledge-base 创建成功
- ✅ ubuntu 已加入 docker 组（docker 免 sudo）
- 🔄 NodeEntry 单元测试待运行

---

## 六、知识收获（小白进阶）

| 知识点 | 一句话总结 |
|--------|-----------|
| 用户与权限 | 系统级操作用 root/sudo，项目操作用普通用户，别混 |
| `~` 的含义 | 当前用户的家目录，换用户就换指向 |
| uv | pip+venv 的极速替代：uv add / uv sync / uv run |
| 镜像源 | 国内必配清华源，一行 printf 搞定 |
| OpenAI 兼容协议 | DashScope 兼容 /v1 格式，换服务商只改 base_url 和 key，代码零改动 |
| 全 API 方案 | 向量化/Rerank 走 DashScope 云端，不下载 GB 级模型，服务器 4核8G 足够 |
| docker inspect | 查容器真实环境变量/配置的瑞士军刀 |
| 配置即代码 | .env 与代码分离；代码读什么变量名，.env 就写什么变量名 |

---

## 七、明日计划（Day 04 正式）

1. ⏳ 运行 `test_node_entry.py`，确认 3 用例全 PASS
2. ⏳ 节点2：PDF 转 Markdown（MinerU API 注册 + 异步轮询 + 解压）
3. ⏳ 节点3：图片处理（Qwen3-VL 生成摘要 + MinIO 上传替换路径）
4. ⏳ 节点4：文档切分（标题层级 + 递归切分）

---

## 💪 给其他小白的话

1. **换环境先做差异分析**：列出两边环境差异清单再动手，比边装边报错省一半时间。
2. **身份是 Linux 第一课**：root 和普通用户的"世界"互相隔离，先想清楚"我现在是谁"再敲命令。
3. **没有输出 ≠ 失败**：先验证（grep / pip list / import 三连），再下结论。
4. **报错先看容器名对不对**：`docker ps -a` 永远是你的第一步。
5. **读初始代码的 config 加载逻辑**：让 .env 适配代码，别让代码适配你的 .env。
