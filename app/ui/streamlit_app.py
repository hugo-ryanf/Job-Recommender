import streamlit as st
import httpx
import json

API_URL = "http://localhost:8000/api/v1"

st.set_page_config(
    page_title="Recomendador de Vagas",
    page_icon="💼",
    layout="wide",
)

# ── Estilo ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .job-card {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        background: white;
    }
    .score-bar { height: 8px; border-radius: 4px; background: #e0e0e0; }
    .score-fill { height: 8px; border-radius: 4px; background: #2E75B6; }
    .skill-tag {
        display: inline-block;
        background: #EBF4FB;
        color: #1F4E79;
        border-radius: 12px;
        padding: 2px 10px;
        margin: 2px;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)


def upload_text(text: str, area: str = None, seniority: str = None) -> dict | None:
    try:
        data = {"text": text}
        if area:
            data["desired_area"] = area
        if seniority:
            data["desired_seniority"] = seniority
        r = httpx.post(f"{API_URL}/profile/text", data=data, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erro ao enviar currículo: {e}")
        return None


def upload_pdf(file_bytes: bytes, filename: str, area: str = None, seniority: str = None) -> dict | None:
    try:
        data = {}
        if area:
            data["desired_area"] = area
        if seniority:
            data["desired_seniority"] = seniority
        r = httpx.post(
            f"{API_URL}/profile/pdf",
            files={"file": (filename, file_bytes, "application/pdf")},
            data=data,
            timeout=60,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erro ao processar PDF: {e}")
        return None


def get_recommendations(session_id: str, n: int, area: str, seniority: str, location: str) -> dict | None:
    try:
        payload = {
            "session_id": session_id,
            "n_results": n,
            "filter_area": area or None,
            "filter_seniority": seniority or None,
            "filter_location": location or None,
        }
        r = httpx.post(f"{API_URL}/recommend", json=payload, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Erro ao buscar recomendações: {e}")
        return None


def send_feedback(session_id: str, job_id: int, rating: int, rank: int, score: float):
    try:
        httpx.post(f"{API_URL}/feedback", json={
            "session_id": session_id,
            "job_id": job_id,
            "rating": rating,
            "rank_position": rank,
            "similarity_score": score,
        }, timeout=10)
    except Exception:
        pass


st.title("💼 Recomendador de Vagas de Emprego")
st.caption("Faça upload do seu currículo e receba vagas personalizadas com base no seu perfil.")

with st.sidebar:
    st.header("⚙️ Configurações")
    n_results = st.slider("Número de recomendações", 5, 30, 10)
    st.divider()
    st.subheader("Filtros")
    filter_area = st.selectbox(
        "Área", ["", "engenharia", "dados", "design", "produto", "marketing", "vendas", "rh", "financeiro", "outros"]
    )
    filter_seniority = st.selectbox("Senioridade", ["", "junior", "mid", "senior", "lead"])
    filter_location = st.text_input("Localização (ex: São Paulo)")
    st.divider()
    st.caption("Modelo: paraphrase-multilingual-mpnet-base-v2")

tab1, tab2, tab3 = st.tabs(["📄 Enviar Currículo", "🔍 Recomendações", "📊 Meu Perfil"])

with tab1:
    st.subheader("Envie seu currículo")
    input_type = st.radio("Formato", ["PDF", "Texto"], horizontal=True)

    col1, col2 = st.columns(2)
    with col1:
        pref_area = st.selectbox(
            "Área de interesse",
            ["", "engenharia", "dados", "design", "produto", "marketing", "vendas", "rh", "financeiro"],
            key="pref_area"
        )
    with col2:
        pref_seniority = st.selectbox(
            "Nível desejado",
            ["", "junior", "mid", "senior", "lead"],
            key="pref_seniority"
        )

    profile = None

    if input_type == "PDF":
        uploaded = st.file_uploader("Arraste ou selecione o PDF", type=["pdf"])
        if uploaded and st.button("📤 Processar currículo", type="primary"):
            with st.spinner("Analisando seu currículo..."):
                profile = upload_pdf(
                    uploaded.read(), uploaded.name,
                    pref_area or None, pref_seniority or None
                )
    else:
        resume_text = st.text_area(
            "Cole o texto do seu currículo aqui",
            height=300,
            placeholder="Exemplo:\nDesenvolvedor Python com 4 anos de experiência em backend...\n\nHabilidades: Python, FastAPI, PostgreSQL, Docker, AWS...\n\nFormação: Bacharel em Ciência da Computação - USP (2020)"
        )
        if resume_text and st.button("📤 Processar currículo", type="primary"):
            with st.spinner("Analisando seu currículo..."):
                profile = upload_text(resume_text, pref_area or None, pref_seniority or None)

    if profile:
        st.session_state["session_id"] = profile["session_id"]
        st.session_state["profile"] = profile
        st.success(f"✅ Currículo processado! Session ID: `{profile['session_id']}`")

        if profile.get("skills"):
            st.subheader("🛠️ Habilidades detectadas")
            skills_html = " ".join(
                f'<span class="skill-tag">{s}</span>' for s in profile["skills"]
            )
            st.markdown(skills_html, unsafe_allow_html=True)

        st.info("Acesse a aba **Recomendações** para ver as vagas!")


with tab2:
    st.subheader("Vagas recomendadas para você")

    if "session_id" not in st.session_state:
        st.warning("⬅️ Primeiro envie seu currículo na aba anterior.")
    else:
        if st.button("🔍 Buscar vagas", type="primary"):
            with st.spinner("Buscando vagas compatíveis..."):
                result = get_recommendations(
                    st.session_state["session_id"],
                    n_results,
                    filter_area or None,
                    filter_seniority or None,
                    filter_location or None,
                )
                if result:
                    st.session_state["recommendations"] = result

        if "recommendations" in st.session_state:
            rec = st.session_state["recommendations"]
            st.caption(f"🔎 Busca em {rec.get('total_jobs_searched', 0):,} vagas | Perfil: _{rec.get('profile_summary', '')}_")
            st.divider()

            for item in rec.get("recommendations", []):
                job = item["job"]
                score = item["similarity_score"]
                rank = item["rank"]
                score_pct = int(score * 100)
                color = "#27AE60" if score_pct >= 75 else "#2E75B6" if score_pct >= 50 else "#E67E22"

                with st.container():
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"### {rank}. {job['title']}")
                        st.markdown(f"🏢 **{job['company']}** &nbsp;|&nbsp; 📍 {job.get('location', 'Remoto/Não informado')}")
                        if job.get("skills"):
                            skills_html = " ".join(
                                f'<span class="skill-tag">{s}</span>'
                                for s in (job["skills"] or [])[:8]
                            )
                            st.markdown(skills_html, unsafe_allow_html=True)
                        st.markdown(
                            f'<div style="margin-top:8px"><div class="score-bar"><div class="score-fill" style="width:{score_pct}%;background:{color}"></div></div>'
                            f'<small style="color:{color}">Compatibilidade: {score_pct}%</small></div>',
                            unsafe_allow_html=True
                        )
                        if job.get("description"):
                            with st.expander("Ver descrição"):
                                st.write(job["description"][:800] + "...")

                    with col2:
                        st.markdown("<br><br>", unsafe_allow_html=True)
                        if st.button("👍 Relevante", key=f"up_{job['id']}"):
                            send_feedback(st.session_state["session_id"], job["id"], 1, rank, score)
                            st.success("Obrigado!")
                        if st.button("👎 Não relevante", key=f"dn_{job['id']}"):
                            send_feedback(st.session_state["session_id"], job["id"], -1, rank, score)
                            st.info("Feedback registrado!")
                        if job.get("url"):
                            st.link_button("🔗 Ver vaga", job["url"])

                    st.divider()


with tab3:
    st.subheader("Meu Perfil Extraído")

    if "profile" not in st.session_state:
        st.warning("⬅️ Primeiro envie seu currículo.")
    else:
        profile = st.session_state["profile"]
        col1, col2 = st.columns(2)

        with col1:
            st.metric("Session ID", profile["session_id"][:8] + "...")
            if profile.get("desired_area"):
                st.metric("Área de interesse", profile["desired_area"].capitalize())
            if profile.get("desired_seniority"):
                st.metric("Nível", profile["desired_seniority"].capitalize())

        with col2:
            if profile.get("languages"):
                st.write("**Idiomas detectados:**")
                for lang in profile["languages"]:
                    st.write(f"• {lang}")
            if profile.get("education"):
                st.write("**Formação:**")
                for edu in profile["education"]:
                    st.write(f"• {edu.get('degree')} em {edu.get('field')}")

        if profile.get("experiences"):
            st.subheader("Experiências detectadas")
            for exp in profile["experiences"][:5]:
                st.write(f"**Período:** {exp.get('period', 'N/A')}")
                st.caption(exp.get("snippet", "")[:200])
                st.divider()

        st.subheader("Texto de consulta gerado")
        st.code(profile.get("query_text", ""), language=None)
