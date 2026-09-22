# AGENTS.md

## Project Mission
Build an AI-powered SCD2 Copilot that:
- accepts a source CSV (today's data)
- accepts a target CSV (yesterday's SCD2 table)
- generates an updated SCD2 table
- validates correctness
- explains every change in human language using an LLM

## Core Rules
- Keep SCD2 logic deterministic and testable.
- Never let the LLM decide whether a row changed.
- The LLM may only explain already-detected changes.
- Prefer free/open tools.
- Keep the app deployable as a public demo.
- Do not introduce unnecessary complexity.

## Approved Stack
- Python
- Streamlit
- Prefect
- Polars
- DuckDB
- Great Expectations
- Gemini API primary
- Groq fallback
- OpenRouter optional fallback
- Google Antigravity for AI-assisted development

## Non-Goals
- No Kubernetes
- No custom MCP server in MVP
- No PySpark cluster unless explicitly approved later
- No multi-agent swarm
- No ML-based change detection
- No heavy frontend framework unless absolutely required

## Required Outputs
- Working app
- Validation checks
- Prompt log
- AI usage note
- Sample data
- Tests
- README
- Demo script
- Deployment notes

## Definition of Done
The project is done only when:
1. source + target CSVs can be uploaded
2. the SCD2 output is correct
3. validation rules pass
4. explanations are generated
5. app runs locally
6. app can be deployed publicly
7. docs and prompt logs are complete

## Working Style
- Start with small, safe changes.
- Read docs before coding.
- Update docs when decisions change.
- Add tests whenever logic changes.
- Save screenshots/artifacts for the demo.