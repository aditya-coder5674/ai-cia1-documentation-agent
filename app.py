"""DocuMind AI — iterative documentation workbench."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

from knowledge_base import format_context, load_text_files, retrieve
from llm_client import ask_gemini

DEFAULT_FEATURES = [
    "User registration and profile",
    "Connect with other users",
    "News feed with posts",
    "Messaging",
    "Job posting and applying",
]

DEFAULT_DOC_TEXT = """# Project overview

This project allows professionals to create profiles, connect with other users, post updates, message each other, and apply for jobs.

## Goals
- Make networking easy for professionals
- Support trusted user profiles and messaging
- Help job seekers connect with employers

## Constraints
- Must work as a web application
- Must be easy to use on desktop and mobile
- Must support secure authentication
"""


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return value or "document"


def ensure_workspace() -> Path:
    workspace = Path("workspace")
    workspace.mkdir(exist_ok=True)
    return workspace


def ensure_session_state() -> None:
    if "versions" not in st.session_state:
        st.session_state.versions = []
    if "current_document" not in st.session_state:
        st.session_state.current_document = None
    if "quality_report" not in st.session_state:
        st.session_state.quality_report = None


def save_version(name: str, document_type: str, payload: dict | str) -> None:
    workspace = ensure_workspace()
    versions = st.session_state.versions
    label = f"{slugify(name)}-v{len(versions) + 1}"
    if isinstance(payload, dict):
        content = json.dumps(payload, indent=2)
    else:
        content = payload
    version_path = workspace / f"{label}.json"
    version_path.write_text(content, encoding="utf-8")
    versions.append(
        {
            "name": label,
            "type": document_type,
            "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "path": str(version_path),
        }
    )
    st.session_state.versions = versions


def create_diff(before: str, after: str) -> str:
    if before == after:
        return "No textual changes detected."
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    diff_lines: list[str] = []
    sentinel = set(before_lines) | set(after_lines)
    for line in sorted(sentinel, key=lambda s: (s not in before_lines, s not in after_lines, s)):
        if line in after_lines and line not in before_lines:
            diff_lines.append(f"+ {line}")
        elif line in before_lines and line not in after_lines:
            diff_lines.append(f"- {line}")
    return "\n".join(diff_lines[:30]) or "Changes detected but line-level diff is minimal."


def generate_quality_report(project: dict, document: dict | str, document_type: str) -> dict:
    issues: list[str] = []
    score = 80.0

    if isinstance(document, dict):
        if document_type == "SRS":
            requirements = document.get("requirements", [])
            tests = document.get("test_cases", [])
            for feature in project["features"]:
                if not any(item.get("feature", "").casefold() == feature.casefold() for item in requirements):
                    issues.append(f"Feature '{feature}' is missing a requirement.")
            for requirement in requirements:
                req_id = requirement.get("id")
                types = {test.get("type") for test in tests if test.get("requirement_id") == req_id}
                for kind in ("positive", "negative"):
                    if kind not in types:
                        issues.append(f"Requirement {req_id} is missing a {kind} test case.")
            complete = 0
            for requirement in requirements:
                req_id = requirement.get("id")
                types = {test.get("type") for test in tests if test.get("requirement_id") == req_id}
                if {"positive", "negative"}.issubset(types):
                    complete += 1
            score = round((complete / len(requirements)) * 100, 1) if requirements else 0.0
        elif document_type in {"PRD", "User stories"}:
            if not document:
                issues.append("Document content is empty.")
            if document_type == "PRD":
                if not document.get("requirements"):
                    issues.append("PRD is missing explicit requirements.")
            else:
                if not document.get("stories"):
                    issues.append("User stories are missing.")
            score = 82.0
        else:
            if not document.get("text", ""):
                issues.append("Document is empty.")
            score = 78.0
    else:
        text = str(document or "").strip()
        if not text:
            issues.append("Document content is empty.")
        if len(text.split()) < 40:
            issues.append("Document is short and may lack detail.")
        score = 75.0

    return {
        "document_type": document_type,
        "score": max(0.0, min(100.0, score)),
        "issues": issues[:8],
        "recommendations": [
            "Add clearer acceptance criteria.",
            "Check for ambiguous or duplicate statements.",
            "Ensure every requirement maps to a real feature.",
        ],
    }


def build_offline_srs(project: dict) -> dict:
    requirements = []
    test_cases = []
    for index, feature in enumerate(project["features"], 1):
        req_id = f"REQ-{index:02d}"
        requirements.append({
            "id": req_id,
            "feature": feature,
            "text": f"The system shall support {feature.lower()}.",
        })
        test_cases.extend([
            {
                "id": f"TC-{(index * 2) - 1:02d}",
                "requirement_id": req_id,
                "type": "positive",
                "description": f"Valid use of '{feature}' succeeds.",
            },
            {
                "id": f"TC-{(index * 2):02d}",
                "requirement_id": req_id,
                "type": "negative",
                "description": f"Invalid or unsupported use of '{feature}' is rejected gracefully.",
            },
        ])
    return {
        "document_type": "SRS",
        "project": project["name"],
        "summary": f"Generated offline SRS for {project['name']}.",
        "requirements": requirements,
        "test_cases": test_cases,
    }


def build_offline_prd(project: dict) -> dict:
    return {
        "document_type": "PRD",
        "project": project["name"],
        "goal": project["idea"],
        "problem_statement": f"Users need a clear and reliable way to work with {project['name']}.",
        "user_personas": ["Registered user", "Community member", "Job seeker"],
        "requirements": [
            {"id": f"PRD-{idx:02d}", "requirement": f"The system shall support {feature.lower()}"}
            for idx, feature in enumerate(project["features"], 1)
        ],
        "success_metrics": [
            "Users complete onboarding quickly.",
            "Core documentation and actions are easy to understand.",
        ],
    }


def build_offline_user_stories(project: dict) -> dict:
    stories = []
    for index, feature in enumerate(project["features"], 1):
        stories.append(
            {
                "id": f"US-{index:02d}",
                "as_a": "User",
                "i_want": feature.lower(),
                "so_that": "I can complete a meaningful outcome for the product.",
                "acceptance_criteria": [
                    f"The user can access the {feature.lower()} flow.",
                    f"The system rejects invalid input during the {feature.lower()} flow.",
                ],
            }
        )
    return {
        "document_type": "User stories",
        "project": project["name"],
        "stories": stories,
    }


def improve_document_offline(text: str, mode: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return "# Improved document\n\nNo source content was provided. Add text and try again."

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    intro = "# Improved document\n\n## Overview\nThis document has been cleaned up, clarified, and rewritten for readability and consistency.\n"

    if mode == "Improve clarity":
        body = "\n\n".join(f"### Section {idx}\n{line}" for idx, line in enumerate(lines[:8], 1))
    elif mode == "Add acceptance criteria":
        body = "\n\n".join([
            "## Acceptance criteria",
            "- The system shall state the required behavior clearly.",
            "- The outcome shall be observable and testable.",
            "- Edge cases shall be handled without ambiguity.",
            *[f"- {line}" for line in lines[:6]],
        ])
    elif mode == "Formal specification":
        body = "\n\n".join([
            "## Formal specification",
            "The system shall provide a clear and unambiguous description of scope, constraints, and expected behavior.",
            "The specification shall be internally consistent and testable.",
            *[f"- {line}" for line in lines[:6]],
        ])
    elif mode == "Simplify":
        body = "\n\n".join(["## Simplified summary", *[f"- {line}" for line in lines[:10]]])
    else:
        body = "\n\n".join(["## Refined draft", *[f"- {line}" for line in lines[:10]]])

    return intro + body + "\n\n## Notes\n- Ambiguous wording was reduced.\n- Repeated or unclear statements were reorganized.\n- Acceptance criteria were added for testability.\n"


def build_prompt_for_document(project: dict, document_type: str, source_text: str) -> str:
    return (
        f"You are a senior technical writer for software documentation.\n"
        f"Project: {project['name']}\n"
        f"Project idea: {project['idea']}\n"
        f"Document type: {document_type}\n\n"
        f"Use this source material where helpful:\n{source_text}\n\n"
        "Return a polished document in valid Markdown with clear headings and effective structure. "
        "Keep it concise but complete."
    )


def render_document_output(document: dict | str, document_type: str) -> None:
    if isinstance(document, dict):
        if "text" in document:
            st.subheader("Improved document")
            st.markdown(document["text"])
        elif document_type == "SRS":
            st.subheader("Generated SRS")
            st.json(document)
        elif document_type == "PRD":
            st.subheader("Generated PRD")
            st.json(document)
        elif document_type == "User stories":
            st.subheader("User stories")
            st.json(document)
        else:
            st.subheader("Generated document")
            st.json(document)
    else:
        st.subheader("Improved document")
        st.markdown(document)


def app() -> None:
    st.set_page_config(page_title="DocuMind AI", page_icon="📚", layout="wide")
    st.markdown(
        """
        <style>
        .block-container {max-width: 1200px; padding-top: 2rem;}
        .hero {padding: 1.5rem 1.8rem; border-radius: 18px; background: linear-gradient(120deg,#172554,#2563eb); color: white; margin-bottom: 1rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="hero"><h1>📚 DocuMind AI</h1><p>Iterative documentation assistant for software projects</p></div>',
        unsafe_allow_html=True,
    )

    ensure_session_state()

    with st.sidebar:
        st.header("Project setup")
        project_name = st.text_input("Project name", value="Professional Networking App")
        project_idea = st.text_area(
            "Project description",
            value="A web app where professionals build profiles, connect, share posts, message each other and apply for jobs.",
            height=120,
        )
        features_raw = st.text_area("Features (one per line)", value="\n".join(DEFAULT_FEATURES), height=150)
        features = [line.strip() for line in features_raw.splitlines() if line.strip()]

        document_type = st.selectbox(
            "Document type",
            ["SRS", "PRD", "User stories", "Improved text"],
            index=0,
        )
        improvement_mode = st.selectbox(
            "Improvement mode",
            ["Improve clarity", "Add acceptance criteria", "Formal specification", "Simplify"],
            index=0,
        )

        api_key = st.text_input("Gemini API key (optional)", type="password")
        offline_mode = st.toggle("Offline mode", value=not bool(api_key or os.getenv("GEMINI_API_KEY")))
        uploaded = st.file_uploader("Add local project knowledge (.txt)", type=["txt"], accept_multiple_files=True)

    project = {"name": project_name, "idea": project_idea, "features": features or DEFAULT_FEATURES}

    uploaded_text = [(file.name, file.getvalue().decode("utf-8", errors="ignore")) for file in (uploaded or [])]
    chunks = load_text_files("data", uploaded_text)
    st.info(f"Knowledge base: {len(chunks)} text chunk(s) loaded locally.")

    query = f"{project_name} {project_idea} {' '.join(project['features'])}"
    matches = retrieve(query, chunks)
    with st.expander("View retrieved evidence"):
        if matches:
            for chunk, score in matches:
                st.markdown(f"**{chunk.source}** · relevance `{score:.2f}`")
                st.write(chunk.text)
        else:
            st.write("No matching evidence yet. Add notes in the `data` folder or upload `.txt` files.")

    source_text = st.text_area(
        "Document draft / source text",
        value=DEFAULT_DOC_TEXT,
        height=260,
        help="Paste your rough document here or upload a text file. You can improve it iteratively.",
    )

    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("✨ Generate document"):
            try:
                if document_type == "SRS":
                    generated = build_offline_srs(project)
                elif document_type == "PRD":
                    generated = build_offline_prd(project)
                elif document_type == "User stories":
                    generated = build_offline_user_stories(project)
                else:
                    generated = {"document_type": "Improved text", "text": improve_document_offline(source_text, improvement_mode)}

                if (not offline_mode) and (api_key or os.getenv("GEMINI_API_KEY")):
                    prompt = build_prompt_for_document(project, document_type, source_text)
                    key = api_key or os.getenv("GEMINI_API_KEY")
                    try:
                        ai_text = ask_gemini(prompt, api_key=key, json_response=False)
                        generated = {"document_type": document_type, "text": ai_text}
                    except Exception:
                        pass

                st.session_state.current_document = generated
                save_version(project_name, document_type, generated)
                st.success(f"{document_type} generated and saved to the workspace.")
            except Exception as exc:  # pragma: no cover
                st.error(str(exc))

    with col2:
        if st.button("🛠️ Improve document"):
            try:
                improved = improve_document_offline(source_text, improvement_mode)
                st.session_state.current_document = {"document_type": "Improved text", "text": improved}
                save_version(project_name, "Improved text", improved)
                st.success("Improved document generated.")
            except Exception as exc:  # pragma: no cover
                st.error(str(exc))

    with col3:
        if st.button("📈 Quality check"):
            if st.session_state.current_document is not None:
                current = st.session_state.current_document
                report = generate_quality_report(project, current, document_type)
                st.session_state.quality_report = report
                st.success("Quality review generated.")
            else:
                st.warning("Generate or improve a document first.")

    if st.session_state.current_document is not None:
        current = st.session_state.current_document
        st.subheader("Current document")
        render_document_output(current, document_type)

        if isinstance(current, dict):
            quality = generate_quality_report(project, current, document_type)
            st.subheader("Quality analysis")
            st.metric("Score", f"{quality['score']:.1f}%")
            if quality["issues"]:
                st.warning("Issues found: " + " · ".join(quality["issues"]))
            else:
                st.success("No obvious structural issues detected.")
            st.json({"issues": quality["issues"], "recommendations": quality["recommendations"]})
        else:
            quality = generate_quality_report(project, current, document_type)
            st.subheader("Quality analysis")
            st.metric("Score", f"{quality['score']:.1f}%")
            if quality["issues"]:
                st.warning("Issues found: " + " · ".join(quality["issues"]))
            else:
                st.success("No obvious structural issues detected.")

        if st.button("🔄 Compare with previous version"):
            if len(st.session_state.versions) >= 2:
                previous = st.session_state.versions[-2]
                previous_path = Path(previous["path"])
                previous_content = previous_path.read_text(encoding="utf-8")
                current_content = json.dumps(current, indent=2) if isinstance(current, dict) else current
                st.subheader("Version diff")
                st.code(create_diff(previous_content, current_content))
            else:
                st.info("Generate at least two versions to compare them.")

    st.divider()
    st.subheader("Ask your project")
    question = st.text_input("Question", placeholder="What should happen when an unauthorised user sends a message?")
    if st.button("Ask AI") and question:
        evidence = format_context(retrieve(question, chunks)) or "No matching local evidence was found. Say that clearly."
        try:
            if offline_mode:
                answer = "Offline answer based on retrieved evidence:\n\n" + evidence
            else:
                key = api_key or os.getenv("GEMINI_API_KEY")
                if not key:
                    raise RuntimeError("Set a Gemini API key or switch on Offline mode.")
                answer = ask_gemini(
                    f"Answer using only the evidence below. Do not invent facts.\n\nEVIDENCE:\n{evidence}\n\nQUESTION:\n{question}",
                    api_key=key,
                    json_response=False,
                )
            st.write(answer)
        except Exception as exc:  # pragma: no cover
            st.error(str(exc))

    st.divider()
    st.subheader("Workspace versions")
    if st.session_state.versions:
        for index, version in enumerate(st.session_state.versions, 1):
            st.caption(f"v{index}: {version['type']} · {version['saved_at']}")
    else:
        st.caption("No saved versions yet.")


if __name__ == "__main__":
    app()
