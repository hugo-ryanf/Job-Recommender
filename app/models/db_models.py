from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Job(Base):
    """Tabela de vagas de emprego."""
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(255), unique=True, index=True, nullable=True)
    title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    location = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    seniority = Column(String(100), nullable=True)   # junior, mid, senior, lead
    area = Column(String(100), nullable=True)         # engenharia, design, dados, etc.
    salary_min = Column(Float, nullable=True)
    salary_max = Column(Float, nullable=True)
    url = Column(String(500), nullable=True)
    skills = Column(JSON, nullable=True)             # lista extraída automaticamente
    embedding_id = Column(String(255), nullable=True) # ID no ChromaDB
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    feedbacks = relationship("UserFeedback", back_populates="job")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, index=True)
    raw_text = Column(Text, nullable=True)           # texto bruto do currículo
    skills = Column(JSON, nullable=True)             # lista de habilidades
    experiences = Column(JSON, nullable=True)        # cargos e empresas anteriores
    education = Column(JSON, nullable=True)          # formação acadêmica
    languages = Column(JSON, nullable=True)          # idiomas
    desired_area = Column(String(100), nullable=True)
    desired_seniority = Column(String(100), nullable=True)
    query_text = Column(Text, nullable=True)         # texto montado para embedding
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    feedbacks = relationship("UserFeedback", back_populates="profile")


class UserFeedback(Base):
    __tablename__ = "user_feedbacks"

    id = Column(Integer, primary_key=True, index=True)
    profile_id = Column(Integer, ForeignKey("user_profiles.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1 = relevante, -1 = não relevante
    rank_position = Column(Integer, nullable=True)   # posição em que apareceu
    similarity_score = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    profile = relationship("UserProfile", back_populates="feedbacks")
    job = relationship("Job", back_populates="feedbacks")
