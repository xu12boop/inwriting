"""生成压测用的最小 DOCX 简历（避免在压测主脚本里重复构造文件）。"""
import os

from docx import Document

_HERE = os.path.dirname(os.path.abspath(__file__))
RESUME_PATH = os.path.join(_HERE, "_stress_resume.docx")

RESUME_LINES = [
    ("张三", 16),
    ("求职意向：AI 应用开发实习生", None),
    ("教育背景：某大学 计算机科学与技术 本科 2022-2026", None),
    ("项目经历：基于 FastAPI 与向量检索的模拟面试系统，负责后端流式接口、RAG 检索与重排模块，"
     "单机压测可支撑每秒 200 并发。", None),
    ("技能：Python、FastAPI、Vue3、RAG、Prompt 工程、SQLite", None),
]


def build(path: str | None = None) -> str:
    if path is None:
        path = RESUME_PATH
    doc = Document()
    for line, size in RESUME_LINES:
        p = doc.add_paragraph()
        run = p.add_run(line)
        if size:
            run.bold = True
    doc.save(path)
    return path


if __name__ == "__main__":
    print(build())
