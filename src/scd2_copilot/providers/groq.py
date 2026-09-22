"""Groq LLM provider for fallback explanation generation.

Uses the Groq Python SDK to call fast-inference models.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import groq as groq_sdk

from ..config import GROQ_MODEL_CHAIN
from ..models import ChangeRecord, ChangeType, Explanation, LLMMetrics
from .base import LLMProvider
from .template import TemplateProvider

logger = logging.getLogger(__name__)

# Centralized active Groq models fallback chain
MODEL_CHAIN = GROQ_MODEL_CHAIN
MAX_RETRIES_PER_MODEL = 2
RETRY_BASE_DELAY = 1  # seconds for fast failover


class GroqProvider(LLMProvider):
    """Generates explanations using the Groq API with fallback chain."""

    # Retain MODEL property for backward compatibility (defaults to primary chain model)
    MODEL = MODEL_CHAIN[0]

    def __init__(self, api_key: str) -> None:
        self._client = groq_sdk.Groq(api_key=api_key)
        self._working_model: str | None = None

    @property
    def name(self) -> str:
        return "groq"

    def _record_metrics(self, response: Any, prompt: str, content: str, model: str) -> None:
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
            completion_tokens = getattr(usage, "completion_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or 0
            is_estimated = False
        else:
            prompt_tokens = max(1, len(prompt) // 4)
            completion_tokens = max(1, len(content) // 4)
            total_tokens = prompt_tokens + completion_tokens
            is_estimated = True

        cost = (prompt_tokens * 0.10 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)
        self.last_metrics = LLMMetrics(
            provider="groq",
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost,
            is_estimated=is_estimated,
        )

    def explain_change(self, record: ChangeRecord) -> Explanation:
        prompt = _build_prompt(record)
        models = [self._working_model] if self._working_model else list(MODEL_CHAIN)
        last_error: Exception | None = None

        for model in models:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = self._client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a data engineering assistant explaining SCD2 "
                                    "(Slowly Changing Dimension Type 2) changes. "
                                    "Write clear, concise explanations for business users. "
                                    "Do not use markdown."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=600,
                        temperature=0.3,
                    )
                    text = response.choices[0].message.content
                    if not text:
                        text = getattr(response.choices[0].message, "reasoning", "") or ""
                    text = text.strip()
                    if not text:
                        raise ValueError(f"Model {model} returned empty content")

                    self._record_metrics(response, prompt, text, model)
                    self._working_model = model

                    return Explanation(
                        business_key_values=record.business_key_values,
                        change_type=record.change_type,
                        text=text,
                        provider=f"groq ({model})",
                    )
                except Exception as e:
                    last_error = e
                    err_str = str(e).lower()
                    if any(q in err_str for q in ("quota", "resource_exhausted", "404", "not found", "invalid model", "unsupported", "deactivated")):
                        logger.info("Groq model %s quota/unavailable (%s). Trying next model.", model, e)
                        break
                    if attempt < MAX_RETRIES_PER_MODEL and any(t in err_str for t in ("429", "rate limit", "500", "502", "503", "504", "timeout", "connection")):
                        logger.info("Groq model %s transient error (%s). Retrying in %ds...", model, e, RETRY_BASE_DELAY)
                        time.sleep(RETRY_BASE_DELAY)
                        continue
                    logger.warning("Groq model %s failed with %s: %s", model, type(e).__name__, str(e)[:200])
                    break

        if self._working_model:
            self._working_model = None
            return self.explain_change(record)

        raise last_error or RuntimeError("All Groq models failed.")

    def explain_changes_batch(self, records: list[ChangeRecord]) -> list[Explanation]:
        """Generate human-readable explanations for a batch of change records using JSON mode."""
        if not records:
            return []

        prompt = _build_batch_prompt(records)
        prompt += (
            "\n\nReturn the output ONLY as a JSON object containing a key 'explanations' which is a list of objects. "
            "Each object must have 'id' (the integer Record ID) and 'explanation' (the clear, concise 1-2 sentence explanation of the changes). "
            "Example format:\n"
            "{\n"
            "  \"explanations\": [\n"
            "    {\"id\": 0, \"explanation\": \"...\"}\n"
            "  ]\n"
            "}"
        )

        models = [self._working_model] if self._working_model else list(MODEL_CHAIN)
        last_error: Exception | None = None

        for model in models:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = self._client.chat.completions.create(
                        model=model,
                        messages=[
                            {
                                "role": "system",
                                "content": (
                                    "You are a data engineering assistant explaining SCD2 "
                                    "(Slowly Changing Dimension Type 2) changes. "
                                    "Write clear, concise explanations for business users. "
                                    "You must respond ONLY with a valid JSON object matching the requested schema."
                                ),
                            },
                            {"role": "user", "content": prompt},
                        ],
                        max_tokens=2500,
                        temperature=0.3,
                        response_format={"type": "json_object"},
                    )
                    content = response.choices[0].message.content or ""
                    content = content.strip()
                    if not content:
                        raise ValueError(f"Model {model} returned empty JSON content")

                    data = json.loads(content)
                    items = data.get("explanations", [])
                    explanation_map = {
                        item.get("id"): item.get("explanation")
                        for item in items
                        if isinstance(item, dict) and "id" in item
                    }

                    self._record_metrics(response, prompt, content, model)
                    self._working_model = model

                    explanations = []
                    template = TemplateProvider()
                    for idx, record in enumerate(records):
                        text = explanation_map.get(idx)
                        if text:
                            explanations.append(
                                Explanation(
                                    business_key_values=record.business_key_values,
                                    change_type=record.change_type,
                                    text=text,
                                    provider=f"groq ({model})",
                                )
                            )
                        else:
                            explanations.append(template.explain_change(record))
                    return explanations

                except Exception as e:
                    last_error = e
                    err_str = str(e).lower()
                    if any(q in err_str for q in ("quota", "resource_exhausted", "404", "not found", "invalid model", "unsupported", "json")):
                        logger.info("Groq batch model %s failed (%s). Trying next model.", model, e)
                        break
                    if attempt < MAX_RETRIES_PER_MODEL and any(t in err_str for t in ("429", "rate limit", "500", "502", "503", "504", "timeout", "connection")):
                        logger.info("Groq batch model %s transient error (%s). Retrying in %ds...", model, e, RETRY_BASE_DELAY)
                        time.sleep(RETRY_BASE_DELAY)
                        continue
                    logger.warning("Groq batch model %s failed with %s: %s", model, type(e).__name__, str(e)[:200])
                    break

        if self._working_model:
            self._working_model = None
            return self.explain_changes_batch(records)

        raise last_error or RuntimeError("All Groq models failed.")


def _build_prompt(record: ChangeRecord) -> str:
    """Build a prompt for the Groq model."""
    key_str = ", ".join(f"{k}={v}" for k, v in record.business_key_values.items())

    lines = [
        f"Record: {key_str}",
        f"Change type: {record.change_type.value}",
    ]

    if record.change_type == ChangeType.CHANGED and record.field_changes:
        lines.append("Field changes:")
        for fc in record.field_changes:
            lines.append(f"  - {fc.column}: '{fc.old_value}' → '{fc.new_value}'")

    lines.append("")
    lines.append("Explain this SCD2 change in one or two clear sentences.")

    return "\n".join(lines)


def _build_batch_prompt(records: list[ChangeRecord]) -> str:
    """Build a structured prompt for explaining a batch of changes."""
    lines = [
        "You are a data engineering assistant explaining SCD2 (Slowly Changing Dimension Type 2) changes.",
        "For each of the input records, generate a clear, concise explanation of the SCD2 changes in one or two sentences for a business user.",
        "Do not use markdown.",
        "",
        "Input records to explain:",
    ]
    for idx, record in enumerate(records):
        key_str = ", ".join(f"{k}={v}" for k, v in record.business_key_values.items())
        lines.append(f"--- Record ID: {idx} ---")
        lines.append(f"Business key: {key_str}")
        lines.append(f"Change type: {record.change_type.value}")
        if record.change_type == ChangeType.CHANGED and record.field_changes:
            lines.append("Field changes:")
            for fc in record.field_changes:
                lines.append(f"  - {fc.column}: '{fc.old_value}' → '{fc.new_value}'")
        lines.append("")

    return "\n".join(lines)
