from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# jobs openinga
class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: str
    requirements: Optional[str] = None
    seniority: Optional[str] = None
    area: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    url: Optional[str] = None
    skills: Optional[list[str]] = None


class JobCreate(JobBase):
    external_id: Optional[str] = None


class JobResponse(JobBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# user profile / resume
class ProfileCreate(BaseModel):
    raw_text: Optional[str] = None
    skills: Optional[list[str]] = None
    experiences: Optional[list[dict]] = None
    education: Optional[list[dict]] = None
    languages: Optional[list[str]] = None
    desired_area: Optional[str] = None
    desired_seniority: Optional[str] = None


class ProfileResponse(ProfileCreate):
    id: int
    session_id: str
    query_text: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# recommendations
class RecommendRequest(BaseModel):
    session_id: str
    n_results: int = Field(default=10, ge=1, le=50)
    filter_area: Optional[str] = None
    filter_seniority: Optional[str] = None
    filter_location: Optional[str] = None


class RecommendedJob(BaseModel):
    job: JobResponse
    similarity_score: float
    rank: int


class RecommendResponse(BaseModel):
    session_id: str
    profile_summary: str
    recommendations: list[RecommendedJob]
    total_jobs_searched: int


# Feedback 
class FeedbackCreate(BaseModel):
    session_id: str
    job_id: int
    rating: int = Field(..., ge=-1, le=1, description="1 = relevante, -1 = não relevante")
    rank_position: Optional[int] = None
    similarity_score: Optional[float] = None


class FeedbackResponse(BaseModel):
    id: int
    message: str
