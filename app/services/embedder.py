import hashlib
import chromadb
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

settings = get_settings()

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        print(f"[Embedder] Carregando modelo: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        print("[Embedder] Modelo carregado com sucesso.")
    return _model

def get_chroma_client() -> chromadb.HttpClient:
    return chromadb.HttpClient(
        host=settings.chroma_host,
        port=settings.chroma_port,
    )


def get_jobs_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="jobs",
        metadata={"hnsw:space": "cosine"},  # similaridade por cosseno
    )

def embed_text(text: str) -> list[float]:
    model = get_model()
    return model.encode(text, normalize_embeddings=True).tolist()


def embed_batch(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    model = get_model()
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    return embeddings.tolist()


def job_to_embedding_text(job: dict) -> str:

    parts = []
    if job.get("title"):
        parts.append(f"Cargo: {job['title']}")
    if job.get("area"):
        parts.append(f"Área: {job['area']}")
    if job.get("seniority"):
        parts.append(f"Nível: {job['seniority']}")
    if job.get("skills"):
        skills = job["skills"] if isinstance(job["skills"], list) else []
        parts.append(f"Habilidades: {', '.join(skills)}")
    if job.get("requirements"):
        parts.append(f"Requisitos: {job['requirements'][:500]}")
    if job.get("description"):
        parts.append(f"Descrição: {job['description'][:600]}")
    return "\n".join(parts)


# ── Indexação de vagas ────────────────────────────────────────────────────────

def index_job(job_id: int, job: dict) -> str:

    collection = get_jobs_collection()
    text = job_to_embedding_text(job)
    embedding = embed_text(text)
    embedding_id = f"job_{job_id}"

    collection.upsert(
        ids=[embedding_id],
        embeddings=[embedding],
        metadatas=[{
            "job_id": str(job_id),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "area": job.get("area", "") or "",
            "seniority": job.get("seniority", "") or "",
            "location": job.get("location", "") or "",
        }],
        documents=[text],
    )
    return embedding_id


def index_jobs_batch(jobs: list[tuple[int, dict]]) -> list[str]:

    collection = get_jobs_collection()
    ids, texts, metadatas = [], [], []

    for job_id, job in jobs:
        text = job_to_embedding_text(job)
        embedding_id = f"job_{job_id}"
        ids.append(embedding_id)
        texts.append(text)
        metadatas.append({
            "job_id": str(job_id),
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "area": job.get("area", "") or "",
            "seniority": job.get("seniority", "") or "",
            "location": job.get("location", "") or "",
        })
    
    embeddings = embed_batch(texts) # Gera embeddings em lote

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=texts,
    )
    print(f"[Embedder] {len(ids)} vagas indexadas com sucesso.")
    return ids

def search_similar_jobs( 
    query_text: str,
    n_results: int = 10,
    filter_area: str = None,
    filter_seniority: str = None,
    filter_location: str = None,
) -> list[dict]:
    
    collection = get_jobs_collection()
    query_embedding = embed_text(query_text)

    where_clauses = []
    if filter_area:
        where_clauses.append({"area": {"$eq": filter_area}})
    if filter_seniority:
        where_clauses.append({"seniority": {"$eq": filter_seniority}})
    if filter_location:
        where_clauses.append({"location": {"$contains": filter_location}})

    where = None
    if len(where_clauses) == 1:
        where = where_clauses[0]
    elif len(where_clauses) > 1:
        where = {"$and": where_clauses}

    query_kwargs = {
        "query_embeddings": [query_embedding],
        "n_results": min(n_results, collection.count() or 1),
        "include": ["metadatas", "distances", "documents"],
    }
    if where:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)

    output = []
    if results["ids"] and results["ids"][0]:
        for i, embedding_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            similarity = 1 - (distance / 2)
            metadata = results["metadatas"][0][i]
            output.append({
                "embedding_id": embedding_id,
                "job_id": int(metadata["job_id"]),
                "similarity_score": round(similarity, 4),
                "title": metadata.get("title"),
                "company": metadata.get("company"),
            })
            # ChromaDB retorna distância coseno: 0 = idêntico, 2 = oposto
            # Converti para score de similaridade [0, 1]
    return output
