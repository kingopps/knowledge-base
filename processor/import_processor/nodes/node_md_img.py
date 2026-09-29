# processor/import_processor/nodes/node_md_img.py

"""
Markdown 图片处理节点

核心流程：
1. 读取 MD 内容和图片文件夹
2. 扫描筛选 MD 中实际引用的支持格式图片
3. 调用多模态大模型（VLM）为每张图片生成中文摘要（带速率限制）
4. 上传图片至 MinIO，替换 MD 中本地路径为 MinIO URL，Alt 文本填入摘要
5. 备份原 MD，保存处理后的新 MD 为 _new.md
"""

import base64
import json
import logging
import os
import re
import time
from collections import deque
from pathlib import Path
from typing import Tuple, List, Deque, Dict

from langchain_openai import ChatOpenAI
from minio import Minio
from minio.deleteobjects import DeleteObject

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError, FileProcessingError
from processor.import_processor.state import ImportGraphState
from utils.minio_utils import get_minio_client

class NodeMDImg(BaseNode):
    """
    Markdown 图片处理节点：多模态图片理解
    """

    name = "node_md_img"

    def process(self, state: ImportGraphState):
        # 步骤1：初始化数据，获取 MD 核心信息
        md_content, md_path_obj, images_dir = self._step_1_get_content(state)

        # 无图片文件夹，直接跳过图片处理
        if not images_dir.exists():
            self.logger.info("无图片文件夹，跳过图片处理")
            return state

        # 步骤2：扫描并筛选 MD 中引用的图片
        target_images = self._step_2_scan_images(md_content, images_dir)
        if not target_images:
            self.logger.info("未检测到 MD 中引用了图片，跳过图片处理")
            return state

        # 步骤3：调用多模态大模型生成图片摘要
        summaries = self._step_3_generate_summaries(md_path_obj.stem, target_images)

        # 步骤4：上传图片至 MinIO，替换 MD 图片路径并填充摘要
        new_md_content = self._step_4_upload_and_replace(md_path_obj.stem, target_images, summaries, md_content)

        # 步骤5：备份并保存新 MD 文件
        new_md_file_name = self._step_5_backup_new_md_file(state['md_path'], new_md_content)

        # 步骤6：更新 state 状态值
        state["md_content"] = new_md_content
        state["md_path"] = new_md_file_name

        return state

    def _step_1_get_content(self, state: ImportGraphState) -> Tuple[str, Path, Path]:
        """
        步骤1：从全局状态中提取并初始化 MD 处理所需核心数据
        :return: 三元组(MD文件内容, MD文件路径, 图片文件夹路径)
        """
        # 1. 参数非空校验
        md_path = state.get("md_path")
        if not md_path:
            raise StateFieldError(field_name="md_path", message="MD文件路径不能为空", expected_type=str)

        # 2. 路径转换
        md_path_obj = Path(md_path)

        # 3. 检查文件有效性
        if not md_path_obj.exists():
            raise FileProcessingError(message=f"文件{md_path_obj.name}不存在")

        # 4. 优先使用 state 中已存在的 md_content，无则从文件读取
        md_content = state.get("md_content")
        if not md_content:
            md_content = md_path_obj.read_text(encoding="utf-8")
            state["md_content"] = md_content

        # 5. 组装图片文件夹路径：固定为 MD 文件同级的 images 目录
        img_dir = md_path_obj.parent / "images"

        return md_content, md_path_obj, img_dir

    def _step_2_scan_images(self, md_content: str, images_dir: Path) -> List[Tuple[str, str, Tuple[str, str]]]:
        """
        步骤2：扫描图片文件夹，过滤出「支持格式 + MD 中实际引用」的图片
        :return: 待处理图片列表，每个元素为 (图片文件名, 图片完整路径, 图片上下文) 元组
        """
        target_images = []

        # 遍历图片文件夹
        for image_file in os.listdir(images_dir):
            # 1. 过滤无效后缀
            file_ext = os.path.splitext(image_file)[1].lower()
            if file_ext not in self.config.image_extensions:
                self.logger.warning(f"图片{image_file}格式不支持")
                continue

            # 2. 组装图片完整路径并转成字符串
            img_path = str(images_dir / image_file)

            # 3. 查找图片在 MD 中的引用上下文
            context = self._find_image_in_md(md_content, image_file)
            if not context:
                self.logger.warning(f"图片{image_file}未在 MD 文档中找到")
                continue

            # 4. 加入待处理列表
            target_images.append((image_file, img_path, context))

        return target_images

    def _find_image_in_md(self, md_content: str, image_file: str, context_len: int = 100) -> Tuple[str, str]:
        """
        查找 MD 内容中指定图片的引用位置，返回该位置的上下文（上文, 下文）
        正则：![任意描述](任意路径 + 图片文件名 + 任意后缀)
        """
        # re.escape：转义图片文件名中的特殊字符（如 .），避免正则语法错误
        # 同时支持 Markdown ![]() 和 HTML <img src=""/> 两种格式（MinerU 会输出 HTML 格式）
        escaped_file = re.escape(image_file)

        # 1. 先尝试 Markdown 标准格式：![alt](path/filename)
        md_pattern = re.compile(r'!\[.*?\]\(.*?' + escaped_file + r'.*?\)')
        match = md_pattern.search(md_content)

        # 2. Markdown 没匹配到，再尝试 HTML <img> 标签格式
        if not match:
            html_pattern = re.compile(
                r'<img\s+[^>]*?src=".*?' + escaped_file + r'.*?"[^>]*/?>',
                re.IGNORECASE
            )
            match = html_pattern.search(md_content)

        if not match:
            return None

        # 截取匹配位置的上文和下文（防止索引越界）
        start, end = match.span()
        pre_text = md_content[max(0, start - context_len):start]
        post_text = md_content[end:min(len(md_content), end + context_len)]

        return pre_text, post_text

    def _step_3_generate_summaries(self, doc_stem: str, target_images: List[Tuple[str, str, Tuple[str, str]]]) -> Dict[str, str]:
        """
        步骤3：批量为待处理图片生成内容摘要，带 API 速率限制防止触发大模型限流
        :return: 图片摘要字典，键：图片文件名，值：图片内容摘要
        """
        summaries = {}
        request_deque = deque()  # 双端队列，用于速率限制（跨循环复用）

        for img_file, img_path, context in target_images:
            # 1. 限速（滑动窗口算法）
            self._apply_api_rate_limit(request_deque, self.config.requests_per_minute)

            # 2. 调用大模型生成图片摘要
            summaries[img_file] = self._summarize_image(img_path, root_folder=doc_stem, image_content=context)

        return summaries

    def _summarize_image(self, image_path: str, root_folder: str, image_content: Tuple[str, str]) -> str:
        """
        调用多模态大模型生成图片内容摘要
        :param image_path: 图片本地完整路径
        :param root_folder: 文档主名（不含后缀），为大模型提供上下文
        :param image_content: 图片在 MD 中的上下文元组 (上文, 下文)
        :return: 图片内容摘要（异常时返回默认值 root_folder）
        """
        # 1. 将图片转成 base64
        with open(image_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode("utf-8")

        try:
            # 2. 创建多模态大模型客户端（LangChain 标准接口）
            chat_model = ChatOpenAI(
                model=self.config.vl_model,
                api_key=self.config.openai_api_key,
                base_url=self.config.openai_api_base,
                temperature=self.config.llm_temperature
            )

            # 3. 构造多模态消息（文本提示 + base64 图片）
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"""这是"{root_folder}"文件中的一张图片，图片上文部分为"{image_content[0]}"，下文部分为"{image_content[1]}"，请用中文简要总结这张图片的内容，用于 Markdown 图片标题，控制在50字以内。"""
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ]

            # 4. 调用大模型
            response = chat_model.invoke(messages)
            # 5. 解析响应（去掉换行）
            return response.content.strip().replace("\n", "")

        except Exception as e:
            self.logger.error(f"获取图片摘要失败:{image_path}， 错误：{e}")
            return root_folder

    def _apply_api_rate_limit(
            self,
            request_times: Deque[float],
            max_requests: int,
            window_seconds: int = 60
    ) -> None:
        """
        通用滑动窗口 API 速率限制器
        核心逻辑：维护请求时间戳双端队列，窗口内请求数超上限则自动等待
        """
        # 1. 记录当前时间
        current_time = time.time()

        # 2. 清理滑动窗口中的过期请求
        while request_times and current_time - request_times[0] >= window_seconds:
            request_times.popleft()

        # 3. 窗口内请求数达到上限，计算需要等待的时间并阻塞
        if len(request_times) >= max_requests:
            sleep_duration = window_seconds - (current_time - request_times[0])
            if sleep_duration > 0:
                self.logger.info(f"请求被限速，等待{sleep_duration:.2f}秒...")
                time.sleep(sleep_duration)

                # 等完后重新清理过期请求
                current_time = time.time()
                while request_times and current_time - request_times[0] >= window_seconds:
                    request_times.popleft()

        # 4. 记录当前请求的时间戳，新请求入队
        request_times.append(current_time)
        self.logger.info(f"{self.name} 请求成功，当前{window_seconds}s窗口内请求次数为{len(request_times)}")

    def _step_4_upload_and_replace(
            self,
            doc_stem: str,
            target_images: List[Tuple[str, str, Tuple[str, str]]],
            summaries: Dict[str, str],
            md_content: str
    ) -> str:
        """
        步骤4：清理 MinIO 旧目录 → 批量上传新图片 → 合并摘要和 URL → 替换 MD 内容
        """
        # 1. 获取 MinIO 客户端
        minio_client = get_minio_client()

        # 2. 获取 MinIO 上传目录（按文档名隔离，去空格避免路径问题）
        upload_dir = f"{self.config.minio_img_dir}/{doc_stem}".replace(" ", "")

        # 3. 清理该文档对应的 MinIO 旧目录
        self._clean_minio_dir(minio_client, upload_dir)

        # 4. 批量上传图片至 MinIO，获取 URL 映射
        urls = self._upload_images_batch(minio_client, upload_dir, target_images)

        # 5. 合并图片摘要和 URL，过滤上传失败的图片
        image_info = self._merge_summary_and_url(summaries, urls)

        # 6. 替换 MD 内容中的本地图片引用为 MinIO 远程引用
        md_content = self._process_md_file(md_content, image_info)

        return md_content

    def _clean_minio_dir(self, minio_client: Minio, update_dir: str) -> None:
        """幂等性清理 MinIO 指定目录下的所有旧文件"""
        try:
            # 1. 列出待删除的对象（递归遍历）
            objects_to_delete = minio_client.list_objects(
                self.config.minio_bucket, update_dir, recursive=True
            )
            delete_list = [DeleteObject(obj.object_name) for obj in objects_to_delete]

            # 2. 批量删除
            errors = minio_client.remove_objects(self.config.minio_bucket, delete_list)
            for error in errors:
                self.logger.error(f"删除图片错误：{error}")

        except Exception as e:
            self.logger.error(f"MinIO连接失败，错误原因：{e}")

    def _upload_images_batch(self, minio_client: Minio, upload_dir: str, target_images: List[Tuple]) -> Dict[str, str]:
        """批量上传待处理图片至 MinIO，返回 图片文件名 → URL 映射"""
        urls = {}
        for img_file, img_path, _ in target_images:
            object_name = f"{upload_dir}/{img_file}"
            urls[img_file] = self._upload_to_minio(minio_client, img_path, object_name)
        return urls

    def _upload_to_minio(self, minio_client: Minio, local_path: str, object_name: str) -> str:
        """
        将单张本地图片上传至 MinIO 对象存储，并返回公网可访问 URL
        :return: 图片 MinIO 访问 URL（上传失败返回 None）
        """
        try:
            content_type = os.path.splitext(local_path)[1][1:]  # 去掉点号，如 "jpg"
            minio_client.fput_object(
                bucket_name=self.config.minio_bucket,
                object_name=object_name,
                file_path=local_path,
                content_type=f"image/{content_type}",
            )

            # 组织图片访问 URL（优先使用外部访问地址）
            external_endpoint = os.getenv("MINIO_EXTERNAL_ENDPOINT", self.config.minio_endpoint)
            url = f"http://{external_endpoint}/{self.config.minio_bucket}/{object_name}"
            return url
        except Exception as e:
            self.logger.error(f"上传图片失败：{local_path}，错误：{e}")
            return None

    def _merge_summary_and_url(self, summaries: Dict[str, str], urls: Dict[str, str]) -> Dict[str, Tuple[str, str]]:
        """合并图片摘要字典和 URL 字典，过滤掉上传失败无 URL 的图片"""
        image_info = {}
        for image_file, summary in summaries.items():
            # 海象运算符 :=：表达式内赋值 + 结果判断一体化
            if url := urls.get(image_file):
                image_info[image_file] = (summary, url)
        return image_info

    def _process_md_file(self, md_content: str, image_info: Dict[str, Tuple[str, str]]) -> str:
        """
        核心功能：替换 MD 内容中的本地图片引用为 MinIO 远程引用
        替换规则：![原描述](本地路径) → ![图片摘要](MinIO 访问URL)
        """
        for image_file, (summary, new_url) in image_info.items():
            escaped_file = re.escape(image_file)

            # 1. 替换 Markdown 标准格式：![alt](path) → ![summary](new_url)
            md_pattern = re.compile(r'!\[.*?\]\(.*?' + escaped_file + r'.*?\)')
            md_content = md_pattern.sub(lambda m: f'![{summary}]({new_url})', md_content)

            # 2. 替换 HTML <img> 标签格式：<img src="path"/> → <img src="new_url" alt="summary"/>
            html_pattern = re.compile(
                r'<img\s+[^>]*?src=".*?' + escaped_file + r'.*?"[^>]*/?>',
                re.IGNORECASE
            )
            md_content = html_pattern.sub(lambda m: f'<img src="{new_url}" alt="{summary}"/>', md_content)

        return md_content

    def _step_5_backup_new_md_file(self, origin_md_path: str, md_content: str) -> str:
        """
        步骤5：将处理后的 MD 内容保存为新文件（原文件不变，避免数据丢失）
        新文件命名规则：原文件名 + _new.md（如 test.md → test_new.md）
        """
        new_md_file_name = os.path.splitext(origin_md_path)[0] + "_new.md"
        with open(new_md_file_name, "w", encoding="utf-8") as f:
            f.write(md_content)

        return new_md_file_name

if __name__ == "__main__":
    setup_logging()

    # 用节点2 输出的 MD 文件路径
    md_path = "/home/ubuntu/project/ZGzhiku/code/knowledge_base/output/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册.md"

    init_state = {
        "task_id": "task_test_003",
        "md_path": md_path,
        "md_content": ""  # 留空则自动从文件读取
    }

    # 执行核心处理流程
    node_md_img = NodeMDImg()
    result = node_md_img(init_state)

    logging.getLogger().info(json.dumps(
        {"md_path": result["md_path"], "md_content_len": len(result["md_content"])},
        ensure_ascii=False, indent=4
    ))