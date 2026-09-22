# SCD2 Copilot — Master Project Plan

## 1. Project Goal

Build an **AI-assisted Slowly Changing Dimension Type 2 (SCD2) Copilot** that:
- accepts a **source CSV** (today’s data)
- accepts a **target CSV** (yesterday’s SCD2 table)
- produces an **updated SCD2 table**
- validates correctness with deterministic checks
- explains every change in human-readable language using an LLM
- feels like a real business tool, not a toy CSV script

This project is designed to solve a real enterprise pain point: repeated hand-coding of SCD2 logic in data warehouse and ETL pipelines.

---

## 2. Why This Project Matters

SCD2 is used when a business needs to preserve **full history** of changing records such as:
- customer address changes
- employee department changes
- product attribute changes
- vendor or account status changes

Why it matters:
- compliance and auditability
- point-in-time analytics
- trend analysis
- historical reporting
- less manual code repetition

The project is valuable because current tools only partially solve the problem. Teams still need to configure keys, tracked columns, merge logic, date handling, validation, and explanation/reporting.

---

## 3. Final Product Vision

The final product should behave like a **data engineering copilot**:

### Input
- `source_today.csv`
- `target_yesterday_scd2.csv`

### Core outputs
- updated SCD2 table
- summary of detected changes
- validation report
- natural-language explanations of changes
- downloadable output files

### Optional but strong extras
- detected business key suggestions
- tracked-column suggestions
- health / validation panel
- generated documentation summary
- deployment-ready public UI

---

## 4. Final Recommended Stack

### Core stack
- **Python** — main backend language
- **Streamlit** — UI
- **Prefect 3** — workflow orchestration
- **Polars** — fast dataframe engine
- **DuckDB** — local SQL analytics and validation support
- **Great Expectations GX Core** — data validation
- **Gemini API** — primary LLM explainer
- **Groq API** — fallback LLM provider
- **OpenRouter** — optional router / fallback layer
- **Google Antigravity** — AI-assisted development environment

### Deployment target
- **Hugging Face Spaces** if you want easy public deployment
- **Render** if you want more deployment control
- **Streamlit Community Cloud** if you want the fastest Streamlit-only deployment

### Why this stack
- fast to build
- easy to demo
- deployable publicly
- free/open-source friendly
- strong enough to feel enterprise-like
- minimizes risk compared with PySpark/Spark cluster setups

---

## 5. Why Not PySpark for the MVP

PySpark is powerful, but it is not the best fit for this project’s first version.

Use PySpark only if:
- the data is huge
- distributed processing is necessary
- you already have a Spark environment available

For this project:
- data is CSV-based
- UI and workflow matter more than distributed scale
- deployment simplicity matters
- Polars + DuckDB gives enough performance with less complexity

So the MVP should **not** start with Spark.

---

## 6. High-Level Workflow

### Workflow steps
1. Upload source CSV
2. Upload target SCD2 CSV
3. Detect schema and business key
4. Detect changes deterministically
5. Generate updated SCD2 table
6. Validate result with rules
7. Generate LLM explanations for each change
8. Display everything in Streamlit
9. Save outputs for download and demo evidence

### Important rule
The LLM must **not** decide whether a row changed.
The LLM only explains already-detected changes.

---

## 7. Architecture

### Modules
- `ingestion.py`
- `schema.py`
- `detect_changes.py`
- `transform_scd2.py`
- `validate.py`
- `explain.py`
- `workflow.py`
- `streamlit_app.py`

### Optional provider abstraction
- `providers/base.py`
- `providers/gemini.py`
- `providers/groq.py`
- `providers/openrouter.py`

### Data flow
Source CSV + Target CSV
→ Schema detection
→ Business key selection
→ Change detection
→ SCD2 transform
→ Validation
→ LLM explanation
→ Streamlit display
→ File export

---

## 8. Repo Structure

```text
project-root/
├─ AGENTS.md
├─ README.md
├─ .gitignore
├─ .env.example
├─ requirements.txt
├─ prefect.yaml
├─ Dockerfile
├─ render.yaml
│
├─ src/
│  └─ scd2_copilot/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ ingestion.py
│     ├─ schema.py
│     ├─ detect_changes.py
│     ├─ transform_scd2.py
│     ├─ validate.py
│     ├─ explain.py
│     ├─ workflow.py
│     └─ providers/
│        ├─ base.py
│        ├─ gemini.py
│        ├─ groq.py
│        └─ openrouter.py
│
├─ app/
│  └─ streamlit_app.py
│
├─ validation/
│  ├─ gx_suite/
│  └─ rules.md
│
├─ tests/
│  ├─ test_detect_changes.py
│  ├─ test_transform_scd2.py
│  ├─ test_validate.py
│  └─ test_explain.py
│
├─ sample-data/
│  ├─ source_today.csv
│  ├─ target_yesterday.csv
│  ├─ expected_output.csv
│  └─ edge_cases/
│
├─ docs/
│  ├─ project_brief.md
│  ├─ architecture.md
│  ├─ data_contract.md
│  ├─ acceptance_criteria.md
│  ├─ decision_log.md
│  ├─ prompt_log.md
│  ├─ ai_usage_note.md
│  ├─ demo_script.md
│  ├─ limitations.md
│  └─ deployment_notes.md
│
├─ artifacts/
│  └─ antigravity/
│     ├─ plans/
│     ├─ screenshots/
│     └─ browser-recordings/
│
├─ submission/
│  ├─ team.md
│  ├─ resumes/
│  ├─ demo_video_link.md
│  └─ final_submission_checklist.md
│
└─ .github/
   └─ workflows/
      └─ ci.yml
```

---

## 9. Documents to Maintain

### `AGENTS.md`
Single canonical instruction file for Antigravity. Keep it short and clear.

