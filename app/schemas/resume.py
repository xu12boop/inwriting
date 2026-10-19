from pydantic import BaseModel
from typing import Optional, Dict, Any

class ResumeResponse(BaseModel):
    id: int
    target_job: str
    original_filename: Optional[str]
    parsed_json: Optional[Dict[str, Any]]
    match_score: Optional[float]

    class Config:
        from_attributes = True