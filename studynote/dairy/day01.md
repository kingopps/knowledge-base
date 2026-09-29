# 掌柜智库项目环境搭建全过程（小白友好版）

> 📅 记录日期：2026-09-04
> 🖥️ 服务器：腾讯云轻量应用服务器 4核8G，Ubuntu 22.04 LTS
> 👤 当前用户：`ubuntu`（普通用户，非 root）
> 📁 项目目录：`/home/ubuntu/project/ZGzhiku`
> 🎯 目标：完成 Milvus（向量数据库）+ 独立 MinIO（对象存储）+ MongoDB（文档数据库）三大中间件的部署

---

## 📊 项目整体进度

### 掌柜智库（RAG 知识库问答系统）—— 10 天完成计划

| 阶段 | 任务 | 状态 | 完成日期 | 备注 |
|------|------|------|---------|------|
| **Day 01** | 环境准备：服务器基础 + Docker + 三大中间件 | ✅ **已完成** | 2026-09-04 | 本文档 |
| **Day 02** | Python 环境搭建：uv + 依赖 + 项目骨架代码 | ⏳ 待开始 | - | - |
| **Day 03** | 配置文件 + .env + 中间件连接测试 | ⏳ 待开始 | - | - |
| **Day 04** | 数据导入：PDF 上传 + 切片 + 向量化 + 入库 Milvus | ⏳ 待开始 | - | - |
| **Day 05** | 检索链路：问题改写 + HyDE + 向量检索 + RRF 融合 | ⏳ 待开始 | - | - |
| **Day 06** | 重排序：DashScope Rerank API + Top-K 筛选 | ⏳ 待开始 | - | - |
| **Day 07** | 答案生成：Prompt 组装 + LLM 调用 + SSE 流式输出 | ⏳ 待开始 | - | - |
| **Day 08** | 对话历史：MongoDB 存储 + 历史窗口裁剪 | ⏳ 待开始 | - | - |
| **Day 09** | Web 服务：FastAPI + 前后端联调测试 | ⏳ 待开始 | - | - |
| **Day 10** | 全流程测试 + 优化 + 项目总结 | ⏳ 待开始 | - | - |

### 三大中间件部署状态（Day 01 成果）

```
✅ Docker 已安装 + 镜像加速已配置
✅ Milvus 全家桶（etcd + 内置 MinIO + standalone + Attu）—— 4 容器 healthy
✅ 独立 MinIO（存 PDF/图片）—— 运行中
✅ MongoDB（存对话历史）—— 运行中
```

| 中间件 | 容器名 | 端口 | 验证方式 | 状态 |
|--------|--------|------|---------|------|
| Milvus etcd | milvus-etcd | 内部 2379 | - | ✅ healthy |
| Milvus 内置 MinIO | milvus-minio | 9002/9003 | - | ✅ healthy |
| Milvus 主服务 | milvus-standalone | 19530 | Attu 已连上 | ✅ healthy |
| Milvus Attu | milvus-attu | 7000 | http://IP:7000 | ✅ Up |
| 独立 MinIO | zg-minio | 9000/9001 | http://IP:9001 | ✅ Up |
| MongoDB | zg-mongo | 27017 | mongosh ping | ✅ Up |

---

## 目录

