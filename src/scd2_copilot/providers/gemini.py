"""Gemini LLM provider via google-genai SDK.

Uses the new unified ``google.genai`` SDK (v2.x) to call Gemini models
for generating human-readable change explanations.

Includes a model fallback chain and retry logic for transient errors.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from google import genai
from pydantic import BaseModel, Field

from ..config import GEMINI_MODEL_CHAIN
from ..models import ChangeRecord, ChangeType, Explanation, LLMMetrics
from .base import LLMProvider
from .template import TemplateProvider

logger = logging.getLogger(__name__)

# Model fallback chain: centralized active Gemini models
MODEL_CHAIN = GEMINI_MODEL_CHAIN

MAX_RETRIES_PER_MODEL = 2
RETRY_BASE_DELAY = 1  # seconds for fast failover


class ExplanationItem(BaseModel):
    """Pydantic model for a single structured explanation item."""

    id: int = Field(description="The Record ID (index) from the input list.")
    explanation: str = Field(
        description="The clear, concise 1-2 sentence business explanation of the change."
    )


class GeminiProvider(LLMProvider):
    """Generates explanations using the Gemini API with model fallback."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._working_model: str | None = None  # cache the first model that works

    @property
    def name(self) -> str:
        return "gemini"

    def explain_change(self, record: ChangeRecord) -> Explanation:
        prompt = _build_prompt(record)
        text, model_used = self._call_with_fallback(prompt, config={"max_output_tokens": 300})

        return Explanation(
            business_key_values=record.business_key_values,
            change_type=record.change_type,
            text=text,
            provider=f"gemini ({model_used})",
        )

    def explain_changes_batch(self, records: list[ChangeRecord]) -> list[Explanation]:
        """Generate human-readable explanations for a batch of change records using structured output."""
        if not records:
            return []

        prompt = _build_batch_prompt(records)

        # Setup structured output config using Pydantic model list
        config = {
            "response_mime_type": "application/json",
            "response_schema": list[ExplanationItem],
            "max_output_tokens": 2000,
        }

        try:
            parsed_items, model_used = self._call_with_fallback(prompt, config=config)
        except Exception as e:
            logger.warning("Gemini batch API call failed: %s", e)
            raise

        # Map parsed results back to input records
        explanation_map = {}
        if isinstance(parsed_items, list):
            for item in parsed_items:
                if isinstance(item, ExplanationItem):
                    explanation_map[item.id] = item.explanation
                elif isinstance(item, dict):
                    explanation_map[item.get("id")] = item.get("explanation")

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
                        provider=f"gemini ({model_used})",
                    )
                )
            else:
                # Fallback to local template explanation for missing items in the parsed response
                explanations.append(template.explain_change(record))

        return explanations

    def _call_with_fallback(
        self, prompt: str, config: dict | None = None
    ) -> tuple[Any, str]:
        """Try models in the fallback chain until one succeeds.

        Returns:
            Tuple of (response_text or parsed_object, model_name).

        Raises:
            Last exception if all models and retries fail.
        """
        # If we already found a working model, try it first
        models = (
            [self._working_model] if self._working_model
            else list(MODEL_CHAIN)
        )

        last_error: Exception | None = None

        for model in models:
            for attempt in range(1, MAX_RETRIES_PER_MODEL + 1):
                try:
                    response = self._client.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=config,
                    )

                    # Extract text or parsed schema depending on configuration
                    if config and "response_schema" in config:
                        result = response.parsed
                        if result is None:
                            raise ValueError(f"Model {model} returned empty or unparsed structured output")
                    else:
                        result = response.text.strip() if response.text else ""

                    # Extract usage metadata
                    usage = getattr(response, "usage_metadata", None)
                    if usage:
                        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
                        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
                        total_tokens = getattr(usage, "total_token_count", 0) or 0
                        is_estimated = False
                    else:
                        # Character-based estimation: 4 chars per token roughly
                        prompt_tokens = max(1, len(prompt) // 4)
                        completion_tokens = max(1, len(str(result)) // 4)
                        total_tokens = prompt_tokens + completion_tokens
                        is_estimated = True

                    # Estimate cost: Prompt: $0.075 / 1M, Completion: $0.30 / 1M
                    cost = (prompt_tokens * 0.075 / 1_000_000) + (completion_tokens * 0.30 / 1_000_000)

                    self.last_metrics = LLMMetrics(
                        provider="gemini",
                        model=model,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                        estimated_cost=cost,
                        is_estimated=is_estimated,
                    )

                    # Cache this model for future calls
                    self._working_model = model
                    return result, model

                except Exception as e:
                    last_error = e
                    err_str = str(e).lower()

                    # Immediate fallback (no retry) for quota exhaustion, 404, invalid model
                    if any(q in err_str for q in ("perday", "quota", "resource_exhausted", "404", "not found", "invalid model", "unsupported", "parse")):
                        logger.info("Model %s unavailable or quota exhausted (%s). Trying next model in chain.", model, e)
                        break

                    # Retry at most once for transient rate limit or server error
                    if attempt < MAX_RETRIES_PER_MODEL and any(t in err_str for t in ("429", "rate limit", "500", "502", "503", "504", "timeout", "connection")):
                        delay = RETRY_BASE_DELAY
                        logger.info("Model %s transient error (%s). Retrying in %ds...", model, e, delay)
                        time.sleep(delay)
                        continue

                    # Otherwise, fail over to the next model immediately
                    logger.warning("Model %s failed with %s: %s. Moving to next model.", model, type(e).__name__, str(e)[:200])
                    break

        # If cached model failed, try the full chain
        if self._working_model:
            self._working_model = None
            return self._call_with_fallback(prompt, config=config)

        # All models exhausted
        raise last_error or RuntimeError("All Gemini models failed.")


def _build_prompt(record: ChangeRecord) -> str:
    """Build a structured prompt for the LLM from a ChangeRecord."""
    key_str = ", ".join(f"{k}={v}" for k, v in record.business_key_values.items())

    lines = [
        "You are a data engineering assistant explaining SCD2 (Slowly Changing Dimension Type 2) changes.",
        "Explain the following change in one or two clear sentences for a business user.",
        "",
        f"Record: {key_str}",
        f"Change type: {record.change_type.value}",
    ]

    if record.change_type == ChangeType.CHANGED and record.field_changes:
        lines.append("Field changes:")
        for fc in record.field_changes:
            lines.append(f"  - {fc.column}: '{fc.old_value}' → '{fc.new_value}'")

    lines.append("")
    lines.append("Write a clear, concise explanation. Do not use markdown.")

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
