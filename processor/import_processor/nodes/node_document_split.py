# processor/import_processor/nodes/node_document_split.py

"""
文档切分节点

将长 MD 文档切分为长度适中、语义完整的 Chunk，为向量化做准备。
切分策略：标题初切 → 超长递归切 → 过短合并 → 父标题兜底
"""

import json
import logging
import re
from pathlib import Path
from typing import Tuple, List, Dict

from langchain_text_splitters import RecursiveCharacterTextSplitter

from processor.import_processor.base import BaseNode, setup_logging
from processor.import_processor.exceptions import StateFieldError
from processor.import_processor.state import ImportGraphState

class NodeDocumentSplit(BaseNode):
    """
    文档切分节点：将长文档切分为 Chunk
    """

    name: str = "node_document_split"

    def process(self, state: ImportGraphState) -> ImportGraphState:
        # 步骤1：加载并标准化输入数据
        content, file_title = self._step_1_get_inputs(state)

        # 步骤2：按MD标题进行初次切分
        sections, title_count, lines_count = self._step_2_split_by_titles(content, file_title)

        # 步骤3：无标题场景兜底处理
        sections = self._step_3_handle_no_title(content, sections, title_count, file_title)

        # 步骤4：Chunk精细化处理（长切短合）
        sections = self._step_4_refine_chunks(sections)

        # 步骤5：输出文档切分统计信息
        self._step_5_print_stats(lines_count, sections)

        # 步骤6：Chunk结果本地JSON备份
        self._step_6_backup(state, sections)

        # 写入状态字典
        state["chunks"] = sections
        return state

    def _step_1_get_inputs(self, state: ImportGraphState) -> Tuple[str, str]:
        """
        步骤1：获取并预处理输入数据
        功能：从状态字典中提取MD内容/文件标题，做基础标准化
        """
        file_title = state.get("file_title")
        if not file_title:
            raise StateFieldError(field_name="file_title", message="文件标题不能为空", expected_type=str)

        md_content = state.get("md_content")
        if not md_content:
            raise StateFieldError(field_name="md_content", message="文件内容不能为空", expected_type=str)

        # 基础标准化：统一换行符（消除Windows/Linux差异）
        md_content = md_content.replace("\r\n", "\n").replace("\r", "\n")

        self.logger.info(f"步骤1：输入数据加载完成，文件标题：{file_title}")
        return md_content, file_title

    def _step_2_split_by_titles(self, content: str, file_title: str) -> Tuple[List[Dict[str, str]], int, int]:
        """
        步骤2：按Markdown标题初次切分
        核心：按#分级切分，跳过代码块内标题，保证章节语义完整
        """
        # 1. 定义标题正则：行首允许空格 + 1-6个# + 至少1个空格 + 标题文字
        title_pattern = r'\s*#{1,6}\s+.+'

        # 2. 初始化数据
        lines = content.split("\n")
        sections = []
        title_count = 0
        current_title = ""
        current_lines = []
        in_code_block = False
        code_block_start_marker = None

        # 3. 内部辅助函数：将当前缓存的章节写入sections
        def _flush_section():
            if not current_lines:
                return
            sections.append({
                "title": current_title,
                "content": "\n".join(current_lines),
                "file_title": file_title,
            })

        # 4. 逐行遍历，识别标题/普通行/代码块
        for line in lines:
            stripped_line = line.strip()

            # 4.1 识别代码块边界（```、~~~、```` 等，至少3个连续字符）
            code_block_marker_match = re.match(r'^(`{3,}|~{3,})$', stripped_line)
            if code_block_marker_match:
                marker = code_block_marker_match.group(1)
                if not in_code_block:
                    in_code_block = True
                    code_block_start_marker = marker
                elif in_code_block and stripped_line == code_block_start_marker:
                    in_code_block = False
                    code_block_start_marker = None
                current_lines.append(line)
                continue

            # 4.2 识别标题（代码块内的#不算标题）
            is_valid_title = (not in_code_block) and re.match(title_pattern, line)
            if is_valid_title:
                _flush_section()
                current_title = stripped_line
                current_lines = [current_title]
                title_count += 1
                self.logger.info(f"识别标题：{current_title}")
            else:
                current_lines.append(stripped_line)

        _flush_section()
        self.logger.info(
            f"步骤2：文档粗切完成，共{len(sections)}个章节，标题数{title_count}，文本共{len(lines)}行"
        )
        return sections, title_count, len(lines)

    def _step_3_handle_no_title(self, content: str, sections: List[Dict[str, str]],
                                title_count: int, file_title: str) -> List[Dict[str, str]]:
        """步骤3：无标题兜底处理"""
        if title_count == 0:
            self.logger.warning(f"步骤3：未识别到任何MD标题，将全文作为单个章节处理")
            return [{
                "title": "无标题",
                "content": content,
                "file_title": file_title
            }]
        return sections

    def _step_4_refine_chunks(self, sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """步骤4：Chunk精细化处理（长切短合）"""
        # 阶段1：超长章节切分
        refined_split = []
        for section in sections:
            refined_split.extend(self._split_long_section(section))
        self.logger.info(f"步骤4-1：超长章节切分完成，共生成{len(refined_split)}个初始子Chunk")

        # 阶段2：短章节合并
        final_sections = self._merge_short_sections(refined_split)
        self.logger.info(f"步骤4-2：过短章节合并完成，最终{len(final_sections)}个Chunk")

        # 阶段3：父标题兜底（Milvus schema必填字段）
        for sec in final_sections:
            if not sec.get("parent_title"):
                sec["parent_title"] = sec.get("title") or ""
        self.logger.info(f"步骤4-3：父标题兜底完成")

        return final_sections

    def _split_long_section(self, section: Dict[str, str]) -> List[Dict[str, str]]:
        """辅助函数：超长章节二次切分（按段落→句子→标点递归切）"""
        content = section.get("content", "")
        if len(content) <= self.config.max_content_length:
            return [section]

        title = section.get("title", "")
        prefix = f"{title}\n\n" if title else ""
        available_len = self.config.max_content_length - len(prefix)

        if available_len <= 0:
            self.logger.warning(f"章节标题过长，无法切分：{title[:20]}...")
            return [section]

        # 清理正文开头重复的标题
        body = content
        if title and body.lstrip().startswith(title):
            body = body[body.find(title) + len(title):].lstrip()

        # LangChain 递归分割器（分隔符优先级从粗到细）
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=available_len,
            chunk_overlap=0,
            separators=["\n\n", "\n", "。", "！", "？", "；", ".", "!", "?", ";", " "],
        )

        sub_sections = []
        for idx, chunk in enumerate(splitter.split_text(body), start=1):
            text = chunk.strip()
            if not text:
                continue
            full_text = (prefix + text).strip()
            sub_sections.append({
                "parent_title": title,
                "title": f"{title}-{idx}" if title else f"chunk-{idx}",
                "content": full_text,
                "part": idx,
                "file_title": section.get("file_title"),
            })

        self.logger.info(f"超长章节切分：{title} → {len(sub_sections)}个子Chunk")
        return sub_sections

    def _merge_short_sections(self, sections: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """辅助函数：过短章节合并（同父标题 + <500字才合并）"""
        if not sections:
            return []

        merged_sections = []
        current_chunk = None

        for section in sections:
            if current_chunk is None:
                current_chunk = section
                continue

            is_current_short = len(current_chunk["content"]) < self.config.min_content_length
            is_same_parent = current_chunk.get("parent_title") == section.get("parent_title")

            if is_current_short and is_same_parent:
                # 合并前清理下一块开头重复的父标题
                parent_title = section.get("parent_title", "")
                next_content = section["content"]
                if parent_title and next_content.startswith(parent_title):
                    next_content = next_content[len(parent_title):].lstrip()
                current_chunk["content"] += "\n\n" + next_content
                if "part" in section:
                    current_chunk["part"] = section["part"]
            else:
                merged_sections.append(current_chunk)
                current_chunk = section

        if current_chunk is not None:
            merged_sections.append(current_chunk)

        return merged_sections

    def _step_5_print_stats(self, lines_count: int, sections: List[Dict[str, str]]) -> None:
        """步骤5：输出文档切分统计信息"""
        chunk_num = len(sections)
        self.logger.info("-" * 50 + " 文档切分统计信息 " + "-" * 50)
        self.logger.info(f"MD原始文本总行数：{lines_count}")
        self.logger.info(f"最终生成Chunk数量：{chunk_num}")
        if sections:
            first = sections[0]
            self.logger.info(f"首个Chunk预览：title={first.get('title')}, "
                             f"content长度={len(first.get('content', ''))}")

    def _step_6_backup(self, state: ImportGraphState, sections: List[Dict[str, str]]) -> None:
        """步骤6：Chunk结果本地JSON备份（与MD文件同目录）"""
        try:
            backup_path = Path(state["md_path"]).parent / "chunks.json"
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(sections, f, ensure_ascii=False, indent=2)
            self.logger.info(f"步骤6：Chunk结果备份成功，路径：{backup_path}")
        except Exception as e:
            self.logger.error(f"步骤6：Chunk结果备份失败：{e}", exc_info=False)

if __name__ == "__main__":
    setup_logging()

    # 用节点3 输出的 _new.md 文件
    md_path = "/home/ubuntu/project/ZGzhiku/code/knowledge_base/output/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册/Aolynk CB304n Cable网桥 用户手册-5W100-整本手册_new.md"
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    init_state = {
        "task_id": "task_test_004",
        "md_path": md_path,
        "md_content": md_content,
        "file_title": "Aolynk CB304n Cable网桥 用户手册-5W100-整本手册"
    }

    node_document_split = NodeDocumentSplit()
    result = node_document_split(init_state)

    # 只打印关键信息，避免 chunks 列表太长
    logging.getLogger().info(json.dumps({
        "chunks_count": len(result["chunks"]),
        "first_chunk_title": result["chunks"][0]["title"] if result["chunks"] else None,
        "last_chunk_title": result["chunks"][-1]["title"] if result["chunks"] else None,
    }, ensure_ascii=False, indent=4))