- [一、准备工作清单](#一准备工作清单)
- [二、服务器基础配置](#二服务器基础配置)
  - [2.1 安全组端口开放](#21-安全组端口开放)
  - [2.2 ❌ 踩坑1：apt update 权限拒绝](#22--踩坑1apt-update-权限拒绝)
  - [2.3 Docker 安装](#23-docker-安装)
  - [2.4 ❌ 踩坑2：Docker socket 权限问题](#24--踩坑2docker-socket-权限问题)
  - [2.5 ❌ 踩坑3：Docker 镜像加速配置格式错误](#25--踩坑3docker-镜像加速配置格式错误)
- [三、项目目录结构规划](#三项目目录结构规划)
- [四、离线镜像包导入](#四离线镜像包导入)
  - [4.1 上传 tar 包到服务器](#41-上传-tar-包到服务器)
  - [4.2 ❌ 踩坑4：批量加载命令多行粘贴失败](#42--踩坑4批量加载命令多行粘贴失败)
- [五、Milvus 向量数据库部署](#五milvus-向量数据库部署)
  - [5.1 修改 docker-compose.yml](#51-修改-docker-composeyml)
  - [5.2 启动 Milvus 全家桶](#52-启动-milvus-全家桶)
  - [5.3 ❌ 踩坑5：Milvus 内置 MinIO 与独立 MinIO 端口冲突](#53--踩坑5milvus-内置-minio-与独立-minio-端口冲突)
  - [5.4 Attu 浏览器验证](#54-attu-浏览器验证)
- [六、独立 MinIO + MongoDB 部署](#六独立-minio--mongodb-部署)
  - [6.1 ❌ 踩坑6：docker run 多行命令粘贴失败](#61--踩坑6docker-run-多行命令粘贴失败)
  - [6.2 独立 MinIO 启动（存 PDF/图片）](#62-独立-minio-启动存-pdf图片)
  - [6.3 MongoDB 启动（存对话历史）](#63-mongodb-启动存对话历史)
  - [6.4 ❓ 疑问：MongoDB 浏览器打不开？](#64--疑问mongodb-浏览器打不开)
- [七、最终成果检查清单](#七最终成果检查清单)
- [八、踩坑总结 Top 8](#八踩坑总结-top-8)

---

## 一、准备工作清单

在动手之前，请确认以下事项全部到位：

| 序号 | 项目 | 说明 | 确认 |
|------|------|------|------|
| 1 | 云服务器 | 腾讯云/阿里云轻量应用服务器，**最低 4核8G** | ✅ |
| 2 | 操作系统 | Ubuntu 22.04 LTS 或 CentOS 7.9 | ✅ |
| 3 | 公网 IP | 服务器分配的固定公网 IP（例：139.199.80.37） | ✅ |
| 4 | SSH 工具 | 推荐 Windows Terminal / Xshell / VS Code Remote SSH | ✅ |
| 5 | 离线镜像包 | 6 个 tar 文件（见第五节） | ✅ |
| 6 | 稳定网络 | 服务器网络正常（用 `ping baidu.com` 测试） | ✅ |

### 1. 完成步骤清单

**Day 01 环境搭建逐步完成情况**：

✅ 1.1 在腾讯云控制台拿到「公网IP」和「密码」
✅ 1.2 配置安全组（开放项目需要的端口：22/7000/9000/9001/19530/27017/8000-8001）
✅ 1.3 本地安装远程连接工具（Windows Terminal / FinalShell / Xshell 任选）
✅ 1.4 用远程工具成功连上服务器（`ssh ubuntu@公网IP`）
✅ 1.5 更新系统包：`sudo apt update && sudo apt upgrade -y`
✅ 1.6 在服务器上安装 Docker（官方脚本 + Aliyun 镜像加速）
✅ 1.7 解决 Docker socket 权限问题：`sudo usermod -aG docker $USER` 后重登
✅ 1.8 配置 Docker 镜像加速（用 Python 生成合法 daemon.json）
✅ 1.9 创建项目目录结构：`~/project/ZGzhiku/deploy/{milvus,data,offline_images,logs}`
✅ 1.10 上传 6 个离线 tar 镜像包到服务器 offline_images 目录
✅ 1.11 批量导入 Docker 镜像：`for f in *.tar; do docker load -i "$f"; done`
✅ 1.12 修改 docker-compose.yml（数据卷改绝对路径 + 删除 Attu TLS 挂载 + Milvus 内置 MinIO 端口改 9002/9003）
✅ 1.13 启动 Milvus 全家桶：`docker compose up -d`（4 容器均 healthy）
✅ 1.14 Attu 浏览器验证：`http://IP:7000` 成功连接 Milvus
✅ 1.15 启动独立 MinIO：`docker run -d --name zg-minio ...`（端口 9000/9001）
✅ 1.16 独立 MinIO 浏览器验证：`http://IP:9001` 用 minioadmin 登录成功
✅ 1.17 启动 MongoDB：`docker run -d --name zg-mongo ...`（端口 27017）
✅ 1.18 MongoDB 健康检查：`docker exec zg-mongo mongosh --eval "db.runCommand({ping: 1})"` 返回 `{ ok: 1 }`
✅ 1.19 验证 6 个容器全部 Up：`docker ps`

---

## 二、服务器基础配置

### 2.1 安全组端口开放

**必须开放以下 TCP 端口**（腾讯云控制台 → 轻量应用服务器 → 防火墙）：

| 端口 | 用途 | 对应服务 |
|------|------|---------|
| 22 | SSH 远程连接 | sshd |
| 7000 | Milvus Attu 管理界面 | milvus-attu |
| 9000 | 独立 MinIO API | zg-minio |
| 9001 | 独立 MinIO 控制台 | zg-minio |
| 19530 | Milvus 主服务 | milvus-standalone |
| 27017 | MongoDB | zg-mongo |
| 8000-8001 | 项目 Web 服务（后面要用） | 项目代码 |

> ⚠️ **不需要开放**：Milvus 内置 MinIO 的 9002/9003、监控端口 9091 —— 它们只在 Docker 内部通信。

### 2.2 ❌ 踩坑1：apt update 权限拒绝

**现象**：
```
ubuntu@VM-0-3-ubuntu:~$ apt update
E: Could not open lock file /var/lib/apt/lists/lock - open (13: Permission denied)
```

**原因**：`apt` 是系统级操作，只有 root 能执行。你当前是普通用户 `ubuntu`。

**解决**：命令前面加 `sudo`：
```bash
sudo apt update && sudo apt upgrade -y
```

> 💡 第一次 sudo 时会让你输入当前用户密码。Ubuntu 默认 `ubuntu` 用户在 sudo 组里。

### 2.3 Docker 安装

执行官方安装脚本（国内版加速）：
```bash
curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun
```

### 2.4 ❌ 踩坑2：Docker socket 权限问题

**现象**：
```
ubuntu@VM-0-3-ubuntu:~$ docker ps
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

**原因**：普通用户默认无权访问 Docker socket。

**解决**：把当前用户加入 docker 用户组：
```bash
sudo usermod -aG docker $USER
```

**让修改生效**：**退出 SSH 重新登录**（或执行 `newgrp docker`），再试 `docker ps` 就 OK 了。

### 2.5 ❌ 踩坑3：Docker 镜像加速配置格式错误

**现象**：网上复制的 daemon.json 配置文件有各种问题：
- URL 带了 Markdown 反引号 `` ` ``
- 有中文引号 `"` 代替英文引号 `"`
- 最后一个条目后多了逗号
- 用 Tee 命令粘贴时被 shell 截断

**正确做法**：用 Python 生成合法 JSON（最保险）：
```bash
sudo python3 -c "
import json
config = {
    'registry-mirrors': [
        'https://docker.m.daocloud.io',
        'https://docker.nju.edu.cn',
        'https://docker.mirrors.ustc.edu.cn'
    ]
}
with open('/etc/docker/daemon.json', 'w') as f:
    json.dump(config, f, indent=2)
print('✅ 配置写入成功')
"
```

**验证配置**：
```bash
cat /etc/docker/daemon.json
# 正确输出（注意都是英文引号，最后一个条目后无逗号）：
# {
#   "registry-mirrors": [
#     "https://docker.m.daocloud.io",
#     "https://docker.nju.edu.cn",
#     "https://docker.mirrors.ustc.edu.cn"
#   ]
# }
```

**重启 Docker 生效**：
```bash
sudo systemctl daemon-reload
sudo systemctl restart docker
```

---

## 三、项目目录结构规划

**为什么要规划目录？** 避免文件散落各处，后期维护找不着。

**创建命令**：
```bash
mkdir -p ~/project/ZGzhiku/{deploy,code}
mkdir -p ~/project/ZGzhiku/deploy/{milvus,data/{milvus/{etcd,minio,milvus},minio,mongo},offline_images,logs}
```

**最终目录树**：
```
~/project/ZGzhiku/
├── deploy/                          # 部署相关
│   ├── milvus/                      # Milvus docker-compose.yml 放这里
│   │   └── docker-compose.yml
│   ├── data/                        # 持久化数据（重要！不要删！）
│   │   ├── milvus/                  # Milvus 全家桶数据
│   │   │   ├── etcd/
│   │   │   ├── minio/               # Milvus 内置 MinIO 数据
│   │   │   └── milvus/              # 向量数据
│   │   ├── minio/                   # 独立 MinIO 数据（存 PDF/图片）
│   │   └── mongo/                   # MongoDB 数据
│   ├── offline_images/              # 离线 tar 镜像包
│   └── logs/                        # 日志
└── code/                            # 项目源码（后面放）
```

---

## 四、离线镜像包导入

### 4.1 上传 tar 包到服务器

你的本地电脑应该有 6 个 tar 文件（来自课程 `02-镜像` 目录）：

| 文件名 | 对应镜像 | 大小 |
|--------|---------|------|
| `milvus-etcd.tar` | `quay.io/coreos/etcd:v3.5.18` | ~124MB |
| `milvus-minio.tar` | `minio/minio:RELEASE.2023-03-20T20-16-18Z`（Milvus 内置） | ~517MB |
| `milvus.tar` | `milvusdb/milvus:v2.5.5` | ~3.48GB |
| `attu.tar` | `zilliz/attu:v2.5.10` | ~901MB |
| `minio.tar` | `quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z`（独立） | ~361MB |
| `mongo.tar` | `mongo:latest` | ~1.92GB |

**用 WinSCP 或 scp 命令**上传到服务器 `~/project/ZGzhiku/deploy/offline_images/`。

### 4.2 ❌ 踩坑4：批量加载命令多行粘贴失败

**现象**：把带 `\` 的多行命令复制粘贴到终端后，所有内容挤成一行，shell 显示 `>` 提示符等待输入。

**原因**：Windows 的换行符（CRLF）和 Linux（LF）不同 + 反斜杠后面可能有空格。

**解决方案 A：用单行分号命令**（推荐）
```bash
cd ~/project/ZGzhiku/deploy/offline_images && for f in *.tar; do docker load -i "$f"; done
```

**解决方案 B：逐个加载**（最稳妥）
```bash
cd ~/project/ZGzhiku/deploy/offline_images
docker load -i milvus-etcd.tar
docker load -i milvus-minio.tar
docker load -i milvus.tar
docker load -i attu.tar
docker load -i minio.tar
docker load -i mongo.tar
```

**验证导入**：
```bash
docker images
```

**期望看到**：6 个镜像全部列出，IMAGE 列对应上表。

---

## 五、Milvus 向量数据库部署

### 5.1 修改 docker-compose.yml

课程提供的 `docker-compose.yml` 需要修改后才能在你的服务器上跑。**本地修改后上传到服务器**。

#### 修改 1：数据卷路径 → 绝对路径

原文件用相对路径 `${DOCKER_VOLUME_DIRECTORY:-.}/volumes/xxx`，数据会散落在 compose 文件旁边。改为统一绝对路径：

**etcd 服务**：
```yaml
# 改前
volumes:
  - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/etcd:/etcd
# 改后
volumes:
  - /home/ubuntu/project/ZGzhiku/deploy/data/milvus/etcd:/etcd
```

**Milvus 内置 MinIO 服务**：
```yaml
# 改前
volumes:
  - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/minio:/minio_data
# 改后
volumes:
  - /home/ubuntu/project/ZGzhiku/deploy/data/milvus/minio:/minio_data
```

**Milvus standalone 服务**：
```yaml
# 改前
volumes:
  - ${DOCKER_VOLUME_DIRECTORY:-.}/volumes/milvus:/var/lib/milvus
# 改后
volumes:
  - /home/ubuntu/project/ZGzhiku/deploy/data/milvus/milvus:/var/lib/milvus
```

#### 修改 2：删除 Attu 的 TLS 挂载

```yaml
# 改前
attu:
  ...
  ports:
    - "7000:7000"
  volumes:          # ← 删掉这两行
    - /root/milvus:/app/tls
  depends_on:
    - standalone

# 改后
attu:
  ...
  ports:
    - "7000:7000"
  depends_on:
    - standalone
```

**为什么删？** `/root/milvus` 目录不存在 + 你用 `ubuntu` 用户无权访问 `/root` + 学习项目不需要 HTTPS。

#### 修改 3（可选）：删掉 version 行

文件第一行 `version: '3.5'` 已被 Docker Compose V2 废弃，会产生警告。删掉即可（不删也能跑）。

### 5.2 ❌ 踩坑5：Milvus 内置 MinIO 与独立 MinIO 端口冲突

**冲突分析**：

| MinIO | 端口 | 来源 |
|-------|------|------|
| 独立 MinIO（项目用） | 9000（API）、9001（控制台） | 我们自己启动 |
| Milvus 内置 MinIO | **默认也是 9000/9001** 😱 | docker-compose.yml 启动 |

**解决**：修改 docker-compose.yml 中 Milvus 内置 MinIO 的端口映射：
```yaml
minio:
  container_name: milvus-minio
  ...
  ports:
    - "9003:9001"   # 改前 "9001:9001" → 改后 9003
    - "9002:9000"   # 改前 "9000:9000" → 改后 9002
```

> 💡 9002 是 API、9003 是控制台，随意取两个没被占用的端口就行。

### 5.3 启动 Milvus 全家桶

**Step 1：在服务器上提前创建数据目录**（防止 Docker 自动建目录归属 root 导致权限问题）：
```bash
mkdir -p ~/project/ZGzhiku/deploy/data/milvus/{etcd,minio,milvus}
```

**Step 2：上传修改后的 docker-compose.yml 到服务器**（本地 PowerShell）：
```powershell
scp "F:\Download\ai大模型\sgg项目\知识类\09Project实战\掌柜智库\02-镜像\milvus-v2.5.5配合attu-v2.5.10\docker-compose.yml" ubuntu@你的服务器IP:/home/ubuntu/project/ZGzhiku/deploy/milvus/
```

**Step 3：启动**：
```bash
cd ~/project/ZGzhiku/deploy/milvus
docker compose up -d
```

**预期输出**：
```
[+] Running 5/5
 ✔ Network milvus               Created
 ✔ Container milvus-etcd        Started
 ✔ Container milvus-minio       Started
 ✔ Container milvus-standalone  Started
 ✔ Container milvus-attu        Started
```

**Step 4：等待 30 秒后检查状态**：
```bash
sleep 30 && docker compose ps
```

**期望 4 个容器都是 Up，etcd 和 standalone 应为 healthy**。

### 5.4 Attu 浏览器验证

**打开** `http://你的服务器IP:7000`

| 字段 | 填写 |
|------|------|
| Milvus Address | `standalone:19530`（容器内通信，不要写公网 IP） |
| Database / Username / Password | 留空，直接 Connect |

**连接成功标志**：看到"数据库 (1) default"界面，运行时间开始计时。

---

## 六、独立 MinIO + MongoDB 部署

### 6.1 ❌ 踩坑6：docker run 多行命令粘贴失败

**现象**：和踩坑 4 一样，带 `\` 的多行命令粘贴后变成一行，报错 `docker: invalid reference format`。

**解决**：**不要用多行续接符**，直接写单行命令！

### 6.2 独立 MinIO 启动（存 PDF/图片）

```bash
docker rm -f zg-minio 2>/dev/null
docker run -d --name zg-minio --restart always -p 9000:9000 -p 9001:9001 -e MINIO_ROOT_USER=minioadmin -e MINIO_ROOT_PASSWORD=minioadmin123 -v ~/project/ZGzhiku/deploy/data/minio:/data quay.io/minio/minio:RELEASE.2024-12-18T13-15-44Z server /data --console-address ":9001"
```

**参数说明**：
- `--restart always`：服务器重启后自动启动
- `-p 9000:9000 -p 9001:9001`：映射到宿主机 9000/9001（和 Milvus 内置的 9002/9003 不冲突）
- `MINIO_ROOT_USER/PASSWORD`：登录账号密码
- `-v ...:/data`：数据持久化
- 镜像名：注意是 `quay.io/minio/minio`（带前缀！）

**浏览器验证**：`http://服务器IP:9001`，用 `minioadmin` / `minioadmin123` 登录。

### 6.3 MongoDB 启动（存对话历史）

```bash
docker rm -f zg-mongo 2>/dev/null
docker run -d --name zg-mongo --restart always -p 27017:27017 -v ~/project/ZGzhiku/deploy/data/mongo:/data/db mongo:latest mongod
```

**验证 MongoDB 是否运行**：
```bash
docker exec zg-mongo mongosh --eval "db.runCommand({ping: 1})"
# 或旧版
docker exec zg-mongo mongo --eval "db.runCommand({ping: 1})"
```

返回 `{ ok: 1 }` 就是正常。

### 6.4 ❓ 疑问：MongoDB 浏览器打不开？

**现象**：`http://服务器IP:27017/` 浏览器显示无法访问。

**结论：这是正常的！** 不用担心。

**原因**：
| 服务 | 类型 | 有网页界面？ | 浏览器能访问？ |
|------|------|------------|--------------|
| MinIO | 对象存储 + 控制台 | ✅ 有 | ✅ 能 |
| Milvus Attu | Milvus 管理界面 | ✅ 有 | ✅ 能 |
| MongoDB | 纯数据库服务 | ❌ 没有 | ❌ 不能（正常） |
| Milvus 主服务 | 纯向量数据库协议 | ❌ 没有 | ❌ 不能（正常） |

**MongoDB 只接受程序通过 `mongodb://` 协议连接**，不会返回 HTML 页面。就像你拿手机充电器插 HDMI 口没反应一样——不同协议的东西。

---

## 七、最终成果检查清单

执行以下命令，确认全部 ✅：

```bash
echo "========== 1. 所有容器状态 =========="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "========== 2. 数据目录 =========="
du -sh ~/project/ZGzhiku/deploy/data/*/

echo ""
echo "========== 3. 浏览器可访问 =========="
echo "MinIO 控制台: http://服务器IP:9001"
echo "Milvus Attu:  http://服务器IP:7000"

echo ""
echo "========== 4. MongoDB 健康检查 =========="
docker exec zg-mongo mongosh --eval "db.runCommand({ping: 1})"
```

**期望输出**：

| 检查项 | 期望 |
|--------|------|
| 6 个容器 | 都是 `Up` 状态 |
| 数据目录 | 4 个（milvus/minio/mongo + milvus 子目录） |
| 浏览器 | 两个页面能打开 |
| MongoDB | `{ ok: 1 }` |

---

## 八、踩坑总结 Top 8

| # | 坑 | 原因 | 解决方案 |
|---|------|------|---------|
| 1 | `apt update` Permission denied | 普通用户不能直接执行系统命令 | 加 `sudo` |
| 2 | `docker ps` permission denied | 当前用户未加入 docker 组 | `sudo usermod -aG docker $USER` 后重登 |
| 3 | daemon.json 配置报错 | 复制的 JSON 有格式问题（反引号、中文引号、多余逗号） | 用 Python 生成合法 JSON |
| 4 | 批量 `docker load` 失败 | `for` 循环多行粘贴后挤成一行 | 用单行分号命令或逐个加载 |
| 5 | Milvus 内置 MinIO 端口冲突 | 默认 9000/9001 被独立 MinIO 占用 | 改 compose 端口为 9002/9003 |
| 6 | `docker run invalid reference format` | `\` 续接符后有空格/换行丢失 | 直接写单行命令，不用反斜杠 |
| 7 | Attu 容器启动报 TLS 错误 | `/root/milvus` 不存在且 ubuntu 用户无权访问 | 删除 volumes 挂载 |
| 8 | MongoDB 浏览器打不开 | MongoDB 是纯数据库协议，不提供 HTTP 页面 | 正常现象，用命令行 `ping` 验证 |

---

## 附：一键清理所有中间件（危险操作）

如果出了大问题要重来：
```bash
# 停止并删除所有容器（数据还在）
cd ~/project/ZGzhiku/deploy/milvus && docker compose down
docker rm -f zg-minio zg-mongo

# 连同数据一起删除（⚠️ 数据丢失！）
rm -rf ~/project/ZGzhiku/deploy/data/*
```

---

> 📝 **小白寄语**：环境搭建是做项目最容易让人崩溃的阶段，各种权限、格式、路径问题层出不穷。**但每踩一个坑，你对 Linux 和 Docker 的理解就深一分**。别慌，按步骤来，复制粘贴命令时注意有没有被截断，遇到错误先仔细读报错信息再搜索——你已经离成功很近了！
