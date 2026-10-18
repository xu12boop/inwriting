from __future__ import annotations
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional
from sqlalchemy import DateTime, Float, ForeignKey, JSON, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.database import Base

if TYPE_CHECKING:
    from app.models.interview import Interview

class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 保证一场面试只有一份报告
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id", ondelete="CASCADE"), unique=True, index=True, nullable=False)
    
    # 用于前端 ECharts 渲染的雷达图数据和推荐学习任务
    radar_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    learning_plan: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    overall_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    interview: Mapped["Interview"] = relationship(back_populates="report")