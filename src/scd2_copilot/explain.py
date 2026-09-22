"""Explanation orchestration: generate explanations for all detected changes.

Routes change records through the multi-tier provider chain:
Gemini (5 models) → Groq (2 models) → Local deterministic template.
Tracks fallback events and metrics so the UI can inform the user.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .config import LLMProvider as LLMProviderEnum, Settings
from .models import ChangeRecord, ChangeReport, Explanation, LLMMetrics
from .providers.base import LLMProvider
from .providers.gemini import GeminiProvider
from .providers.groq import GroqProvider
from .providers.template import TemplateProvider

logger = logging.getLogger(__name__)


@dataclass
class ExplainResult:
    """Result of explanation generation, including any warnings."""

    explanations: list[Explanation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provider_used: str = "template"
    metrics: Optional[LLMMetrics] = None


def get_provider(settings: Settings) -> LLMProvider:
    """Create the appropriate primary LLM provider based on settings.

    Falls back through: configured provider → next available → template.
    """
    effective = settings.get_effective_provider()

    if effective == LLMProviderEnum.GEMINI:
        return GeminiProvider(api_key=settings.gemini_api_key)
    elif effective == LLMProviderEnum.GROQ:
        return GroqProvider(api_key=settings.groq_api_key)
    else:
        return TemplateProvider()


def explain_changes(
    change_report: ChangeReport,
    settings: Optional[Settings] = None,
    provider: Optional[LLMProvider] = None,
) -> ExplainResult:
    """Generate explanations for all non-unchanged changes using batch processing.

    Uses a multi-tier fallback chain:
    Gemini (5 models) → Groq (2 models) → Template.
    Returns an ExplainResult with explanations and any fallback warnings.

    Args:
        change_report: The detected changes.
        settings: App settings (used to configure providers and fallbacks).
        provider: Override provider instance (for testing).

    Returns:
        ExplainResult with explanations list, warnings list, and performance metrics.
    """
    if settings is None and provider is None:
        from .config import get_settings
        settings = get_settings()

    # Collect all records that need explanation
    records_to_explain: list[ChangeRecord] = (
        change_report.new + change_report.changed + change_report.deleted
    )

    template = TemplateProvider()
    result = ExplainResult()

    if not records_to_explain:
        result.provider_used = provider.name if provider else (
            get_provider(settings).name if settings else "template"
        )
        return result

    # Build the sequence of providers to attempt in order
    providers_to_try: list[LLMProvider] = []
    if provider is not None:
        providers_to_try.append(provider)
        if provider.name == "gemini" and settings and settings.has_groq_key:
            providers_to_try.append(GroqProvider(api_key=settings.groq_api_key))
    elif settings is not None:
        effective = settings.get_effective_provider()
        if effective == LLMProviderEnum.GEMINI:
            providers_to_try.append(GeminiProvider(api_key=settings.gemini_api_key))
            if settings.has_groq_key:
                providers_to_try.append(GroqProvider(api_key=settings.groq_api_key))
        elif effective == LLMProviderEnum.GROQ:
            providers_to_try.append(GroqProvider(api_key=settings.groq_api_key))
            if settings.has_gemini_key:
                providers_to_try.append(GeminiProvider(api_key=settings.gemini_api_key))
        else:
            providers_to_try.append(template)

    if not providers_to_try:
        providers_to_try.append(template)

    t_start = time.perf_counter()
    success = False

    for idx, current_provider in enumerate(providers_to_try):
        if current_provider.name == "template":
            break

        try:
            explanations = current_provider.explain_changes_batch(records_to_explain)
            duration = time.perf_counter() - t_start

            # Calculate template fallbacks within the batch
            fallback_count = sum(1 for exp in explanations if exp.provider == "template")
            if fallback_count > 0:
                result.warnings.append(
                    f"⚠️ {current_provider.name.capitalize()} API fell back to template "
                    f"for {fallback_count} explanation(s) due to missing items in the response."
                )

            result.explanations = explanations
            result.provider_used = current_provider.name

            metrics = getattr(current_provider, "last_metrics", None)
            if metrics:
                metrics.request_duration = duration
                metrics.num_changes_explained = len(records_to_explain)
                metrics.avg_tokens_per_change = (
                    metrics.total_tokens / len(records_to_explain)
                ) if records_to_explain else 0.0
                result.metrics = metrics

            success = True
            break

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.warning("Provider '%s' failed: %s", current_provider.name, e)

            # Check if there is another LLM provider in chain
            has_next_llm = (idx + 1 < len(providers_to_try) and providers_to_try[idx + 1].name != "template")
            if has_next_llm:
                next_name = providers_to_try[idx + 1].name.capitalize()
                result.warnings.append(
                    f"⚠️ {current_provider.name.capitalize()} API failed: {error_msg}. Falling back to {next_name}."
                )
            else:
                result.warnings.append(
                    f"⚠️ {current_provider.name.capitalize()} API failed: {error_msg}. Fell back to template."
                )

    if not success:
        # Generate with offline template
        duration = time.perf_counter() - t_start
        result.explanations = [template.explain_change(r) for r in records_to_explain]
        result.provider_used = "template"
        result.metrics = LLMMetrics(
            provider="template",
            model="local-templates",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            estimated_cost=0.0,
            request_duration=duration,
            num_changes_explained=len(records_to_explain),
            avg_tokens_per_change=0.0,
            is_estimated=False,
        )

    return result
