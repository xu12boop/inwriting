import json
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db, SessionLocal
from app.models.interview import Interview
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import InterviewStartRequest, ChatRequest, InterviewResponse
from app.core.llm import get_llm_stream
from app.api.deps import get_current_user
from app.core.rag import search_jd

router = APIRouter(prefix="/interview", tags=["模拟面试"])

INTERVIEWER_PROMPT = """
你是一位大厂资深面试官。候选人简历信息：
{resume_json}

该岗位的核心 JD 要求（请结合这些要求提问）：
{jd_text}

要求：
1. 提问专业有深度，结合项目经历深挖。
2. 每次提问 1-2 个问题，不要长篇大论。
3. 直接输出问题，不要输出其他废话。
"""

@router.post("/start", response_model=InterviewResponse)
def start_interview(
    req: InterviewStartRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == req.resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="未找到该简历")

    new_interview = Interview(
        user_id=current_user.id, # ✅ 真实用户
        resume_id=req.resume_id,
        chat_history=[],
        status="ongoing"
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)
    return new_interview


@router.post("/chat")
async def chat(req: ChatRequest):
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == req.interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="面试记录不存在")
            
        resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
        chat_history = interview.chat_history or []
        chat_history.append({"role": "user", "content": req.user_message})

        # 🚨 RAG 检索：去 Chroma 库里查这个岗位的 JD
        jd_text = search_jd(resume.target_job) if resume else "暂无 JD 信息"

        system_msg = {
            "role": "system", 
            "content": INTERVIEWER_PROMPT.format(
                resume_json=json.dumps(resume.parsed_json, ensure_ascii=False) if resume else "暂无",
                jd_text=jd_text
            )
        }
        messages = [system_msg] + chat_history

        def sse_generator():
            full_response = ""
            for chunk in get_llm_stream(messages):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
            
            # 兜底
            if not full_response.strip():
                mock_question = "我看你简历里写了 FastAPI，结合我们这个岗位的 JD 要求，能说说你是如何实现接口鉴权和 RAG 检索的吗？"
                for char in mock_question:
                    time.sleep(0.05)
                    full_response += char
                    yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"

            chat_history.append({"role": "assistant", "content": full_response})
            interview.chat_history = chat_history
            db.add(interview)
            db.commit()
            db.close()
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream")

    except Exception as e:
        db.close()
        print(f"报错: {e}")
        raise HTTPException(status_code=500, detail="服务器错误")