# AI-Powered Testing Checklist System

AI assistant that turns feature requirements into structured testing checklists (Functional, UI, Edge, Regression, Risk), with editable UI and export options for real QA workflows.

## Problem Statement Mapping

- **Phase 1 — Input Processing & Context**
  - Implemented in `checklist_pipeline.py`:
    - `parse_feature_input()`
    - `url_analyzer()`
    - entity/flow extraction helpers
- **Phase 2 — Scenario Generation Logic**
  - Implemented in `checklist_pipeline.py`:
    - `build_scenario_seeds()`
- **Phase 3 — LLM Integration**
  - Implemented in `checklist_pipeline.py`:
    - `generate_checklist_with_openai()`
    - `run_pipeline()`
- **Phase 4 — Application Layer (UI + API)**
  - **UI**: `app.py` (Streamlit, CoverIQ-style shell)
  - **API**: `api.py` (FastAPI endpoint `POST /generate-checklist`)
- **Phase 5 — Impact & Scaling**
  - Productivity panel and generation timing metadata included as baseline.

## Features

- Input fields:
  - Feature description
  - Application URL (optional)
  - Project type (`API`, `Web`, `Mobile`, `Backend`, `Desktop`)
  - Additional preferences (optional)
- AI generation with phased pipeline
- Editable checklist with per-item delete (`❌`)
- Exports:
  - CSV
  - Excel (`.xlsx`)
  - Word (`.docx`)
  - Jira-shaped JSON
  - TestRail-style CSV
- Active checklist tracking and detailed checklist view with progress

## Project Structure

- `app.py` — Streamlit UI
- `coveriq_ui.py` — shared theme/topbar/nav shell
- `checklist_pipeline.py` — core pipeline (Phases 1–3)
- `api.py` — FastAPI backend endpoint
- `export_utils.py` — export format utilities
- `requirements.txt` — dependencies

## Setup

1. Install Python 3.10+ (recommended).
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set API key:

Windows PowerShell:

```powershell
$env:OPENAI_API_KEY="your_api_key_here"
```

## Run the UI (Streamlit)

```bash
python -m streamlit run app.py
```

## Run the API (FastAPI)

```bash
python -m uvicorn api:app --reload --port 8000
```

Health check:

```bash
curl http://localhost:8000/health
```

## API Contract

### POST `/generate-checklist`

Request body:

```json
{
  "feature": "Add login API with JWT and rate limiting",
  "url": "https://staging.example.com",
  "project_type": "web",
  "extras": "high traffic, strict latency SLO"
}
```

Response shape:

```json
{
  "checklist": {
    "functional_tests": ["..."],
    "ui_tests": ["..."],
    "edge_cases": ["..."],
    "regression": ["..."],
    "risk_areas": ["..."]
  },
  "meta": {
    "model": "gpt-4o-mini",
    "generation_time_ms": 1234
  },
  "intermediate": {
    "feature": "...",
    "flows": ["..."],
    "entities": ["..."],
    "context": "..."
  },
  "seeds": {
    "Functional": ["..."],
    "UI": ["..."],
    "Edge": ["..."],
    "Regression": ["..."],
    "Risk": ["..."]
  }
}
```

## Curl Example

```bash
curl -X POST "http://localhost:8000/generate-checklist" \
  -H "Content-Type: application/json" \
  -d "{\"feature\":\"Add API rate limiting\",\"url\":\"https://staging.example.com\",\"project_type\":\"API\",\"extras\":\"high traffic\"}"
```

## Notes

- If `uvicorn` command is not found, use `python -m uvicorn ...`.
- The app uses OpenAI directly; no secret manager is required for local dev.