### `docs/project_brief.md`
Explains the problem, goals, users, and why the project matters.

### `docs/architecture.md`
Explains the full system architecture and stack decisions.

### `docs/data_contract.md`
Defines CSV schema, business key rules, tracked columns, and SCD2 rules.

### `docs/acceptance_criteria.md`
Defines what counts as a successful result.

### `docs/decision_log.md`
Records stack choices, scope decisions, and why certain options were rejected.

### `docs/prompt_log.md`
Records the key prompts used during development and the results.

### `docs/ai_usage_note.md`
Explains what AI helped with, what it got wrong, and what was corrected manually.

### `docs/demo_script.md`
Contains the exact demo flow and speaking order.

### `docs/limitations.md`
Explains what the MVP does not do and what belongs in a future version.

### `docs/deployment_notes.md`
Explains deployment steps for Hugging Face Spaces / Render / Streamlit Cloud.

---

## 10. What to Create Before the First Prompt

Before prompting Antigravity, create these files first:

- `AGENTS.md`
- `docs/project_brief.md`
- `docs/architecture.md`
- `docs/data_contract.md`
- `docs/acceptance_criteria.md`
- `docs/decision_log.md`
- `.env.example`
- `.gitignore`
- `README.md`
- `requirements.txt`
- `sample-data/source_today.csv`
- `sample-data/target_yesterday.csv`
- `tests/test_smoke.py`

This gives Antigravity enough context to work correctly without overwhelming it.

---

## 11. Antigravity Best Practice

Use Antigravity in stages:

### Stage 1 — Planning
Ask it to read the docs and summarize:
- what the project is
- what the stack is
- what the repo structure should be
- what order to build features in
- what risks exist

### Stage 2 — Scaffolding
Ask it to generate:
- empty files
- module skeletons
- initial Streamlit screen
- initial workflow skeleton
- test skeletons

### Stage 3 — Core build
Ask it to implement:
- deterministic change detection
- SCD2 transformation
- validation rules
- explanations
- file export

### Stage 4 — Verification
Ask it to:
- run tests
- generate sample outputs
- fix bugs
- create screenshots / artifacts
- check edge cases

### Stage 5 — Packaging
Ask it to:
- finalize README
- finalize prompt log
- finalize AI usage note
- finalize demo script
- finalize deployment notes

### Stage 6 — Freeze
Stop adding features once:
- the pipeline works
- validations pass
- the UI is stable
- the deployment works
- the documentation is complete

---

## 12. What Antigravity Should Not Do

Do not let it:
- redesign the whole architecture repeatedly
- add multi-agent complexity
- replace deterministic logic with LLM reasoning
- add Spark unless necessary
- add K8s / Docker complexity early
- build a custom MCP server in the MVP
- add a full frontend framework
- overcomplicate the UI

The best use of AI is to accelerate correct work, not to create new risk.

---

## 13. SCD2 Rules

### New record
Insert a new row with:
- `effective_from = today`
- `effective_to = null`
- `is_current = true`

### Changed record
- close old row
- insert new row
- preserve history

### Unchanged record
- keep row unchanged

### Missing record
- treat as soft delete or close based on config

### Validation requirements
- one current row per business key
- no overlapping date ranges
- no duplicate business keys
- no broken null rules

---

## 14. LLM Strategy

### Primary rule
The LLM only explains the detected change.

### Input to LLM
Structured diff, for example:
- key
- old values
- new values
- change type
- processing date

### Output from LLM
Short natural-language explanation.

### Fallback logic
If the primary provider fails:
- try fallback provider
- if all fail, use a deterministic template sentence

This ensures the app remains usable even if the API is down.

---

## 15. Deployment Strategy

### Option 1 — Hugging Face Spaces
Best for:
- public demo
- easy sharing
- Streamlit or Docker deployment
- secrets support

### Option 2 — Streamlit Community Cloud
Best for:
- fastest Streamlit deployment
- simple GitHub-based workflow

### Option 3 — Render
Best for:
- more control
- web-service style deployment
- persistent disks and custom domains

### Recommended default
Use **Hugging Face Spaces** unless deployment constraints suggest otherwise.

---

## 16. Testing Plan

### Unit tests
- change detection
- SCD2 transform
- explanation generation
- validation rules

### Scenario tests
- no change
- one update
- many updates
- new records only
- deleted records
- duplicate business keys
- malformed schema
- missing tracked columns

### Acceptance tests
- end-to-end output matches expected sample
- validations pass
- explanations are generated
- UI shows the right summary

---

## 17. Prompt Logging Plan

Every meaningful prompt should be logged with:
- prompt purpose
- exact prompt
- output received
- what was corrected
- whether it was reused later

This is important for the AI usage note and for showing judges that AI was used responsibly.

---

## 18. Submission Deliverables

The final GitHub repo should contain:
- source code
- tests
- README
- docs
- prompt log
- AI usage note
- sample data
- demo script
- deployment config
- resume PDFs
- demo video link

This matches the project guidelines and keeps the final submission complete.

---

## 19. Final Build Order

### Step 1
Create the context files and repo skeleton.

### Step 2
Implement deterministic SCD2 logic.

### Step 3
Add validation.

### Step 4
Add LLM explanations.

### Step 5
Add Streamlit UI.

### Step 6
Add Prefect workflow.

### Step 7
Add tests.

### Step 8
Add deployment configuration.

### Step 9
Record demo artifacts.

### Step 10
Freeze scope and prepare final submission.

---

## 20. Definition of a Good Final Product

A good final product should:
- feel like a real business tool
- be understandable by a judge in one demo
- be correct
- be explainable
- be deployable
- be documented
- use AI meaningfully without relying on AI for correctness

That is the right boundary between a student project and a real business prototype.
