import json
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.resume import Resume
from app.models.user import User
from app.schemas.resume import ResumeResponse
from app.utils.file_parser import extract_text_from_pdf, extract_text_from_docx
from app.core.llm import get_llm_response
from app.core.config import settings
from app.api.deps import get_current_user
from app.core.rag import add_jd_to_kb, get_best_match_reranked
from app.core.jsonutil import loads_object

router = APIRouter(prefix="/resume", tags=["简历解析"])

# 重排最高分低于该阈值，说明库里没有真正相近的岗位，需要先补一条再检索
RERANK_MIN_SCORE = 55.0


def _loads_json(raw: str) -> dict:
    """容错解析大模型返回的 JSON：去掉 ``` 围栏与前后杂字，失败则抛异常由调用方兜底。"""
    return loads_object(raw)


def _normalize_str_list(value, limit: int = 5) -> list[str]:
    """把模型可能返回的 str / list 统一成干净字符串列表，并截断长度与条数。"""
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        return []
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            out.append(text[:40])
        if len(out) >= limit:
            break
    return out


def _normalize_matched(value, limit: int = 5) -> list[dict]:
    """逐条命中：{"requirement", "evidence"}；模型偶尔返回纯字符串，统一降级处理。"""
    if not isinstance(value, list):
        return []
    out: list[dict] = []
    for item in value:
        if isinstance(item, dict):
            req = str(item.get("requirement", "")).strip()[:40]
            ev = str(item.get("evidence", "")).strip()[:60]
            if req or ev:
                out.append({"requirement": req, "evidence": ev})
        else:
            text = str(item).strip()
            if text:
                out.append({"requirement": text[:40], "evidence": ""})
        if len(out) >= limit:
            break
    return out

RESUME_PARSE_PROMPT = """
你是一个专业的 HR 简历解析助手。请从以下简历文本中提取关键信息，并严格按 JSON 格式输出。
不要输出任何其他的解释文字，也不要加 ```json 这样的标记，只输出纯 JSON 字符串。
JSON 结构要求：
{{
    "name": "求职者姓名",
    "skills": ["技能1", "技能2"],
    "projects": [{{"name": "项目名称", "role": "担任角色", "description": "项目描述"}}],
    "education": "最高学历及学校"
}}
简历文本如下：
{resume_text}
"""

# 🚨 Agent 工作流：分析简历与 JD 的匹配度（结论 + 逐条命中 + 差距项，支撑"可溯源"）
MATCH_AGENT_PROMPT = """
你是一位高级技术评估专家。这是候选人的简历特征：
{resume_json}

这是目标岗位的 JD 要求：
{jd_text}

请对比两者，严格输出纯 JSON（不要任何 Markdown 包裹、不要解释文字）：
{{
  "match_score": 0 到 100 的整数,
  "matched": [{{"requirement": "JD 中的一条具体要求", "evidence": "简历里对应的经历或技能"}}],
  "gaps": ["JD 要求但简历里没有或明显偏弱的能力"],
  "verdict": "一句话结论，例如：基础匹配，缺消息队列实战"
}}

约束：
1. matched 最多 5 条，gaps 最多 3 条；每条不超过 30 个字。
2. 只依据 JD 与简历文本作判断，不得臆造简历里没有的经历。
3. gaps 要具体到能力点（如"消息队列实战"），不要写"经验不足"这类空话。
"""

