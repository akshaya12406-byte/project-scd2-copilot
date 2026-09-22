# SCD2 Copilot 🚀
### AI-Powered Slowly Changing Dimensions (Type 2) with Human Explanations

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B.svg)](https://streamlit.io)
[![Polars](https://img.shields.io/badge/Data%20Engine-Polars-CD792C.svg)](https://pola.rs/)
[![Tests Passing](https://img.shields.io/badge/tests-196%20passed-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A hands-on data engineering project that automates **Slowly Changing Dimension Type 2 (SCD2)** updates on CSV data, validates table integrity with strict checks, and uses LLMs (Gemini / Groq) to explain what changed in plain English.

Built as a practical exploration of modern data pipelines, combining high-speed dataframe processing in **Polars** with structured AI explanations.

---

## 💡 The Problem & The Idea

### Why is SCD2 so tedious?
If you've ever studied database systems or worked with data warehouses, you know **Slowly Changing Dimensions (Type 2)** is one of the classic concepts:
- Instead of overwriting a row when an entity's attributes change (like a customer moving cities or changing tiers), you keep full history by tracking `effective_from`, `effective_to`, and an `is_current` flag.
- Writing the SQL merges or Python scripts to handle this by hand gets messy fast: date boundary bugs, overlapping intervals, handling null keys, and tracking which specific fields actually changed.
- Even worse, once you update a table with dozens of rows, looking at raw diffs doesn't tell you *why* a change happened in human terms.

### How SCD2 Copilot solves this
1. **100% Deterministic Core**: Built with **Polars**. All change detection (`NEW`, `CHANGED`, `UNCHANGED`, `DELETED`), interval closing, and data integrity checks are done purely mathematically in code. **The AI never decides if data changed.**
2. **AI Explanation Layer**: Translates detected field changes into friendly 1–2 sentence explanations using Google Gemini or Groq.
3. **Multi-Tier Fallback (Zero Crashes)**: Cascades gracefully across a 5-model Gemini chain $\rightarrow$ Groq GPT-OSS $\rightarrow$ local offline template. If you don't have an API key or hit free-tier rate limits, the pipeline never breaks—it simply uses local templates!
4. **Interactive Streamlit Web App**: Upload your source and target CSVs, preview detected diffs, inspect validation checks, and download updated tables with explanations. There's also a 1-click demo button with sample data ready to go.

---

## 🛠️ Architecture

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
│  - Inserts active versions           │          │  - Groq GPT-OSS fallback chain       │
│  - Preserves closed history          │          │  - Offline template fallback         │
└──────────────────┬───────────────────┘          └──────────────────┬───────────────────┘
                    │                                                 │
                    ▼                                                 ▼
┌──────────────────────────────────────┐          ┌──────────────────────────────────────┐
│       Data Integrity Validator       │          │   Token & Latency Metrics Tracker    │
│            (validate.py)             │          │             (models.py)              │
│  - 5-point invariant checks          │          │  - Token counts & execution time     │
└──────────────────┬───────────────────┘          └──────────────────┬───────────────────┘
                    │                                                 │
                    └─────────────────────┬───────────────────────────┘
                                          ▼
                          ┌─────────────────────────────────────┐
                          │         Streamlit Web App           │
                          │        (app/streamlit_app.py)       │
                          └─────────────────────────────────────┘
```

### The Golden Rule
> **The LLM never modifies or validates the data.**  
> Change detection and SCD2 transformations are strictly deterministic. The LLM only receives already-computed diffs to write helpful human-friendly summaries.

---

## ✨ Features

- **Smart Schema Detection**: Automatically identifies candidate business keys (like `customer_id` or `id`) and tracked columns, while letting you override selections in the UI.
- **Fast Columnar Processing**: Powered by Polars to quickly compare datasets and compute field-level changes (`old_value` $\rightarrow$ `new_value`).
- **Standard SCD2 Transformations**:
  - Closes updated records (`effective_to = processing_date`, `is_current = False`).
  - Inserts new current records (`effective_from = processing_date`, `effective_to = None`, `is_current = True`).
  - Handles brand-new records and soft-deleted/missing records.
- **5 Automated Integrity Checks**:
  1. *Schema check* — confirms all SCD2 columns exist.
  2. *Single current version* — at most one active record per business key.
  3. *No null keys* — business keys cannot contain nulls.
  4. *No overlapping dates* — version timelines never intersect.
  5. *Chronological consistency* — `effective_from <= effective_to`.
- **Multi-Model AI Explanations**:
  - Primary: Google Gemini (`gemini-3.5-flash-lite`, `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash`, `gemini-3.5-flash`)
  - Fallback: Groq (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`)
  - Offline: Deterministic string templates (works with no API keys or internet!)
- **1-Click Demo Mode**: Don't have sample CSVs on hand? Just click **"Load Built-in Demo Data"** in the app to immediately see the pipeline in action.
- **Export Artifacts**: Download the updated SCD2 table (CSV), validation report (TXT), and AI explanation logs with one click.

---

## 🧰 Tech Stack

- **Language**: Python 3.12
- **Data Engine**: [Polars](https://pola.rs/) (fast columnar dataframe processing) & [DuckDB](https://duckdb.org/)
- **Frontend / UI**: [Streamlit](https://streamlit.io/)
- **Orchestration**: [Prefect 3](https://www.prefect.io/)
- **AI Providers**:
  - [Google GenAI SDK](https://github.com/googleapis/python-genai) (`gemini-3.5-flash-lite`, `gemini-3.8-flash`, etc.)
  - [Groq SDK](https://github.com/groq/groq-python) (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`)
  - Rule-based template generator (offline fallback)
- **Data Models & Config**: Pydantic v2 & `pydantic-settings`
- **Testing**: Pytest (196 tests), property-based testing, saturation benchmarks

---

## 🚀 Getting Started

### 1. Clone the repo
```bash
git clone <your-repo-url>
cd project-scd2-copilot
```

### 2. Set up a virtual environment
```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Windows (CMD)
python -m venv .venv
.\.venv\Scripts\activate.bat
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Keys (Optional)
If you want to use live LLMs, copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
And add your keys:
```env
GEMINI_API_KEY=your_gemini_api_key
GROQ_API_KEY=your_groq_api_key
LLM_PROVIDER=gemini
```
*(No keys? No problem! The app will automatically run using the built-in deterministic template generator.)*

### 5. Launch the Streamlit app
```bash
streamlit run app/streamlit_app.py
```
Open `http://localhost:8501` in your browser. Click **"📂 Load Built-in Demo Data"** to try it out right away!

---

## 🧪 Testing & Validation

We wrote an extensive test suite to make sure the data transformations and fallback chains are bulletproof:

### Run Unit & Integration Tests
```bash
pytest
```
Runs **196 tests** covering schema detection, SCD2 transforms, validation rules, fallback chains, and error simulations (429 rate limits, timeouts, and missing keys).

### Run Saturation & Property Benchmark
```bash
python tests/run_saturation_audit.py
```
Runs:
- 1,000 randomized property-based invariant tests.
- Composite key validations.
- Schema evolution tests (column addition, deletion, rename, type coercion).
- Stress test scaling up to **100,000 rows** in ~8.9 seconds.

---

## 🌐 Deploying to Streamlit Community Cloud

You can easily host this online for free on Streamlit Community Cloud:
1. Push this repo to your GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io/) and create a **New app**.
3. Point to:
   - **Repository**: `your-username/project-scd2-copilot`
   - **Branch**: `main`
   - **Main file path**: `app/streamlit_app.py`
4. Under **Advanced settings**, set Python to `3.12` and add your `GEMINI_API_KEY` or `GROQ_API_KEY` under Secrets (optional).
5. Click **Deploy**!

---

## 🎓 What We Learned
- **Polars vs Pandas**: Using Polars for anti-joins and date comparisons made the transformation blazing fast compared to traditional procedural SQL or Pandas row loops.
- **Fail-Safe AI Pipelines**: External APIs fail, get throttled, or run out of free quota. Designing a multi-tier fallback (Gemini $\rightarrow$ Groq $\rightarrow$ Offline Template) meant our app never crashes during a demo.
- **Strict Separation of Concerns**: Keeping the data engine 100% deterministic and letting LLMs handle *only* human communication is the best pattern for reliable AI data tools.

---

## 📄 License
MIT License — feel free to use, modify, and build upon this for your own projects and coursework!
