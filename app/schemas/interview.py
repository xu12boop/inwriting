from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class InterviewStartRequest(BaseModel):
    resume_id: int
    target_job: str
    interview_type: str = "tech" # 👈 新增

class ChatRequest(BaseModel):
    interview_id: int
    user_message: str

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
    
    class Config:
        from_attributes = True