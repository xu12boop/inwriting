from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class InterviewStartRequest(BaseModel):
    resume_id: int
    target_job: str
    interview_type: str = "tech" # 👈 新增

class ChatRequest(BaseModel):
    interview_id: int
    user_message: str
    # 轮次进度：由前端回传，用于在到达上限时让面试官主动收尾。
    # 均带默认值，旧版前端不传也能正常走老流程。
    round_no: int = 0
    max_rounds: int = 6

class InterviewResponse(BaseModel):
    id: int
    resume_id: int
    status: str
    interview_type: str # 👈 新增
    
    class Config:
        from_attributes = True

class ReportResponse(BaseModel):
    id: int
    interview_id: int
    radar_data: Dict[str, Any]
    learning_plan: List[Dict[str, Any]]
    overall_score: float
    summary: str
    # 逐题点评；老报告没有该字段时为 None，前端自动隐藏整块
    question_reviews: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        from_attributes = True
