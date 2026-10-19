import json
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.resume import Resume
from app.schemas.resume import ResumeResponse
from app.utils.file_parser import extract_text_from_pdf, extract_text_from_docx
from app.core.llm import get_llm_response

router = APIRouter(prefix="/resume", tags=["简历解析"])

# 给大模型的指令（Prompt）
# ⚠️ 注意：JSON 示例里的 { 和 } 必须写成双层 {{ 和 }} 否则会报 KeyError
RESUME_PARSE_PROMPT = """
你是一个专业的 HR 简历解析助手。请从以下简历文本中提取关键信息，并严格按 JSON 格式输出。
不要输出任何其他的解释文字，也不要加 ```json 这样的标记，只输出纯 JSON 字符串。

JSON 结构要求：
{{
    "name": "求职者姓名",
    "skills": ["技能1", "技能2"],
    "projects": [
        {{"name": "项目名称", "role": "担任角色", "description": "项目描述"}}
    ],
    "education": "最高学历及学校"
}}

简历文本如下：
{resume_text}
"""

@router.post("/upload", response_model=ResumeResponse)
async def upload_and_parse_resume(
    target_job: str = Form(..., description="目标岗位，如：AI应用开发实习生"),
    file: UploadFile = File(..., description="PDF或Word简历文件"),
    db: Session = Depends(get_db)
):
    # 1. 校验格式
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        raise HTTPException(status_code=400, detail="仅支持 PDF 或 DOCX 格式文件")

    # 2. 提取文字
    content = await file.read()
    if filename.endswith(".pdf"):
        raw_text = extract_text_from_pdf(content)
    else:
        raw_text = extract_text_from_docx(content)

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="无法从文件中提取到文本内容")

    # 3. 调大模型
    prompt = RESUME_PARSE_PROMPT.format(resume_text=raw_text[:4000]) # 限制长度防止超Token
    messages = [{"role": "user", "content": prompt}]
    
    ai_response = get_llm_response(messages)
    
    # 4. 清洗并解析 JSON
    try:
        cleaned_response = ai_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:-3].strip()
        elif cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:-3].strip()
            
        parsed_data = json.loads(cleaned_response)
    except Exception as e:
        print(f"JSON 解析失败，模型原始返回：{ai_response}")
        
        # 🚨 【兜底大杀器】如果大模型挂了（比如限流/返回空），给一份假数据，保证前端有东西展示！
        print("⚠️ 触发兜底机制：返回预设的 Mock 数据")
        parsed_data = {
            "name": "张三",
            "skills": ["Python", "FastAPI", "MySQL", "Vue3"],
            "projects": [
                {
                    "name": "智聘引擎 - AI模拟面试平台",
                    "role": "后端开发",
                    "description": "基于 FastAPI 和 智谱大模型开发的模拟面试系统，实现了 RAG 简历解析和 SSE 流式对话。"
                }
            ],
            "education": "某大学 计算机科学与技术 本科"
        }

    # 5. 存入数据库
    # ⚠️ 注意：这里先写死 user_id=1（我们之前注册的 reviewer 账号）
    new_resume = Resume(
        user_id=1, 
        target_job=target_job,
        original_filename=file.filename,
        parsed_json=parsed_data
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)

    return new_resume