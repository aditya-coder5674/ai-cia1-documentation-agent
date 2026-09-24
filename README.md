# DocuMind AI

A local RAG-based software documentation assistant for the AI coursework project.

## What it demonstrates

- **Knowledge base:** local `.txt` project files in `data/` or uploaded through the UI.
- **Retrieval:** local TF-IDF cosine similarity selects relevant evidence.
- **Generation:** Gemini converts the evidence into an SRS and test cases.
- **Critic:** validation checks feature coverage, positive/negative tests, duplicate IDs, and broken references.
- **Offline mode:** the application can be demonstrated without an API key.

## Run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Put project notes in `data/*.txt`. For Gemini mode, set `GEMINI_API_KEY` or enter it in the sidebar. The key is not saved by the app.

The original command-line learning agent remains available:

```bash
python doc_agent.py --offline
```
