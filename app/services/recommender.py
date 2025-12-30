import uuid
from sqlalchemy.orm import Session
from app.models.db_models import Job, UserProfile, UserFeedback
from app.models.schemas import RecommendedJob, RecommendResponse
from app.services.embedder import search_similar_jobs, index_job
from app.services.parser import parse_resume


def create_profile_from_text(
    db: Session,
    text: str,
    desired_area: str = None,
    desired_seniority: str = None,
) -> UserProfile:
    parsed = parse_resume(
        text=text,
        desired_area=desired_area,
        desired_seniority=desired_seniority,
    )
    return _save_profile(db, parsed)


def create_profile_from_pdf(
    db: Session,
    file_bytes: bytes,
    desired_area: str = None,
    desired_seniority: str = None,
) -> UserProfile:
    parsed = parse_resume(
        file_bytes=file_bytes,
        desired_area=desired_area,
        desired_seniority=desired_seniority,
    )
    return _save_profile(db, parsed)


def _save_profile(db: Session, parsed: dict) -> UserProfile:
    profile = UserProfile(
        session_id=str(uuid.uuid4()),
        raw_text=parsed.get("raw_text"),
        skills=parsed.get("skills"),
        experiences=parsed.get("experiences"),
        education=parsed.get("education"),
        languages=parsed.get("languages"),
        desired_area=parsed.get("desired_area"),
        desired_seniority=parsed.get("desired_seniority"),
        query_text=parsed.get("query_text"),
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def recommend_jobs(
    db: Session,
    session_id: str,
    n_results: int = 10,
    filter_area: str = None,
    filter_seniority: str = None,
    filter_location: str = None,
) -> RecommendResponse:
    profile = db.query(UserProfile).filter(
        UserProfile.session_id == session_id
    ).first()
    if not profile:
        raise ValueError(f"Perfil não encontrado: {session_id}")

    if not profile.query_text:
        raise ValueError("Perfil sem texto de consulta. Reenvie o currículo.")

    similar = search_similar_jobs(
        query_text=profile.query_text,
        n_results=n_results,
        filter_area=filter_area,
        filter_seniority=filter_seniority,
        filter_location=filter_location,
    )

    job_ids = [s["job_id"] for s in similar]
    jobs_map = {
        job.id: job
        for job in db.query(Job).filter(Job.id.in_(job_ids)).all()
    }

    recommendations = []
    for rank, result in enumerate(similar, start=1):
        job = jobs_map.get(result["job_id"])
        if not job:
            continue
        recommendations.append(RecommendedJob(
            job=job,
            similarity_score=result["similarity_score"],
            rank=rank,
        ))

    profile_summary = _build_profile_summary(profile)

    from app.services.embedder import get_jobs_collection
    total = get_jobs_collection().count()

    return RecommendResponse(
        session_id=session_id,
        profile_summary=profile_summary,
        recommendations=recommendations,
        total_jobs_searched=total,
    )


def _build_profile_summary(profile: UserProfile) -> str:
    parts = []
    if profile.skills:
        top_skills = profile.skills[:8]
        parts.append(f"Habilidades: {', '.join(top_skills)}")
    if profile.desired_area:
        parts.append(f"Área: {profile.desired_area}")
    if profile.desired_seniority:
        parts.append(f"Nível: {profile.desired_seniority}")
    if profile.languages:
        parts.append(f"Idiomas: {', '.join(profile.languages[:3])}")
    return " | ".join(parts) if parts else "Perfil genérico"


def save_feedback(
    db: Session,
    session_id: str,
    job_id: int,
    rating: int,
    rank_position: int = None,
    similarity_score: float = None,
) -> UserFeedback:
    profile = db.query(UserProfile).filter(
        UserProfile.session_id == session_id
    ).first()
    if not profile:
        raise ValueError("Perfil não encontrado.")

    feedback = UserFeedback(
        profile_id=profile.id,
        job_id=job_id,
        rating=rating,
        rank_position=rank_position,
        similarity_score=similarity_score,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return feedback


def add_job(db: Session, job_data: dict) -> Job:
    job = Job(**{k: v for k, v in job_data.items()
                 if k in Job.__table__.columns.keys() and k != "id"})
    db.add(job)
    db.commit()
    db.refresh(job)

    embedding_id = index_job(job.id, {
        "title": job.title,
        "company": job.company,
        "area": job.area,
        "seniority": job.seniority,
        "skills": job.skills,
        "requirements": job.requirements,
        "description": job.description,
    })
    job.embedding_id = embedding_id
    db.commit()
    return job


def calculate_precision_at_k(db: Session, session_id: str, k: int = 10) -> float:

    profile = db.query(UserProfile).filter(
        UserProfile.session_id == session_id
    ).first()
    if not profile:
        return 0.0

    feedbacks = (
        db.query(UserFeedback)
        .filter(
            UserFeedback.profile_id == profile.id,
            UserFeedback.rank_position <= k,
        )
        .all()
    )

    if not feedbacks:
        return 0.0

    relevant = sum(1 for f in feedbacks if f.rating == 1)
    return round(relevant / min(k, len(feedbacks)), 4)