def _parse_and_match(raw_text: str, target_job: str) -> tuple[dict, float, dict]:
    """同步执行「简历解析 → RAG 检索 → 匹配打分」三段耗时逻辑。

    全部是阻塞调用（模型 HTTP 请求 + 向量库检索），必须放在线程池里跑，
    不能直接写在 async 路由中，否则会独占事件循环导致同 worker 其它请求排队。
    返回 (parsed_data, match_score, match_detail)，语义与原先内联版本完全一致。
    """
    # 1. 解析简历
    prompt = RESUME_PARSE_PROMPT.format(resume_text=raw_text[:4000])
    ai_response = get_llm_response([{"role": "user", "content": prompt}])

    try:
        parsed_data = loads_object(ai_response)
    except Exception:
        parsed_data = {"name": "张三", "skills": ["Python"], "projects": [], "education": "本科"}

    # 2. 获取 JD（RAG：向量 Top-K 召回 → 大模型重排 → 引用溯源）
    match = get_best_match_reranked(target_job, k=5)
    # 库中没有相近岗位（空库 / 重排最高分偏低）时冷启动补一条该岗位的通用要求，再重检。
    # 只看"是否为空"是不够的：库里有别的岗位时会命中一条不相关的 JD，引用就失真了。
    if not match["job_name"] or float(match.get("score") or 0) < RERANK_MIN_SCORE:
        cold_jd = (
            f"【{target_job}】\n"
            f"1. 具备 {target_job} 相关的项目经验，能说清自己做过的部分与取舍；\n"
            "2. 熟悉 Python 或同等工作语言，能独立完成模块开发与联调；\n"
            "3. 具备基本的工程习惯：版本管理、接口约定、日志与异常处理；\n"
            "4. 遇到问题能定位到具体环节，而不是只描述现象。"
        )
        add_jd_to_kb(target_job, cold_jd)
        match = get_best_match_reranked(target_job, k=5)
    jd_text = match["jd"]

    # 3. 计算匹配度，并把检索引用一并注入，保证结论可溯源
    match_prompt = MATCH_AGENT_PROMPT.format(
        resume_json=json.dumps(parsed_data, ensure_ascii=False),
        jd_text=jd_text
    ) + f"\n\n【检索依据】{match['citation']}"
    match_res = get_llm_response([{"role": "user", "content": match_prompt}])

    # 解析失败只影响"明细"，不影响主流程：分数仍给兜底值，界面隐藏差距项与依据。
    match_detail = {
        "job_name": match["job_name"],
        "citation": match["citation"],
        "jd_excerpt": jd_text[:600],
        "retrieval_score": round(float(match.get("score") or 0), 1),
        "matched": [],
        "gaps": [],
        "verdict": "",
    }
    try:
        parsed_match = _loads_json(match_res)
        match_score = float(parsed_match.get("match_score", 70.0))
        match_detail["matched"] = _normalize_matched(parsed_match.get("matched"))
        match_detail["gaps"] = _normalize_str_list(parsed_match.get("gaps"), limit=3)
        match_detail["verdict"] = str(parsed_match.get("verdict", ""))[:60]
    except Exception as e:
        print(f"⚠️ 匹配明细解析失败，仅保留分数: {e}")
        match_score = 75.0  # 兜底

    return parsed_data, match_score, match_detail


@router.post("/upload", response_model=ResumeResponse)
async def upload_and_parse_resume(
    target_job: str = Form(..., description="目标岗位"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) # 🔐 引入 JWT 鉴权
):
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx")):
        raise HTTPException(status_code=400, detail="仅支持 PDF 或 DOCX")

    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大，请上传 {settings.max_upload_mb}MB 以内的简历",
        )
    raw_text = extract_text_from_pdf(content) if filename.endswith(".pdf") else extract_text_from_docx(content)
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="无法提取到文本")

    # 解析 + 检索 + 匹配三段都是同步阻塞调用（requests 打模型、Chroma 检索），
    # 合起来 20~100 秒。本路由是 async def，若直接在此执行会独占事件循环，
    # 同 worker 内的其它请求（含 /health、登录）全部排队——并发上传时表现为
    # 「毫秒级接口要等上百秒」。因此整体丢进线程池，让事件循环保持可调度。
    parsed_data, match_score, match_detail = await run_in_threadpool(
        _parse_and_match, raw_text, target_job
    )

    # 明细挂到 parsed_json 的 _match 键：复用已有 JSON 列，不新增数据库字段（免迁移）。
    # interview.py 在构造简历画像时会剔除下划线开头的键，不影响面试官提示词。
    if isinstance(parsed_data, dict):
        parsed_data["_match"] = match_detail

    # 4. 存库 (使用当前登录用户的 ID)
    new_resume = Resume(
        user_id=current_user.id, # ✅ 真实的用户 ID
        target_job=target_job,
        original_filename=file.filename,
        parsed_json=parsed_data,
        match_score=match_score
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    return new_resume