import argparse
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal, init_db
from app.models.db_models import Job
from app.services.embedder import index_jobs_batch
from app.services.parser import extract_skills


AREA_KEYWORDS = {
    "engenharia": ["software", "backend", "frontend", "fullstack", "devops", "sre", "platform", "infrastructure"],
    "dados": ["data", "analytics", "bi", "machine learning", "ml", "ai", "scientist", "engineer", "analytics"],
    "design": ["design", "ux", "ui", "product designer", "visual"],
    "produto": ["product", "product manager", "pm", "scrum", "agile"],
    "marketing": ["marketing", "growth", "seo", "content", "social media"],
    "vendas": ["sales", "vendas", "account", "comercial", "business development"],
    "rh": ["rh", "hr", "people", "talent", "recruiting", "recruiter"],
    "financeiro": ["finance", "financeiro", "contabil", "accounting", "treasury"],
}

SENIORITY_KEYWORDS = {
    "junior": ["junior", "jr", "entry", "trainee", "intern", "estagi"],
    "mid": ["pleno", "mid", "iii", "ii"],
    "senior": ["senior", "sr", "sênior", "especialista", "specialist"],
    "lead": ["lead", "principal", "staff", "head", "director", "gerente", "manager", "vp", "cto"],
}


def detect_area(text: str) -> str:
    text_lower = text.lower()
    for area, keywords in AREA_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return area
    return "outros"


def detect_seniority(text: str) -> str:
    text_lower = text.lower()
    for level, keywords in SENIORITY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return level
    return "mid"  # padrão


def clean_text(text) -> str:
    if pd.isna(text):
        return ""
    return str(text).strip()


def load_linkedin_dataset(csv_path: str, limit: int = None) -> list[dict]:
    df = pd.read_csv(csv_path, nrows=limit)
    print(f"[Ingestão] {len(df)} vagas carregadas do CSV.")

    jobs = []
    for _, row in df.iterrows():
        title = clean_text(row.get("title", ""))
        company = clean_text(row.get("company_name", row.get("company", "Empresa")))
        description = clean_text(row.get("description", ""))
        location = clean_text(row.get("location", ""))

        if not title or not description or len(description) < 50:
            continue

        full_text = f"{title} {description}"
        skills = extract_skills(full_text)

        jobs.append({
            "external_id": str(row.get("job_id", "")),
            "title": title[:255],
            "company": company[:255],
            "location": location[:255],
            "description": description[:5000],
            "skills": skills,
            "area": detect_area(full_text),
            "seniority": detect_seniority(full_text),
            "url": clean_text(row.get("job_posting_url", row.get("url", ""))),
        })

    print(f"[Ingestão] {len(jobs)} vagas válidas após filtragem.")
    return jobs


def ingest(csv_path: str, limit: int = None, batch_size: int = 100):
    init_db()
    db = SessionLocal()

    try:
        jobs_data = load_linkedin_dataset(csv_path, limit)
        total = len(jobs_data)
        inserted = 0

        for i in range(0, total, batch_size):
            batch = jobs_data[i:i + batch_size]
            db_jobs = []

            for job_dict in batch:
                # Verifica se já existe pelo external_id
                if job_dict.get("external_id"):
                    exists = db.query(Job).filter(
                        Job.external_id == job_dict["external_id"]
                    ).first()
                    if exists:
                        continue

                job = Job(**job_dict)
                db.add(job)
                db_jobs.append(job)

            db.commit()

            # Indexa batch no ChromaDB
            if db_jobs:
                jobs_for_embedding = [
                    (job.id, {
                        "title": job.title,
                        "company": job.company,
                        "area": job.area,
                        "seniority": job.seniority,
                        "skills": job.skills,
                        "description": job.description,
                    })
                    for job in db_jobs
                ]
                embedding_ids = index_jobs_batch(jobs_for_embedding)

                for job, emb_id in zip(db_jobs, embedding_ids):
                    job.embedding_id = emb_id
                db.commit()
                inserted += len(db_jobs)

            print(f"[Ingestão] {min(i + batch_size, total)}/{total} processadas | {inserted} inseridas")

        print(f"\n✅ Ingestão concluída! {inserted} vagas inseridas e indexadas.")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingere dataset de vagas no sistema.")
    parser.add_argument("--csv", required=True, help="Caminho para o arquivo CSV")
    parser.add_argument("--limit", type=int, default=None, help="Limite de vagas a importar")
    parser.add_argument("--batch-size", type=int, default=100, help="Tamanho do batch")
    args = parser.parse_args()

    ingest(args.csv, args.limit, args.batch_size)
