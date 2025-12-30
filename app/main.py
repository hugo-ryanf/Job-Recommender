from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[App] Inicializando banco de dados...")
    init_db()
    print("[App] Banco de dados pronto.")
    yield
    print("[App] Encerrando aplicação.")


app = FastAPI(
    title="Job Recommender API",
    description="Sistema de recomendação de vagas de emprego com NLP e embeddings semânticos.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/", tags=["saúde"])
def root():
    return {
        "service": "Job Recommender API",
        "version": "1.0.0",
        "status": "online",
        "docs": "/docs",
    }


@app.get("/health", tags=["saúde"])
def health_check():
    return {"status": "healthy"}
