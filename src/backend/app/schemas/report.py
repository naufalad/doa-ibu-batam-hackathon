"""Pydantic schemas for LLM-generated user activity reports."""

from datetime import datetime

from pydantic import BaseModel


class TransactionSummary(BaseModel):
    """One historical waste submission, fed into the report prompt."""

    date: datetime
    waste_label: str
    num_objects: int
    points_awarded: int


class UserReportOut(BaseModel):
    user_id: int
    generated_at: datetime
    period_days: int
    total_submissions: int
    total_points: int
    top_categories: list[str]
    narrative: str  # LLM-generated natural-language summary
    llm_provider: str
