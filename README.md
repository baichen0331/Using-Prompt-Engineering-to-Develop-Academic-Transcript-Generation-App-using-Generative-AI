# Using Prompt Engineering to Develop an Academic Transcript Generation App

This project uses a Streamlit frontend and a FastAPI backend to extract transcript data from `.txt` or `.pdf` files, review the structured result, manage reviewer accounts, preview OCR output, and export a polished PDF transcript.

## Improvements in this version

- Removes chain-of-thought output from the schema and prompt flow.
- Calculates GPA deterministically in Python instead of relying on the model.
- Adds file size/type validation and clearer extraction errors.
- Adds a review-and-edit workflow in the frontend before PDF generation.
- Upgrades the PDF layout with better tables, summary data, and review notes.
- Adds login, bearer-token protection, and role-aware review access.
- Adds hashed-password login backed by a SQLite user table.
- Adds optional OCR fallback for scanned PDFs with bilingual page-level control when Tesseract is installed.
- Adds an OCR preview panel, background extraction jobs, and OCR tuning in the frontend.

## Run locally

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in `DASHSCOPE_API_KEY`.

3. Configure login credentials and JWT secret in `.env`.
These credentials are used only to seed the initial SQLite user table on first startup.

This version is fixed to `LLM_MODEL=qwen3.6-plus`. If extraction feels slow, keep using the OCR preview first or increase `REQUEST_TIMEOUT_SECONDS` beyond the default `600`.

4. Optional OCR:

```bash
pip install pytesseract pypdfium2
```

Set `OCR_ENABLED=true` and, on Windows, point `TESSERACT_CMD` to your `tesseract.exe`.

5. Quick start (Windows):

```bat
start.bat
```

6. Or start services manually:

Backend:

```bash
uvicorn app.main:app --reload
```

Frontend:

```bash
streamlit run frontend_app/main.py
```

If `8501` is occupied, Streamlit automatically switches to another port (for example `8502` or `8505`).

## Package structure

The runtime now uses only the new package layout:

```text
app/
  main.py
  core/
  api/v1/
  services/
  models/
frontend_app/
  main.py
```
