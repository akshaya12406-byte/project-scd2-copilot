"""Tests for LLM model stack migration, model chains, and multi-tier fallback resilience."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import polars as pl

from src.scd2_copilot.config import (
    GEMINI_MODEL_CHAIN,
    GROQ_MODEL_CHAIN,
    LLMProvider,
    Settings,
    get_settings,
)
from src.scd2_copilot.detect_changes import detect_changes
from src.scd2_copilot.explain import explain_changes, get_provider
from src.scd2_copilot.models import ChangeRecord, ChangeReport, ChangeType, FieldChange
from src.scd2_copilot.providers.gemini import GeminiProvider
from src.scd2_copilot.providers.groq import GroqProvider
from src.scd2_copilot.providers.template import TemplateProvider
from src.scd2_copilot.transform_scd2 import apply_scd2
from src.scd2_copilot.validate import validate_scd2


# ── 1. Model Chain Definitions ──────────────────────────────────────────────

def test_gemini_model_chain_exact_ordering():
    """Verify Gemini model chain has exact expected models in required order."""
    expected = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
    ]
    assert GEMINI_MODEL_CHAIN == expected
    from src.scd2_copilot.providers.gemini import MODEL_CHAIN
    assert MODEL_CHAIN == expected


def test_groq_model_chain_exact_ordering():
    """Verify Groq model chain has exact expected models in required order."""
    expected = [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
    ]
    assert GROQ_MODEL_CHAIN == expected
    from src.scd2_copilot.providers.groq import MODEL_CHAIN
    assert MODEL_CHAIN == expected


# ── 2. Repository-Wide Deprecation Audit ─────────────────────────────────────

def test_no_deprecated_model_ids_in_src():
    """Verify that no deprecated model IDs exist in runtime source files."""
    deprecated_tokens = [
        "gemini-2.0",
        "gemini-2.5",
        "gemini-3-preview",
        "gemini-3.1",
        "gemini-3-flash",
        "llama-3.3",
        "llama-3.1",
        "qwen",
        "compound",
    ]

    src_dir = Path(__file__).resolve().parent.parent / "src"
    py_files = list(src_dir.rglob("*.py"))
    assert py_files, "No python source files found in src/"

    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8").lower()
        for token in deprecated_tokens:
            assert token not in content, (
                f"Found deprecated model token '{token}' in {py_file.name}"
            )


# ── 3. Gemini Fallback Behavior (429, 503, Timeout, Malformed) ───────────────

@patch("google.genai.Client")
def test_gemini_429_quota_fails_over_to_next_model(mock_genai_client):
    """Verify Gemini 429 quota exhaustion immediately tries the next model."""
    mock_instance = MagicMock()
    mock_genai_client.return_value = mock_instance

    called_models = []

    def fake_generate_content(model, contents, config=None):
        called_models.append(model)
        if model == GEMINI_MODEL_CHAIN[0]:
            raise Exception("429 ResourceExhausted: Quota exceeded for model")
        # Second model succeeds
        mock_response = MagicMock()
        mock_response.text = "Second model succeeded"
        mock_response.parsed = None
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10, candidates_token_count=5, total_token_count=15
        )
        return mock_response

    mock_instance.models.generate_content.side_effect = fake_generate_content

    provider = GeminiProvider(api_key="mock_key")
    record = ChangeRecord({"id": 1}, ChangeType.NEW)
    explanation = provider.explain_change(record)

    assert GEMINI_MODEL_CHAIN[0] in called_models
    assert GEMINI_MODEL_CHAIN[1] in called_models
    assert f"gemini ({GEMINI_MODEL_CHAIN[1]})" in explanation.provider
    assert provider.last_metrics.model == GEMINI_MODEL_CHAIN[1]


@patch("google.genai.Client")
def test_gemini_503_and_timeout_failover(mock_genai_client):
    """Verify 503 server error and timeout trigger failover across models."""
    mock_instance = MagicMock()
    mock_genai_client.return_value = mock_instance

    called_models = []

    def fake_generate_content(model, contents, config=None):
        called_models.append(model)
        if len(called_models) == 1:
            raise Exception("503 Service Unavailable")
        if len(called_models) == 2:
            raise TimeoutError("Connection timed out after 30s")
        # Third model in chain succeeds
        mock_response = MagicMock()
        mock_response.text = "Recovered on 3rd model"
        mock_response.parsed = None
        mock_response.usage_metadata = None
        return mock_response

    mock_instance.models.generate_content.side_effect = fake_generate_content

    provider = GeminiProvider(api_key="mock_key")
    record = ChangeRecord({"id": 1}, ChangeType.NEW)
    explanation = provider.explain_change(record)

    assert "Recovered on 3rd model" in explanation.text
    assert explanation.provider == f"gemini ({GEMINI_MODEL_CHAIN[1]})"


@patch("google.genai.Client")
def test_gemini_malformed_batch_response_handled(mock_genai_client):
    """Verify structured output parsing error triggers model fallback or local template."""
    mock_instance = MagicMock()
    mock_genai_client.return_value = mock_instance

    mock_response = MagicMock()
    mock_response.parsed = None  # None parsed response triggers error
    mock_response.text = "Not valid JSON"
    mock_instance.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="mock_key")
    records = [ChangeRecord({"id": 1}, ChangeType.NEW)]

    with pytest.raises(Exception):
        # When all models return unparsed/empty structured output, it raises to trigger higher-tier fallback
        provider.explain_changes_batch(records)


# ── 4. Groq Fallback Chain (20B -> 120B) ─────────────────────────────────────

@patch("groq.Groq")
def test_groq_fallback_chain_20b_to_120b(mock_groq_client):
    """Verify Groq fails over from openai/gpt-oss-20b to openai/gpt-oss-120b upon failure."""
    mock_instance = MagicMock()
    mock_groq_client.return_value = mock_instance

    called_models = []

    def fake_create(model, messages, **kwargs):
        called_models.append(model)
        if model == "openai/gpt-oss-20b":
            raise Exception("429 rate limit reached for 20b")
        # 120b succeeds
        mock_resp = MagicMock()
        mock_resp.choices = [
            MagicMock(message=MagicMock(content="120b explanation", reasoning=None))
        ]
        mock_resp.usage = MagicMock(prompt_tokens=25, completion_tokens=15, total_tokens=40)
        return mock_resp

    mock_instance.chat.completions.create.side_effect = fake_create

    provider = GroqProvider(api_key="mock_groq_key")
    record = ChangeRecord({"id": 1}, ChangeType.NEW)
    explanation = provider.explain_change(record)

    assert called_models[0] == "openai/gpt-oss-20b"
    assert "openai/gpt-oss-120b" in called_models
    assert explanation.provider == "groq (openai/gpt-oss-120b)"
    assert explanation.text == "120b explanation"
    assert provider.last_metrics.model == "openai/gpt-oss-120b"


# ── 5. Multi-Tier Fallback: Gemini -> Groq -> Local Template ─────────────────

@patch("google.genai.Client")
@patch("groq.Groq")
def test_gemini_unavailable_cascades_to_groq(mock_groq_client, mock_genai_client):
    """When Gemini completely fails, pipeline cascades to Groq if key is present."""
    # Gemini fails on all attempts
    mock_genai = MagicMock()
    mock_genai_client.return_value = mock_genai
    mock_genai.models.generate_content.side_effect = Exception("ResourceExhausted: 429 quota")

    # Groq succeeds
    mock_groq = MagicMock()
    mock_groq_client.return_value = mock_groq
    mock_groq_resp = MagicMock()
    mock_groq_resp.choices = [
        MagicMock(
            message=MagicMock(
                content='{"explanations": [{"id": 0, "explanation": "Handled by Groq"}]}',
                reasoning=None,
            )
        )
    ]
    mock_groq_resp.usage = MagicMock(prompt_tokens=20, completion_tokens=10, total_tokens=30)
    mock_groq.chat.completions.create.return_value = mock_groq_resp

    settings = Settings(
        _env_file=None,
        gemini_api_key="mock_gemini",
        groq_api_key="mock_groq",
        llm_provider=LLMProvider.GEMINI,
    )

    report = ChangeReport(
        new=[ChangeRecord({"customer_id": 101}, ChangeType.NEW)],
        processing_date=date(2026, 6, 8),
    )

    result = explain_changes(report, settings=settings)

    assert len(result.explanations) == 1
    assert result.provider_used == "groq"
    assert result.explanations[0].text == "Handled by Groq"
    assert any("Falling back to Groq" in w for w in result.warnings)


@patch("google.genai.Client")
@patch("groq.Groq")
def test_gemini_and_groq_unavailable_cascades_to_template(mock_groq_client, mock_genai_client):
    """When both Gemini and Groq fail, pipeline safely degrades to local template."""
    mock_genai = MagicMock()
    mock_genai_client.return_value = mock_genai
    mock_genai.models.generate_content.side_effect = Exception("Gemini 429 Quota Exceeded")

    mock_groq = MagicMock()
    mock_groq_client.return_value = mock_groq
    mock_groq.chat.completions.create.side_effect = Exception("Groq 503 Service Unavailable")

    settings = Settings(
        _env_file=None,
        gemini_api_key="mock_gemini",
        groq_api_key="mock_groq",
        llm_provider=LLMProvider.GEMINI,
    )

    report = ChangeReport(
        new=[ChangeRecord({"customer_id": 101}, ChangeType.NEW)],
        processing_date=date(2026, 6, 8),
    )

    result = explain_changes(report, settings=settings)

    assert len(result.explanations) == 1
    assert result.provider_used == "template"
    assert result.explanations[0].provider == "template"
    assert "customer_id=101" in result.explanations[0].text
    assert any("Fell back to template" in w for w in result.warnings)


def test_missing_gemini_key_uses_groq_or_template():
    """When Gemini key is missing but Groq is provided, Groq is used."""
    settings = Settings(
        _env_file=None,
        gemini_api_key="",
        groq_api_key="mock_groq",
        llm_provider=LLMProvider.GEMINI,
    )
    provider = get_provider(settings)
    assert isinstance(provider, GroqProvider)
    assert provider.name == "groq"


def test_missing_groq_and_gemini_keys_uses_template():
    """When no API keys exist, pipeline defaults directly to TemplateProvider."""
    settings = Settings(
        _env_file=None,
        gemini_api_key="",
        groq_api_key="",
        llm_provider=LLMProvider.GROQ,
    )
    provider = get_provider(settings)
    assert isinstance(provider, TemplateProvider)
    assert provider.name == "template"


# ── 6. Metrics Recording ─────────────────────────────────────────────────────

@patch("google.genai.Client")
def test_metrics_recorded_correctly_on_gemini_success(mock_genai_client):
    """Verify LLMMetrics are correctly captured on Gemini success."""
    mock_instance = MagicMock()
    mock_genai_client.return_value = mock_instance

    mock_response = MagicMock()
    mock_response.text = "Explanations generated"
    mock_response.parsed = None
    mock_response.usage_metadata = MagicMock(
        prompt_token_count=45, candidates_token_count=20, total_token_count=65
    )
    mock_instance.models.generate_content.return_value = mock_response

    provider = GeminiProvider(api_key="mock_key")
    record = ChangeRecord({"id": 101}, ChangeType.NEW)
    provider.explain_change(record)

    metrics = provider.last_metrics
    assert metrics is not None
    assert metrics.provider == "gemini"
    assert metrics.model in GEMINI_MODEL_CHAIN
    assert metrics.prompt_tokens == 45
    assert metrics.completion_tokens == 20
    assert metrics.total_tokens == 65
    assert metrics.estimated_cost > 0.0
    assert not metrics.is_estimated


# ── 7. Deterministic SCD2 Engine Verification ────────────────────────────────

def test_deterministic_scd2_pipeline_unchanged():
    """Verify that detect_changes, apply_scd2, and validate_scd2 remain deterministic and intact."""
    source = pl.DataFrame({
        "customer_id": [1, 2, 3],
        "name": ["Alice", "Bob Modified", "Charlie New"],
    })
    target = pl.DataFrame({
        "customer_id": [1, 2, 4],
        "name": ["Alice", "Bob", "Dan Deleted"],
        "effective_from": [date(2026, 6, 1)] * 3,
        "effective_to": [None] * 3,
        "is_current": [True] * 3,
    })

    pd = date(2026, 6, 8)
    report = detect_changes(source, target, ["customer_id"], ["name"], pd)

    assert len(report.new) == 1
    assert report.new[0].business_key_values == {"customer_id": 3}
    assert len(report.changed) == 1
    assert report.changed[0].business_key_values == {"customer_id": 2}
    assert len(report.unchanged) == 1
    assert report.unchanged[0].business_key_values == {"customer_id": 1}
    assert len(report.deleted) == 1
    assert report.deleted[0].business_key_values == {"customer_id": 4}

    output = apply_scd2(source, target, report, ["customer_id"], ["name"], pd)
    val = validate_scd2(output, ["customer_id"])

    assert val.passed
    assert output.height == 5  # 1 unchanged + 2 for changed (closed + new) + 1 new + 1 closed deleted
