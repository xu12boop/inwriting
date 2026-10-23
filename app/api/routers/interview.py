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

router = APIRouter(prefix="/interview", tags=["模拟面试"])

INTERVIEWER_PROMPT = """
你是一位大厂资深面试官。候选人简历信息：
{resume_json}

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
        user_id=current_user.id,
        resume_id=req.resume_id,
        chat_history=[],
        status="ongoing"
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)
    return new_interview


@router.post("/chat")
def chat(req: ChatRequest):  # 👈 注意：这里去掉了 async
    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == req.interview_id).first()
        if not interview:
            raise HTTPException(status_code=404, detail="面试记录不存在")
            
        resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
        chat_history = interview.chat_history or []
        chat_history.append({"role": "user", "content": req.user_message})

        system_msg = {
            "role": "system", 
            "content": INTERVIEWER_PROMPT.format(
                resume_json=json.dumps(resume.parsed_json, ensure_ascii=False) if resume else "暂无"
            )
        }
        messages = [system_msg] + chat_history

        # 👈 这里也去掉了 async，变成普通的同步生成器
        def sse_generator():
            full_response = ""
            
            for chunk in get_llm_stream(messages):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                time.sleep(0.05) # 放心大胆地用 time.sleep，不会卡死服务器了
            
            if not full_response.strip():
                print("⚠️ 大模型未返回内容，触发 Mock 兜底...")
                mock_question = "你好，我是今天的面试官。我看你简历上写了熟悉 FastAPI，能简单说说你是如何处理高并发场景的流式响应的吗？"
                for char in mock_question:
                    full_response += char
                    yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                    time.sleep(0.05)

            chat_history.append({"role": "assistant", "content": full_response})
            interview.chat_history = chat_history
            db.add(interview)
            db.commit()
            db.close()
            
            yield "data: [DONE]\n\n"

        headers = {
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache"
        }
        return StreamingResponse(sse_generator(), media_type="text/event-stream", headers=headers)

    except Exception as e:
        db.close()
        print(f"报错: {e}")
        raise HTTPException(status_code=500, detail="服务器错误")