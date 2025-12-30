import re
import pdfplumber
import spacy
from spacy.matcher import PhraseMatcher
from io import BytesIO

try:
    nlp = spacy.load("pt_core_news_lg")
except OSError:
    nlp = spacy.load("pt_core_news_sm")

TECH_SKILLS = [
    # Linguagens
    "Python", "JavaScript", "TypeScript", "Java", "Kotlin", "Swift", "Go", "Rust",
    "C", "C++", "C#", "PHP", "Ruby", "Scala", "R", "MATLAB", "Perl", "Dart",
    # Frontend
    "React", "Vue", "Angular", "Next.js", "Nuxt", "Svelte", "HTML", "CSS",
    "Tailwind", "Bootstrap", "Redux", "GraphQL", "REST API",
    # Backend
    "Node.js", "Django", "Flask", "FastAPI", "Spring Boot", "Laravel", "Rails",
    "Express", "NestJS", "Gin",
    # Dados & IA
    "Machine Learning", "Deep Learning", "TensorFlow", "PyTorch", "Keras",
    "scikit-learn", "Pandas", "NumPy", "Spark", "Hadoop", "Airflow", "dbt",
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "Elasticsearch",
    "Power BI", "Tableau", "Looker", "BigQuery", "Snowflake", "Databricks",
    "NLP", "Computer Vision", "LLM", "RAG", "LangChain", "OpenAI",
    # DevOps & Cloud
    "Docker", "Kubernetes", "AWS", "Azure", "GCP", "Terraform", "Ansible",
    "CI/CD", "Jenkins", "GitHub Actions", "Linux", "Bash",
    # Mobile
    "Flutter", "React Native", "Android", "iOS", "Jetpack Compose",
    # Outros
    "Git", "Agile", "Scrum", "Kanban", "JIRA", "Figma", "Microservices",
    "Design Patterns", "TDD", "Clean Code", "DDD", "SOLID",
]

SENIORITY_KEYWORDS = {
    "junior": ["junior", "júnior", "jr", "entry level", "trainee", "estágio", "estagiário"],
    "mid": ["pleno", "mid", "mid-level", "intermediário"],
    "senior": ["senior", "sênior", "sr", "sênior", "especialista"],
    "lead": ["lead", "lider", "tech lead", "principal", "staff", "arquiteto"],
}

SECTION_PATTERNS = {
    "experience": r"(experiência|experience|histórico|atuação|trabalho|emprego)",
    "education": r"(formação|educação|education|graduação|faculdade|universidade)",
    "skills": r"(habilidades|competências|skills|tecnologias|ferramentas|stack)",
    "languages": r"(idiomas|languages|línguas)",
}

matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
patterns = [nlp.make_doc(skill.lower()) for skill in TECH_SKILLS]
matcher.add("TECH_SKILL", patterns)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extrai texto de um arquivo PDF."""
    text = ""
    with pdfplumber.open(BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_skills(text: str) -> list[str]:
    doc = nlp(text.lower())
    matches = matcher(doc)
    found = set()
    for _, start, end in matches:
        skill_text = doc[start:end].text
        # Normaliza para o nome original no dicionário
        for original in TECH_SKILLS:
            if original.lower() == skill_text:
                found.add(original)
                break
    return sorted(found)


def extract_seniority(text: str) -> str | None:
    text_lower = text.lower()
    for level, keywords in SENIORITY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return level
    return None


def split_sections(text: str) -> dict[str, str]:
    sections = {"full": text, "experience": "", "education": "", "skills": "", "languages": ""}
    lines = text.split("\n")
    current_section = "full"

    for line in lines:
        line_lower = line.strip().lower()
        matched = False
        for section, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, line_lower) and len(line.strip()) < 50:
                current_section = section
                matched = True
                break
        if not matched:
            sections[current_section] += line + "\n"

    return sections


def extract_experiences(text: str) -> list[dict]:

    doc = nlp(text)
    experiences = []

    # Extrai organizações reconhecidas pelo NER
    orgs = [ent.text for ent in doc.ents if ent.label_ in ("ORG", "PERSON")]

    # Padrão de período: 2020 - 2023 ou jan/2020 - dez/2022
    date_pattern = re.compile(
        r"(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez|january|february|march|"
        r"april|may|june|july|august|september|october|november|december)?[/\s-]?"
        r"(\d{4})\s*[-–]\s*(presente|atual|now|current|\d{4})",
        re.IGNORECASE,
    )

    for match in date_pattern.finditer(text):
        start_idx = max(0, match.start() - 200)
        snippet = text[start_idx:match.end() + 50]
        experiences.append({
            "period": match.group(0),
            "snippet": snippet.strip()[:200],
            "organizations_nearby": [o for o in orgs if o in snippet],
        })

    return experiences[:10]  # limita a 10 experiências


def extract_education(text: str) -> list[dict]:
    education = []
    degree_pattern = re.compile(
        r"(bacharelado|licenciatura|tecnólogo|tecnologia|pós-graduação|mestrado|"
        r"doutorado|mba|especialização|bachelor|master|phd|degree)\s+(?:em\s+)?([^\n,\.]+)",
        re.IGNORECASE,
    )
    for match in degree_pattern.finditer(text):
        education.append({
            "degree": match.group(1).capitalize(),
            "field": match.group(2).strip(),
        })
    return education


def extract_languages(text: str) -> list[str]:
    language_pattern = re.compile(
        r"(inglês|english|português|portuguese|espanhol|spanish|francês|french|"
        r"alemão|german|italiano|italian|mandarim|chinese)\s*[-–:,]?\s*"
        r"(fluente|avançado|intermediário|básico|nativo|fluent|advanced|"
        r"intermediate|basic|native)?",
        re.IGNORECASE,
    )
    languages = []
    for match in language_pattern.finditer(text):
        lang = match.group(1).capitalize()
        level = match.group(2).capitalize() if match.group(2) else ""
        languages.append(f"{lang} {level}".strip())
    return list(set(languages))


def build_query_text(profile: dict) -> str:
    parts = []

    if profile.get("skills"):
        parts.append("Habilidades: " + ", ".join(profile["skills"]))

    if profile.get("experiences"):
        snippets = [exp.get("snippet", "") for exp in profile["experiences"][:3]]
        parts.append("Experiências: " + " | ".join(snippets))

    if profile.get("education"):
        edu_texts = [f"{e['degree']} em {e['field']}" for e in profile["education"]]
        parts.append("Formação: " + ", ".join(edu_texts))

    if profile.get("languages"):
        parts.append("Idiomas: " + ", ".join(profile["languages"]))

    if profile.get("desired_area"):
        parts.append(f"Área desejada: {profile['desired_area']}")

    if profile.get("desired_seniority"):
        parts.append(f"Nível: {profile['desired_seniority']}")

    return "\n".join(parts)


def parse_resume(text: str = None, file_bytes: bytes = None,
                 desired_area: str = None, desired_seniority: str = None) -> dict:

    if file_bytes:
        text = extract_text_from_pdf(file_bytes)
    if not text:
        raise ValueError("É necessário fornecer texto ou arquivo PDF.")

    sections = split_sections(text)

    skills_text = sections["skills"] if sections["skills"] else text
    skills = extract_skills(skills_text)
    if len(skills) < 3:
        skills = extract_skills(text)

    profile = {
        "raw_text": text[:5000],  # limite para não sobrecarregar o bd
        "skills": skills,
        "experiences": extract_experiences(sections["experience"] or text),
        "education": extract_education(sections["education"] or text),
        "languages": extract_languages(sections["languages"] or text),
        "seniority_detected": extract_seniority(text),
        "desired_area": desired_area,
        "desired_seniority": desired_seniority or extract_seniority(text),
    }

    profile["query_text"] = build_query_text(profile)
    return profile
