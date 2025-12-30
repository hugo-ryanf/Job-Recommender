from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.models.db_models import Job
from app.services.embedder import index_jobs_batch


@celery_app.task(bind=True, max_retries=3)
def index_all_jobs_task(self, batch_size: int = 100):
    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.embedding_id.is_(None)).all()
        total = len(jobs)
        print(f"[Task] Indexando {total} vagas...")

        for i in range(0, total, batch_size):
            batch = jobs[i:i + batch_size]
            jobs_data = [
                (job.id, {
                    "title": job.title,
                    "company": job.company,
                    "area": job.area,
                    "seniority": job.seniority,
                    "skills": job.skills,
                    "requirements": job.requirements,
                    "description": job.description,
                })
                for job in batch
            ]
            embedding_ids = index_jobs_batch(jobs_data)

            # Atualiza embedding_id no banco
            for job, embedding_id in zip(batch, embedding_ids):
                job.embedding_id = embedding_id
            db.commit()

            progress = min(i + batch_size, total)
            print(f"[Task] Progresso: {progress}/{total} vagas indexadas")

        return {"status": "success", "total_indexed": total}
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()


@celery_app.task
def index_single_job_task(job_id: int):
    from app.services.embedder import index_job
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return {"status": "error", "message": "Vaga não encontrada"}

        embedding_id = index_job(job_id, {
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
        return {"status": "success", "embedding_id": embedding_id}
    finally:
        db.close()
