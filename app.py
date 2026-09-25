"""DocuMind AI: generate and improve software documentation from user input or uploaded notes."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from knowledge_base import format_context, load_text_files, retrieve
from llm_client import ask_gemini


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "document"


def save_version(name: str, kind: str, value: dict | str) -> None:
    workspace = Path("workspace")
    workspace.mkdir(exist_ok=True)
    versions = st.session_state.setdefault("versions", [])
    path = workspace / f"{slugify(name)}-v{len(versions) + 1}.json"
    path.write_text(json.dumps(value, indent=2) if isinstance(value, dict) else value, encoding="utf-8")
    versions.append({"type": kind, "path": str(path), "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")})


def features_from_text(text: str) -> list[str]:
    """Extract useful feature candidates from headings and bullet points."""
    found = []
    for line in text.splitlines():
        line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        line = re.sub(r"^#+\s*", "", line).strip()
        if 2 < len(line) < 100 and line and not line.endswith(('.', ':')):
            if line.lower() not in {x.lower() for x in found}:
                found.append(line)
    return found[:20]


def offline_document(project: dict, kind: str, source: str) -> dict | str:
    features = project["features"] or features_from_text(source)
    name = project["name"] or "Untitled project"
    idea = project["idea"] or source[:500] or "A software project."
    if kind == "Improved text":
        lines = [x.strip() for x in source.splitlines() if x.strip()]
        return "# Improved document\n\n## Overview\n" + ("\n\n".join(f"- {x}" for x in lines) if lines else "No source text was provided.") + "\n\n## Acceptance criteria\n- Requirements are clear, observable, and testable."
    if kind == "SRS":
        requirements, tests = [], []
        for i, feature in enumerate(features, 1):
            rid = f"REQ-{i:02d}"
            requirements.append({"id": rid, "feature": feature, "text": f"The system shall support {feature.lower()}."})
            tests += [
                {"id": f"TC-{i * 2 - 1:02d}", "requirement_id": rid, "type": "positive", "description": f"Valid {feature.lower()} succeeds."},
                {"id": f"TC-{i * 2:02d}", "requirement_id": rid, "type": "negative", "description": f"Invalid {feature.lower()} is rejected gracefully."},
            ]
        return {"document_type": "SRS", "project": name, "summary": idea, "requirements": requirements, "test_cases": tests}
    if kind == "PRD":
        return {"document_type": "PRD", "project": name, "goal": idea, "requirements": [{"id": f"PRD-{i:02d}", "requirement": f"The system shall support {f.lower()}"} for i, f in enumerate(features, 1)], "success_metrics": ["Users can complete the main task", "The product is easy to understand"]}
    return {"document_type": "User stories", "project": name, "stories": [{"id": f"US-{i:02d}", "as_a": "User", "i_want": f.lower(), "so_that": "I can achieve my goal", "acceptance_criteria": [f"The {f.lower()} flow is available.", "Invalid input is handled clearly."]} for i, f in enumerate(features, 1)]}


def quality(document: dict | str) -> dict:
    if isinstance(document, str):
        score = 75 if len(document.split()) >= 40 else 55
        issues = [] if score == 75 else ["The document is short and may lack detail."]
    elif document.get("document_type") == "SRS":
        reqs, tests = document.get("requirements", []), document.get("test_cases", [])
        complete = sum({t.get("type") for t in tests if t.get("requirement_id") == r.get("id")} >= {"positive", "negative"} for r in reqs)
        score = round(complete / len(reqs) * 100, 1) if reqs else 0
        issues = [] if score == 100 else ["Some requirements do not have both positive and negative tests."]
    else:
        key = "requirements" if document.get("document_type") == "PRD" else "stories"
        score, issues = (82, []) if document.get(key) else (0, [f"{key.title()} are missing."])
    return {"score": score, "issues": issues, "recommendations": ["Add clear acceptance criteria.", "Remove ambiguous or duplicate statements."]}


def app() -> None:
    st.set_page_config(page_title="DocuMind AI", page_icon="📚", layout="wide")
    st.title("📚 DocuMind AI")
    st.caption("Automatically generate and improve documentation from your project description, pasted draft, or uploaded notes.")
    st.session_state.setdefault("versions", [])
    st.session_state.setdefault("current_document", None)

    with st.sidebar:
        st.header("Project setup")
        project_name = st.text_input("Project name", placeholder="My application")
        project_idea = st.text_area("Project description", placeholder="What does the application do?", height=110)
        features_raw = st.text_area("Features (one per line, optional)", placeholder="User login\nSearch\nReports", height=110)
        kind = st.selectbox("Document type", ["SRS", "PRD", "User stories", "Improved text"])
        api_key = st.text_input("Gemini API key (optional)", type="password")
        offline = st.toggle("Offline mode", value=not bool(api_key or os.getenv("GEMINI_API_KEY")))
        uploaded = st.file_uploader("Upload project notes (.txt)", type=["txt"], accept_multiple_files=True)
        auto_generate = st.checkbox("Automatically generate when notes are uploaded", value=True)

    uploaded_text = [(f.name, f.getvalue().decode("utf-8", errors="ignore")) for f in (uploaded or [])]
    uploaded_source = "\n\n".join(f"# {name}\n{text}" for name, text in uploaded_text)
    source = st.text_area("Document draft / source text", value=uploaded_source, height=250, placeholder="Paste a draft here, or upload .txt notes above.")
    source = source.strip() or uploaded_source.strip()

    explicit_features = [x.strip() for x in features_raw.splitlines() if x.strip()]
    detected_features = features_from_text(source)
    features = explicit_features or detected_features
    project = {"name": project_name.strip(), "idea": project_idea.strip(), "features": features}

    if uploaded_source:
        st.success(f"Loaded {len(uploaded_text)} note file(s). The uploaded content is now the source document.")
        if not explicit_features and detected_features:
            st.info(f"Automatically detected {len(detected_features)} feature/section candidate(s) from the uploaded notes.")

    chunks = load_text_files("data", uploaded_text)
    query = " ".join(x for x in [project_name, project_idea, " ".join(features)] if x)
    with st.expander("Retrieved project evidence"):
        matches = retrieve(query, chunks) if query else []
        if matches:
            for chunk, score in matches:
                st.markdown(f"**{chunk.source}** · relevance `{score:.2f}`")
                st.write(chunk.text)
        else:
            st.write("Upload notes or add files to the data folder to retrieve evidence.")

    def generate() -> None:
        if not project_name.strip() and not source:
            st.warning("Enter a project name or upload/paste source notes first.")
            return
        document = offline_document(project, kind, source)
        key = api_key or os.getenv("GEMINI_API_KEY")
        if not offline and key:
            prompt = f"Create a polished {kind} for project '{project['name']}'. Project description: {project['idea']}. Use only these source notes:\n{source}"
            try:
                document = {"document_type": kind, "text": ask_gemini(prompt, api_key=key, json_response=False)}
            except Exception as exc:
                st.warning(f"Gemini was unavailable; used offline generation instead: {exc}")
        st.session_state.current_document = document
        save_version(project_name or "untitled-project", kind, document)

    uploaded_signature = "|".join(name + str(len(text)) for name, text in uploaded_text)
    if auto_generate and uploaded_signature and uploaded_signature != st.session_state.get("last_uploaded_signature"):
        st.session_state.last_uploaded_signature = uploaded_signature
        generate()

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✨ Generate document", type="primary"):
            generate()
    with c2:
        if st.button("🛠️ Improve current text"):
            if source:
                st.session_state.current_document = offline_document(project, "Improved text", source)
                save_version(project_name or "untitled-project", "Improved text", st.session_state.current_document)
            else:
                st.warning("Paste or upload a document first.")

    document = st.session_state.current_document
    if document is not None:
        st.subheader("Generated document")
        if isinstance(document, str):
            st.markdown(document)
        elif "text" in document:
            st.markdown(document["text"])
        else:
            st.json(document)
        report = quality(document)
        st.subheader("Quality analysis")
        st.metric("Score", f"{report['score']:.1f}%")
        if report["issues"]:
            st.warning(" · ".join(report["issues"]))
        else:
            st.success("No obvious structural issues detected.")
        st.json({"recommendations": report["recommendations"]})

    st.divider()
    st.subheader("Ask your project")
    question = st.text_input("Question", placeholder="What should happen when invalid data is submitted?")
    if st.button("Ask AI") and question:
        evidence = format_context(retrieve(question, chunks)) or source or "No project evidence was provided."
        if offline:
            st.write("Answer based on the available project evidence:\n\n" + evidence)
        else:
            try:
                st.write(ask_gemini(f"Answer only from this evidence:\n{evidence}\n\nQuestion: {question}", api_key=api_key or os.getenv("GEMINI_API_KEY"), json_response=False))
            except Exception as exc:
                st.error(str(exc))

    st.subheader("Workspace versions")
    for i, version in enumerate(st.session_state["versions"], 1):
        st.caption(f"v{i}: {version['type']} · {version['saved_at']}")


if __name__ == "__main__":
    app()
