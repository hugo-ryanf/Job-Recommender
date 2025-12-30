from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.models.schemas import (
    JobCreate, JobResponse,
    ProfileResponse,
    RecommendRequest, RecommendResponse,
    FeedbackCreate, FeedbackResponse,
)
from app.services import recommender

router = APIRouter()

# job openings 
@router.post("/jobs", response_model=JobResponse, tags=["vagas"])
def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    job = recommender.add_job(db, job_data.model_dump())
    return job


@router.get("/jobs/{job_id}", response_model=JobResponse, tags=["vagas"])
def get_job(job_id: int, db: Session = Depends(get_db)):
    from app.models.db_models import Job
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Vaga não encontrada")
    return job


@router.get("/jobs", response_model=list[JobResponse], tags=["vagas"])
def list_jobs(
    skip: int = 0,
    limit: int = 20,
    area: Optional[str] = None,
    seniority: Optional[str] = None,
    db: Session = Depends(get_db),
):
    from app.models.db_models import Job
    query = db.query(Job)
    if area:
        query = query.filter(Job.area == area)
    if seniority:
        query = query.filter(Job.seniority == seniority)
    return query.offset(skip).limit(limit).all()


# perfil / curriculo

@router.post("/profile/text", response_model=ProfileResponse, tags=["perfil"])
def upload_resume_text(
    text: str = Form(...),
    desired_area: Optional[str] = Form(None),
    desired_seniority: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    
    try:
        profile = recommender.create_profile_from_text(
            db, text, desired_area, desired_seniority
        )
        return profile
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/profile/pdf", response_model=ProfileResponse, tags=["perfil"])
async def upload_resume_pdf(
    file: UploadFile = File(...),
    desired_area: Optional[str] = Form(None),
    desired_seniority: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas arquivos PDF são aceitos.")

    file_bytes = await file.read()
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=413, detail="Arquivo muito grande (máx. 10MB).")

    try:
        profile = recommender.create_profile_from_pdf(
            db, file_bytes, desired_area, desired_seniority
        )
        return profile
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/profile/{session_id}", response_model=ProfileResponse, tags=["perfil"])
def get_profile(session_id: str, db: Session = Depends(get_db)):
    from app.models.db_models import UserProfile
    profile = db.query(UserProfile).filter(
        UserProfile.session_id == session_id
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Perfil não encontrado")
    return profile


# ── Recomendações ─────────────────────────────────────────────────────────────

@router.post("/recommend", response_model=RecommendResponse, tags=["recomendações"])
def get_recommendations(request: RecommendRequest, db: Session = Depends(get_db)):
    
    try:
        return recommender.recommend_jobs(
            db=db,
            session_id=request.session_id,
            n_results=request.n_results,
            filter_area=request.filter_area,
            filter_seniority=request.filter_seniority,
            filter_location=request.filter_location,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

#Feedback 
@router.post("/feedback", response_model=FeedbackResponse, tags=["feedback"])
def submit_feedback(feedback: FeedbackCreate, db: Session = Depends(get_db)):
    try:
        saved = recommender.save_feedback(
            db=db,
            session_id=feedback.session_id,
            job_id=feedback.job_id,
            rating=feedback.rating,
            rank_position=feedback.rank_position,
            similarity_score=feedback.similarity_score,
        )
        msg = "Obrigado! Vaga marcada como relevante." if feedback.rating == 1 \
            else "Entendido! Usaremos isso para melhorar suas recomendações."
        return FeedbackResponse(id=saved.id, message=msg)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# metrics
@router.get("/metrics/{session_id}", tags=["métricas"])
def get_metrics(session_id: str, k: int = 10, db: Session = Depends(get_db)):
    """Retorna Precision@K para um perfil com feedback coletado."""
    precision = recommender.calculate_precision_at_k(db, session_id, k)
    return {
        "session_id": session_id,
        "precision_at_k": precision,
        "k": k,
        "message": f"Precision@{k} = {precision:.2%}",
    }
