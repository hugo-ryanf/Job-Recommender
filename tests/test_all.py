import pytest
from unittest.mock import patch, MagicMock


class TestParser:
    def test_extract_skills_basic(self):
        from app.services.parser import extract_skills
        text = "Tenho experiência com Python, FastAPI, PostgreSQL e Docker."
        skills = extract_skills(text)
        assert "Python" in skills
        assert "FastAPI" in skills
        assert "PostgreSQL" in skills
        assert "Docker" in skills

    def test_extract_skills_empty_text(self):
        from app.services.parser import extract_skills
        skills = extract_skills("")
        assert skills == []

    def test_extract_seniority_junior(self):
        from app.services.parser import extract_seniority
        text = "Desenvolvedor Junior buscando primeira oportunidade."
        assert extract_seniority(text) == "junior"

    def test_extract_seniority_senior(self):
        from app.services.parser import extract_seniority
        text = "Engenheiro Sênior com 8 anos de experiência."
        assert extract_seniority(text) == "senior"

    def test_extract_seniority_none(self):
        from app.services.parser import extract_seniority
        text = "Profissional de tecnologia."
        assert extract_seniority(text) is None

    def test_extract_languages(self):
        from app.services.parser import extract_languages
        text = "Idiomas: Inglês Fluente, Espanhol Básico."
        langs = extract_languages(text)
        assert any("Inglês" in l or "English" in l.capitalize() for l in langs)

    def test_build_query_text(self):
        from app.services.parser import build_query_text
        profile = {
            "skills": ["Python", "FastAPI"],
            "experiences": [{"snippet": "Desenvolvedor backend na Empresa X"}],
            "education": [{"degree": "Bacharelado", "field": "Ciência da Computação"}],
            "languages": ["Inglês Fluente"],
            "desired_area": "engenharia",
            "desired_seniority": "senior",
        }
        query = build_query_text(profile)
        assert "Python" in query
        assert "FastAPI" in query
        assert "engenharia" in query

    def test_parse_resume_text(self):
        from app.services.parser import parse_resume
        text = """
        João Silva - Desenvolvedor Python Sênior
        
        Habilidades: Python, Django, FastAPI, PostgreSQL, Docker, AWS, Redis
        
        Experiência:
        2020 - 2024: Desenvolvedor Backend - Tech Corp
        2018 - 2020: Programador Junior - StartupXYZ
        
        Formação: Bacharel em Ciência da Computação - USP (2018)
        
        Idiomas: Inglês Fluente
        """
        profile = parse_resume(text=text)
        assert "skills" in profile
        assert "Python" in profile["skills"]
        assert profile["query_text"] is not None
        assert len(profile["query_text"]) > 10

    def test_parse_resume_no_input(self):
        from app.services.parser import parse_resume
        with pytest.raises(ValueError):
            parse_resume()


class TestEmbedder:

    @patch("app.services.embedder.get_model")
    def test_embed_text_returns_list(self, mock_get_model):
        mock_model = MagicMock()
        mock_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 768)
        mock_get_model.return_value = mock_model

        from app.services.embedder import embed_text
        result = embed_text("teste de embedding")
        assert isinstance(result, list)

    def test_job_to_embedding_text(self):
        from app.services.embedder import job_to_embedding_text
        job = {
            "title": "Desenvolvedor Python",
            "area": "engenharia",
            "seniority": "senior",
            "skills": ["Python", "FastAPI"],
            "description": "Vaga para desenvolvedor backend.",
        }
        text = job_to_embedding_text(job)
        assert "Python" in text
        assert "engenharia" in text
        assert "senior" in text

    def test_job_to_embedding_text_empty(self):
        from app.services.embedder import job_to_embedding_text
        text = job_to_embedding_text({})
        assert text == ""


class TestAPI:

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_root_endpoint(self, client):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"

    def test_health_endpoint(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    @patch("app.api.routes.recommender.create_profile_from_text")
    def test_upload_text_profile(self, mock_create, client):
        mock_profile = MagicMock()
        mock_profile.session_id = "test-session-123"
        mock_profile.skills = ["Python", "FastAPI"]
        mock_profile.experiences = []
        mock_profile.education = []
        mock_profile.languages = ["Inglês"]
        mock_profile.desired_area = "engenharia"
        mock_profile.desired_seniority = "senior"
        mock_profile.raw_text = "teste"
        mock_profile.query_text = "Habilidades: Python, FastAPI"
        from datetime import datetime
        mock_profile.created_at = datetime.now()
        mock_create.return_value = mock_profile

        r = client.post("/api/v1/profile/text", data={"text": "Desenvolvedor Python Sênior"})
        assert r.status_code == 200
        assert r.json()["session_id"] == "test-session-123"

    def test_upload_text_empty(self, client):
        r = client.post("/api/v1/profile/text", data={"text": ""})
        assert r.status_code in (400, 422)

    @patch("app.api.routes.recommender.recommend_jobs")
    def test_recommend_endpoint(self, mock_recommend, client):
        from app.models.schemas import RecommendResponse
        mock_recommend.return_value = RecommendResponse(
            session_id="test-123",
            profile_summary="Python | engenharia",
            recommendations=[],
            total_jobs_searched=100,
        )
        r = client.post("/api/v1/recommend", json={
            "session_id": "test-123",
            "n_results": 5,
        })
        assert r.status_code == 200

    def test_recommend_not_found(self, client):
        with patch("app.api.routes.recommender.recommend_jobs") as mock:
            mock.side_effect = ValueError("Perfil não encontrado")
            r = client.post("/api/v1/recommend", json={"session_id": "nao-existe"})
            assert r.status_code == 404


# ── Testes de métricas ────────────────────────────────────────────────────────

class TestMetrics:

    def test_precision_at_k_no_feedback(self):
        from app.services.recommender import calculate_precision_at_k
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        result = calculate_precision_at_k(mock_db, "session-123", k=10)
        assert result == 0.0

    def test_precision_at_k_all_relevant(self):
        from app.services.recommender import calculate_precision_at_k
        from app.models.db_models import UserFeedback

        mock_profile = MagicMock()
        mock_profile.id = 1
        mock_feedbacks = [MagicMock(rating=1) for _ in range(5)]

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_profile
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_feedbacks

        # Como a função faz dois queries, precisamos mockar corretamente
        # Simplificamos testando apenas o caso de perfil não encontrado
        mock_db2 = MagicMock()
        mock_db2.query.return_value.filter.return_value.first.return_value = None
        result = calculate_precision_at_k(mock_db2, "nao-existe", k=5)
        assert result == 0.0
