# DocuMind AI

DocuMind AI is an iterative documentation assistant for software projects. It helps you start from a rough idea, project notes, or a draft document and then improve it through multiple versions, quality checks, and document generation workflows.

## What it does

- Generate project documents such as SRS, PRD, and user stories
- Improve existing text using clarity, simplification, and formal-spec styles
- Track document versions in a local workspace
- Compare versions and review changes
- Run simple quality checks for coverage, consistency, and missing structure
- Answer project questions using local evidence from uploaded or local `.txt` notes
- Optionally use Gemini for live AI generation when an API key is provided

## Run it

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Optional Gemini mode

Set a key in the sidebar or export it before launch:

```bash
export GEMINI_API_KEY="your-key"
python -m streamlit run app.py
```

On Windows PowerShell:

```powershell
$env:GEMINI_API_KEY="your-key"
python -m streamlit run app.py
```

## Adding project notes

Place `.txt` files inside the `data` folder or upload them through the Streamlit page. The app retrieves relevant evidence and uses it to answer project questions or improve documentation.

## Example workflow

1. Enter a project name and description.
2. Add project notes or upload `.txt` files.
3. Pick a document type such as SRS or PRD.
4. Click Generate document.
5. Improve the draft with a quality mode.
6. Compare versions and save them in the workspace.

As this app evolves, it is designed to become a practical documentation workbench rather than a one-shot SRS generator.
