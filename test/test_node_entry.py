# test/test_node_entry.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging
from processor.import_processor.base import setup_logging
from processor.import_processor.nodes.node_enrty import NodeEntry
from processor.import_processor.state import get_default_state

def run_case(file_path: str) -> dict:
    state = get_default_state()
    state["import_file_path"] = file_path
    node = NodeEntry()
    return node(state)

if __name__ == "__main__":
    setup_logging(logging.INFO)

    cases = [
        ("说明书.pdf", True, False),
        ("笔记.md", False, True),
        ("表格.docx", False, False),
    ]

    all_pass = True
    for file_path, expect_pdf, expect_md in cases:
        result = run_case(file_path)
        ok = (
            result["is_pdf_read_enabled"] == expect_pdf
            and result["is_md_read_enabled"] == expect_md
        )
        print(f"{'PASS' if ok else 'FAIL'} | {file_path} -> pdf={result['is_pdf_read_enabled']}, md={result['is_md_read_enabled']}")
        all_pass = all_pass and ok

    print("全部测试通过!" if all_pass else "有测试失败!")
