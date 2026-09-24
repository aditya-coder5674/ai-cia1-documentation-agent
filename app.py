"""Streamlit interface for the local RAG documentation assistant."""
from __future__ import annotations

import json
import os
import streamlit as st

from knowledge_base import format_context, load_text_files, retrieve
from llm_client import ask_gemini
from validators import save_outputs, validate_document

DEFAULT_FEATURES = [
    "User registration and profile",
    "Connect with other users",
    "News feed with posts",
    "Messaging",
    "Job posting and applying",
]

st.set_page_config(page_title="DocuMind AI", page_icon="📚", layout="wide")
st.markdown("""<style>.block-container{max-width:1180px;padding-top:2rem}.hero{padding:1.4rem 1.8rem;border-radius:18px;background:linear-gradient(120deg,#172554,#2563eb);color:white;margin-bottom:1rem}.hero h1{margin:0}.stButton>button{border-radius:10px}</style>""", unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>📚 DocuMind AI</h1><p>Evidence-grounded software documentation assistant</p></div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Project setup")
    name = st.text_input("Project name", "Professional Networking App")
    idea = st.text_area("Project description", "A web app where professionals build profiles, connect, share posts, message each other and apply for jobs.")
    features = [x.strip() for x in st.text_area("Features (one per line)", "\n".join(DEFAULT_FEATURES), height=160).splitlines() if x.strip()]
    api_key = st.text_input("Gemini API key (optional)", type="password", help="It is used only for the current session.")
    offline = st.toggle("Offline demo mode", value=not bool(api_key or os.getenv("GEMINI_API_KEY")))

uploaded = st.file_uploader("Add local project knowledge (.txt)", type=["txt"], accept_multiple_files=True)
project = {"name": name, "idea": idea, "features": features}

uploaded_text = [(file.name, file.getvalue().decode("utf-8", errors="ignore")) for file in (uploaded or [])]
chunks = load_text_files("data", uploaded_text)
st.info(f"Knowledge base: {len(chunks)} text chunk(s) loaded locally.")

if not chunks:
    st.warning("Add .txt files to the data folder or upload a text file to begin.")

query = f"{name} {idea} {' '.join(features)}"
matches = retrieve(query, chunks)
with st.expander("View retrieved evidence"):
    if matches:
        for chunk, score in matches:
            st.markdown(f"**{chunk.source}** · relevance `{score:.2f}`")
            st.write(chunk.text)
    else:
        st.write("No matching evidence yet.")

prompt_template = """You are an expert software analyst. Use only the evidence below where relevant.
Project: {name}
Description: {idea}
Features: {features}

Evidence from local project files:
{context}

Return ONLY valid JSON with this exact structure:
{{"requirements":[{{"id":"REQ-01","feature":"exact feature string","text":"testable shall statement"}}],"test_cases":[{{"id":"TC-01","requirement_id":"REQ-01","type":"positive or negative","description":"specific test"}}]}}
Create one requirement for every feature and one positive plus one negative test for every requirement. Do not add unsupported features."""

col1, col2 = st.columns(2)
with col1:
    generate = st.button("✨ Generate SRS", type="primary", use_container_width=True)
with col2:
    clear = st.button("Clear previous result", use_container_width=True)
if clear:
    st.session_state.pop("document", None)

if generate:
    context = format_context(matches) or "No evidence matched; state assumptions clearly."
    prompt = prompt_template.format(name=name, idea=idea, features=json.dumps(features), context=context)
    try:
        if offline:
            document = {"requirements": [], "test_cases": []}
            for index, feature in enumerate(features, 1):
                req_id = f"REQ-{index:02d}"
                document["requirements"].append({"id": req_id, "feature": feature, "text": f"The system shall support {feature.lower()}."})
                document["test_cases"] += [{"id": f"TC-{2*index-1:02d}", "requirement_id": req_id, "type": "positive", "description": f"Valid {feature.lower()} succeeds."}, {"id": f"TC-{2*index:02d}", "requirement_id": req_id, "type": "negative", "description": f"Invalid {feature.lower()} is rejected."}]
        else:
            document = ask_gemini(prompt, api_key=api_key or None, json_response=True)
        st.session_state["document"] = document
    except Exception as error:
        st.error(str(error))

if "document" in st.session_state:
    document = st.session_state["document"]
    score, issues = validate_document(project, document)
    md_path, json_path = save_outputs(document, name, score)
    st.subheader("Generated SRS")
    metric, status = st.columns([1, 3])
    metric.metric("Coverage", f"{score:.0f}%")
    if issues:
        status.warning("Critic feedback: " + " · ".join(issues[:5]))
    else:
        status.success("Critic found no structural issues.")
    st.json(document)
    st.download_button("Download JSON", json.dumps(document, indent=2), file_name="srs_generated.json", mime="application/json")
    st.download_button("Download Markdown", md_path.read_text(encoding="utf-8"), file_name="srs_generated.md", mime="text/markdown")
    st.caption(f"Also saved locally: {md_path} and {json_path}")

st.divider()
st.subheader("Ask your project")
question = st.text_input("Question", placeholder="What should happen when an unauthorised user sends a message?")
if st.button("Ask AI") and question:
    evidence = format_context(retrieve(question, chunks)) or "No matching local evidence was found. Say that clearly."
    try:
        answer = ("Offline answer based on retrieved evidence:\n\n" + evidence) if offline else ask_gemini(f"Answer using only this evidence:\n{evidence}\n\nQuestion: {question}", api_key=api_key or None)
        st.write(answer)
    except Exception as error:
        st.error(str(error))
