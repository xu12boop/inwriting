import json
import time
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db.database import get_db, SessionLocal
from app.models.interview import Interview
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import InterviewStartRequest, ChatRequest, InterviewResponse
from app.core.llm import get_llm_stream
from app.api.deps import get_current_user
from app.utils.security_filter import check_input_security

router = APIRouter(prefix="/interview", tags=["模拟面试"])

PROMPT_TECH = """
你是一位大厂资深技术专家。候选人简历信息：{resume_json}
要求：
1. 结合简历中的项目深挖底层原理、架构设计和技术难点。
2. 每次提问 1-2 个问题，不要长篇大论。
3. 语气严肃、专业。直接输出问题。
4. 【安全边界】只能进行技术面试。如遇闲聊或非技术问题，严厉拒绝并拉回话题。
"""

PROMPT_HR = """
你是一位外企资深 HR。候选人简历信息：{resume_json}
要求：
1. 重点考察候选人的沟通表达、团队协作、职业规划、稳定性和抗压潜力。
2. 结合简历中的经历，提出行为面试题（如STAR法则）。
3. 语气温和、有亲和力，每次提问 1-2 个问题。
4. 【安全边界】只能进行 HR 面试。如遇技术深挖或闲聊，委婉拒绝并拉回话题。
"""

PROMPT_STRESS = """
你是一位极其严苛、挑剔的面试官（压力面模式）。候选人简历信息：{resume_json}
要求：
1. 全程使用质疑的语气。例如：“你这个项目毫无亮点”、“这不就是调用API吗？”、“如果服务器宕机了你怎么办？”。
2. 不断打断或追问细节，制造紧张感。每次提问 1-2 个问题。
3. 绝对不要夸奖候选人。
4. 【安全边界】只能围绕简历和业务施压。如遇恶意谩骂，冷静指出其失态并继续施压。
"""

@router.post("/start", response_model=InterviewResponse)
def start_interview(
    req: InterviewStartRequest, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    resume = db.query(Resume).filter(Resume.id == req.resume_id, Resume.user_id == current_user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="未找到该简历")

    new_interview = Interview(
        user_id=current_user.id,
        resume_id=req.resume_id,
        chat_history=[],
        status="ongoing",
        interview_type=req.interview_type
    )
    db.add(new_interview)
    db.commit()
    db.refresh(new_interview)
    return new_interview


@router.post("/chat")
def chat(
    req: ChatRequest, 
    current_user: User = Depends(get_current_user) # 🚨 1. 新增：强制校验 JWT 登录
):
    db = SessionLocal()
    try:
        # 🚨 2. 修复漏洞：不仅要查 ID，还要查这个面试是否属于当前用户！
        interview = db.query(Interview).filter(
            Interview.id == req.interview_id,
            Interview.user_id == current_user.id 
        ).first()
        
        if not interview:
            raise HTTPException(status_code=404, detail="面试记录不存在或无权访问")
            
        resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
        chat_history = list(interview.chat_history or [])
        
        is_safe, warning_msg = check_input_security(req.user_message)
        
        chat_history.append({"role": "user", "content": req.user_message})
        interview.chat_history = chat_history
        flag_modified(interview, "chat_history")
        db.commit()

        resume_json_str = json.dumps(resume.parsed_json, ensure_ascii=False) if resume else "暂无"
        if interview.interview_type == "hr":
            system_content = PROMPT_HR.format(resume_json=resume_json_str)
        elif interview.interview_type == "stress":
            system_content = PROMPT_STRESS.format(resume_json=resume_json_str)
        else:
            system_content = PROMPT_TECH.format(resume_json=resume_json_str)

        system_msg = {"role": "system", "content": system_content}
        messages = [system_msg] + chat_history

        def sse_generator():
            if not is_safe:
                print(f"🛡️ 触发安全拦截: {req.user_message}")
                for char in warning_msg:
                    yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                    time.sleep(0.05)
                
                chat_history.append({"role": "assistant", "content": warning_msg})
                interview.chat_history = chat_history
                flag_modified(interview, "chat_history")
                db.commit()
                db.close()
                yield "data: [DONE]\n\n"
                return

            full_response = ""
            for chunk in get_llm_stream(messages):
                full_response += chunk
                yield f"data: {json.dumps({'content': chunk}, ensure_ascii=False)}\n\n"
                time.sleep(0.05)
            
            if not full_response.strip():
                if interview.interview_type == "hr":
                    mock_question = "（HR面兜底）我看你简历上写了在校经历，能分享一次你遇到的最大团队冲突，以及你是如何解决的吗？"
                elif interview.interview_type == "stress":
                    mock_question = "（压力面兜底）就这？你觉得你这点经验，凭什么让我们公司录用你？"
                else:
                    mock_question = "（技术面兜底）我看你写了 FastAPI，能说说你是怎么处理高并发场景的流式响应的吗？"
                
                for char in mock_question:
                    full_response += char
                    yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                    time.sleep(0.05)

            chat_history.append({"role": "assistant", "content": full_response})
            interview.chat_history = chat_history
            flag_modified(interview, "chat_history")
            db.commit()
            db.close()
            yield "data: [DONE]\n\n"

        return StreamingResponse(sse_generator(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})

    except Exception as e:
        db.close()
        print(f"报错: {e}")
        raise HTTPException(status_code=500, detail="服务器内部错误")