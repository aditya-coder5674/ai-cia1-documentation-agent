# DocuMind AI

A local RAG-based software documentation assistant for the AI coursework project.

## Run

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Put project notes in `data/*.txt`. For Gemini mode, set `GEMINI_API_KEY` or enter it in the sidebar. Offline mode works without an API key.
