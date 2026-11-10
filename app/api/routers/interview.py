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
from app.core.planner import plan_next_turn
from app.api.deps import get_current_user
from app.utils.security_filter import check_input_security
from app.core.config import settings

router = APIRouter(prefix="/interview", tags=["模拟面试"])

# 最近一次规划结果缓存（演示/调试用，按面试 ID 存储，不落库，避免改动 DB schema）
_plan_cache: dict = {}

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

        # 简历画像只取解析出的正文字段；下划线开头的是系统附注（如 _match 匹配明细），
        # 不作为画像喂给面试官，避免无关内容占提示词预算。
        resume_payload = None
        if resume and isinstance(resume.parsed_json, dict):
            resume_payload = {k: v for k, v in resume.parsed_json.items() if not k.startswith("_")}
        resume_json_str = json.dumps(resume_payload, ensure_ascii=False) if resume_payload else "暂无"

        # —— 轮次进度：由前端回传，用于让面试官在最后一轮主动收尾 ——
        round_no = max(1, int(req.round_no or 0))
        max_rounds = max(1, int(req.max_rounds or 6))
        if interview.interview_type == "hr":
            system_content = PROMPT_HR.format(resume_json=resume_json_str)
        elif interview.interview_type == "stress":
            system_content = PROMPT_STRESS.format(resume_json=resume_json_str)
        else:
            system_content = PROMPT_TECH.format(resume_json=resume_json_str)

        # —— 规划 Agent：在生成提问前，由总控大脑决定策略并检索工具（可解释、可控）——
        # 开场轮（面试官还没提过任何问题）不存在"上一轮回答"可供评估，
        # 此时跳过规划既能避免错误判压，也能把首字延迟从十几秒压到 1-2 秒。
        answered_turns = sum(1 for m in chat_history if m.get("role") == "assistant")
        plan = None
        if settings.enable_planner and answered_turns > 0:
            try:
                plan = plan_next_turn(
                    interview.interview_type,
                    resume_json_str,
                    chat_history,
                )
                _plan_cache[interview.id] = {**plan, "round_no": round_no, "max_rounds": max_rounds}
                print(f"🧠 规划 Agent：decision={plan['decision']} | reasoning={plan['reasoning']} | tools={[t['name'] for t in plan['tool_calls']]}")
                if plan.get("focus"):
                    system_content += (
                        f"\n\n## 本轮面试官策略（由规划 Agent 生成，请据此聚焦）\n"
                        f"决策：{plan['decision']}\n聚焦点：{plan['focus']}"
                    )
            except Exception as e:
                print(f"⚠️ 规划 Agent 异常，回退原流程: {e}")
                plan = None

        # —— 轮次上限：让一场面试有明确边界，而不是无限追问 ——
        # 到达上限的这一轮，面试官先点评再宣布结束，且不再提问；
        # 前端收到本轮内容后会自动跳转评估报告，形成"面完即出报告"的闭环。
        is_last_round = round_no >= max_rounds
        if is_last_round:
            system_content += (
                f"\n\n## 本轮是最后收尾（第 {round_no}/{max_rounds} 轮，已达上限）\n"
                "本次回复只做两件事，顺序不能反：\n"
                "1. 用两句话点评候选人本次面试的整体表现（一句亮点、一句最该改进的地方）。\n"
                "2. 宣布面试结束，最后一句必须原样是「本次面试到此结束」。\n"
                "严禁提出任何新问题，严禁出现问号，严禁要求候选人继续回答或补充说明。"
            )

        system_msg = {"role": "system", "content": system_content}
        messages = [system_msg] + chat_history
        if is_last_round:
            # 追加一条临时指令强化收尾：小模型对 system 尾部的遵从度偏弱，
            # 这条消息不写入 chat_history，只影响本次生成。
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "（系统指令，非候选人发言）面试到这里结束。"
                        "请忽略上面候选人的回答内容，直接给两句话点评，"
                        "并以「本次面试到此结束」结尾。不要再提问。"
                    ),
                }
            )

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
                if is_last_round:
                    mock_question = "你的表达有条理，能把做过的部分讲清楚；最该补的是把结论落到具体指标上。"
                elif interview.interview_type == "hr":
                    mock_question = "（HR面兜底）我看你简历上写了在校经历，能分享一次你遇到的最大团队冲突，以及你是如何解决的吗？"
                elif interview.interview_type == "stress":
                    mock_question = "（压力面兜底）就这？你觉得你这点经验，凭什么让我们公司录用你？"
                else:
                    mock_question = "（技术面兜底）我看你写了 FastAPI，能说说你是怎么处理高并发场景的流式响应的吗？"
                
                for char in mock_question:
                    full_response += char
                    yield f"data: {json.dumps({'content': char}, ensure_ascii=False)}\n\n"
                    time.sleep(0.05)

            # 收尾句由服务端兜底补齐：模型经常点评完就停，漏掉"到此结束"这句话。
            # 与其反复调 prompt，不如在流末尾确定性补一句，保证前端能收到结束信号。
            if is_last_round and "本次面试到此结束" not in full_response:
                tail = "\n\n本次面试到此结束。"
                for char in tail:
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


@router.get("/plan/{interview_id}")
def get_last_plan(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回该面试最近一次规划 Agent 的决策结果（含工具调用与理由），用于可解释性展示。

    始终返回 200 + 统一结构：没有规划记录时 has_plan=False，
    前端据此显示"开场轮不做规划"的占位，而不是当成请求失败。
    数据来源于内存缓存（单 worker 部署）；生产多 worker 需改为落库。
    """
    interview = db.query(Interview).filter(
        Interview.id == interview_id,
        Interview.user_id == current_user.id,
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="面试记录不存在或无权访问")

    plan = _plan_cache.get(interview_id)
    if not plan:
        return {
            "has_plan": False,
            "round_no": 0,
            "decision": "",
            "focus": "",
            "reasoning": "",
            "tool_calls": [],
        }

    return {
        "has_plan": True,
        "round_no": plan.get("round_no", 0),
        "max_rounds": plan.get("max_rounds", 0),
        "decision": plan.get("decision", ""),
        "focus": plan.get("focus", ""),
        "reasoning": plan.get("reasoning", ""),
        "tool_calls": plan.get("tool_calls", []),
    }