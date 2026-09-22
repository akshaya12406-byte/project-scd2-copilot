# SCD2 Copilot — Enterprise SCD Type 2 Automation & AI Explanations

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.45%2B-FF4B4B.svg)](https://streamlit.io)
[![Polars](https://img.shields.io/badge/Data%20Engine-Polars-CD792C.svg)](https://pola.rs/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An enterprise-ready data engineering tool that automates **Slowly Changing Dimension Type 2 (SCD2)** pipelines while generating human-readable AI explanations for every detected change.

---

## 1. Project Overview & Business Problem

### The Business Problem
In enterprise data warehouses, tracking historical changes to dimensional data (customers, products, accounts) using Slowly Changing Dimension Type 2 is one of the most critical yet repetitive and error-prone engineering tasks:
* **Complex Boundary Edge Cases**: Handling overlapping dates, gap detection, duplicate keys, case insensitivity, and out-of-order snapshots often introduces subtle data corruption.
* **Audit & Business Transparency Gaps**: Business users, auditors, and compliance officers cannot easily decipher raw relational diffs or understand *why* records changed across snapshots.
* **Brittle Pipelines**: External API-dependent systems crash when LLM quotas or network hiccups occur during batch execution.

### The Solution: SCD2 Copilot
SCD2 Copilot provides a **guaranteed deterministic core data engine** combined with an **AI explanation and audit layer**:
1. **100% Deterministic Engine**: Built on **Polars** to perform change detection, SCD2 transformations, and 5-point data integrity validation without any LLM intervention.
2. **AI Explanation Layer**: Translates detected field-level modifications into clear business English using Google Gemini, Groq, or offline deterministic templates.
3. **Resilient Multi-Tier Fallback**: Automatically degrades across a 5-model Gemini chain, then to Groq LLaMA 3.3, and finally to local templates so the pipeline never halts.
4. **Interactive Dashboard**: A responsive Streamlit enterprise workspace with 1-click built-in demo datasets, schema overrides, interactive diff explorers, and audit downloads.

---

## 2. Key Architecture

```
                          ┌─────────────────────────────────────┐
                          │         Input CSV Datasets          │
                          │ (Today's Source & Yesterday's SCD2) │
                          └──────────────────┬──────────────────┘
                                             │
                                             ▼
                          ┌─────────────────────────────────────┐
                          │   CSV Ingestion & Schema Normalizer │
                          │        (ingestion.py, schema.py)    │
                          └──────────────────┬──────────────────┘
                                             │
                                             ▼
                          ┌─────────────────────────────────────┐
                          │    Deterministic Change Engine      │
                          │         (detect_changes.py)         │
                          │   [NEW, CHANGED, UNCHANGED, DELETED]│
                          └───────┬─────────────────────┬───────┘
                                  │                     │
                    ┌─────────────┘                     └─────────────┐
                    ▼                                                 ▼
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│       SCD2 Table Transformer         │          │     AI Explanation Orchestrator      │
│        (transform_scd2.py)           │          │             (explain.py)             │
│  - Closes outdated records           │          │  - Gemini 5-model fallback chain     │
│  - Inserts active versions           │          │  - Groq LLaMA 3.3 fallback           │
│  - Preserves closed history          │          │  - Offline template fallback         │
└──────────────────┬───────────────────┘          └──────────────────┬───────────────────┘
                   │                                                 │
                   ▼                                                 ▼
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│   Data Integrity & Audit Validator   │          │  Token, Cost & Latency Metrics Engine│
│            (validate.py)             │          │             (models.py)              │
│  - 5-point invariant verification    │          │  - Real-time token tracking          │
└──────────────────┬───────────────────┘          └──────────────────┬───────────────────┘
                   │                                                 │
                   └─────────────────────┬───────────────────────────┘
                                         ▼
                          ┌─────────────────────────────────────┐
                          │     Streamlit Enterprise Dashboard  │
                          │        (app/streamlit_app.py)       │
                          └─────────────────────────────────────┘
```

### Core Architecture Rules
* **The LLM never decides if a record changed.** Change detection is strictly mathematical and deterministic.
* **The LLM only explains already-detected changes.**
* **Pipeline runs succeed even with zero API keys** via offline template explanations.

---

## 3. Features

* **CSV Ingestion & Normalization**: Normalizes headers, parses date formats (`%Y-%m-%d`), casts booleans, and automatically isolates SCD2 metadata (`effective_from`, `effective_to`, `is_current`).
* **Heuristic Schema Inference**: Auto-detects primary business keys and tracked attributes with support for interactive user overrides.
* **Deterministic Change Detection**: Categorizes every key into `NEW`, `CHANGED`, `UNCHANGED`, or `DELETED`, detailing exact field-level diffs (`old_value` $\rightarrow$ `new_value`).
* **SCD2 Transformation**: Closes outdated records (`effective_to = processing_date`, `is_current = False`), creates new active records, and preserves non-current historical rows.
* **5-Point Mathematical Validation**:
  1. *Schema completeness* — all required metadata columns present.
  2. *Uniqueness* — at most one active record per business key.
  3. *Null key prevention* — no null business keys permitted.
  4. *Timeline integrity* — historical date windows never overlap.
  5. *Date consistency* — `effective_from <= effective_to`.
* **Multi-Provider AI Explanations**: Uses structured Pydantic batching with fallback across Gemini $\rightarrow$ Groq $\rightarrow$ local template.
* **1-Click Built-In Demo Mode**: Public evaluators can click **"Load Built-in Demo Data"** to evaluate the complete pipeline immediately without uploading files.
* **Audit Exports**: Download updated SCD2 tables (CSV), formal validation reports (TXT), and explanation narratives (TXT) with 1 click.

---

## 4. Tech Stack

* **Language**: Python 3.12
* **Data Processing**: [Polars](https://pola.rs/) (high-performance columnar data engine)
* **Web Framework**: [Streamlit](https://streamlit.io/)
* **Orchestration**: [Prefect 3](https://www.prefect.io/)
* **AI Providers**:
  * [Google GenAI SDK](https://github.com/googleapis/python-genai) (`gemini-3.1-flash-lite`, `gemini-3-flash`, `gemini-2.5-flash-lite`, `gemini-2.5-flash`)
  * [Groq SDK](https://github.com/groq/groq-python) (`llama-3.3-70b-versatile`)
  * Deterministic Template Engine (local offline fallback)
* **Configuration**: `pydantic`, `pydantic-settings`
* **Testing**: `pytest`, property-based testing, saturation benchmarks

---

## 5. Local Setup

### 1. Clone the repository
```bash
git clone <your-repo-url>
cd scd2-copilot
```

### 2. Create and activate a Python 3.12 virtual environment
* **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```
* **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```
* **Windows (Command Prompt)**:
  ```cmd
  python -m venv .venv
  .\.venv\Scripts\activate.bat
  ```

### 3. Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure environment variables (Optional)
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Populate optional API keys:
```env
GEMINI_API_KEY=your-gemini-api-key-here
GROQ_API_KEY=your-groq-api-key-here
LLM_PROVIDER=gemini
APP_ENV=development
DEFAULT_TIMEZONE=UTC
```
*(Note: If no API keys are provided, SCD2 Copilot automatically runs in offline template mode.)*

### 5. Run the application locally
From the repository root:
```bash
streamlit run app/streamlit_app.py
```
Open your browser at `http://localhost:8501`.

---

## 6. Streamlit Community Cloud Deployment

SCD2 Copilot is fully configured for deployment on **Streamlit Community Cloud** with subfolder entrypoint support.

### Step-by-Step Deployment Guide
1. Push your repository to GitHub.
2. Sign in to [share.streamlit.io](https://share.streamlit.io/) using your GitHub account.
3. Click **"New app"**.
4. In the deployment modal, configure:
   * **Repository**: `<your-github-username>/scd2-copilot`
   * **Branch**: `main`
   * **Main file path**: `app/streamlit_app.py`
5. Click **"Advanced settings..."**:
   * **Python version**: Select `3.12`.
   * **Secrets**: Add your API keys (optional — template mode works without keys):
     ```toml
     GEMINI_API_KEY = "your-gemini-api-key"
     GROQ_API_KEY = "your-groq-api-key"
     LLM_PROVIDER = "gemini"
     ```
6. Click **"Deploy!"**.
7. Once deployed, click **"📂 Load Built-in Demo Data"** to verify full pipeline execution.

---

## 7. Verification & Testing

### Run Automated Unit & Integration Tests
```bash
pytest
```
Expected output: **183 passed**.

### Run Property-Based & Scale Saturation Audit
```bash
python tests/run_saturation_audit.py
```
Or via module execution:
```bash
python -m tests.run_saturation_audit
```
Runs 1,000 randomized property datasets, composite key verifications, schema drift simulations, and stress tests up to 100,000 rows.

---

## 8. License

This project is licensed under the MIT License.
