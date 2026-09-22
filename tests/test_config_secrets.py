"""Tests for configuration bridge and Streamlit secrets integration."""

from __future__ import annotations

import sys
from unittest.mock import patch, MagicMock

import pytest

from src.scd2_copilot.config import Settings, get_settings, LLMProvider
from src.scd2_copilot.explain import get_provider
from src.scd2_copilot.providers.template import TemplateProvider


def test_config_without_streamlit_secrets():
    """Verify get_settings returns valid defaults when no st.secrets exist."""
    # Pass _env_file=None to simulate a clean environment without .env
    settings = get_settings(_env_file=None, gemini_api_key="", groq_api_key="")
    assert settings.gemini_api_key == ""
    assert settings.groq_api_key == ""
    assert not settings.has_gemini_key
    assert not settings.has_groq_key
    assert settings.get_effective_provider() == LLMProvider.TEMPLATE


def test_config_with_streamlit_secrets():
    """Verify get_settings correctly layers st.secrets."""
    fake_secrets = {
        "GEMINI_API_KEY": "fake_mock_gemini_key_12345",
        "GROQ_API_KEY": "fake_mock_groq_key_67890",
        "LLM_PROVIDER": "groq",
    }
    mock_st = MagicMock()
    mock_st.secrets = fake_secrets

    with patch.dict(sys.modules, {"streamlit": mock_st}):
        settings = get_settings(_env_file=None)
        assert settings.gemini_api_key == "fake_mock_gemini_key_12345"
        assert settings.groq_api_key == "fake_mock_groq_key_67890"
        assert settings.has_gemini_key
        assert settings.has_groq_key
        assert settings.llm_provider == LLMProvider.GROQ
        assert settings.get_effective_provider() == LLMProvider.GROQ


def test_config_precedence():
    """Verify precedence: runtime kwargs > st.secrets > defaults."""
    fake_secrets = {
        "GEMINI_API_KEY": "secret_gemini_key",
        "GROQ_API_KEY": "secret_groq_key",
    }
    mock_st = MagicMock()
    mock_st.secrets = fake_secrets

    with patch.dict(sys.modules, {"streamlit": mock_st}):
        # Runtime kwargs override secrets
        settings = get_settings(_env_file=None, gemini_api_key="runtime_gemini_override")
        assert settings.gemini_api_key == "runtime_gemini_override"
        assert settings.groq_api_key == "secret_groq_key"


def test_missing_keys_fallback_to_template():
    """Verify missing Gemini and Groq keys safely fall back to template provider."""
    settings = get_settings(_env_file=None, gemini_api_key="", groq_api_key="", llm_provider=LLMProvider.GEMINI)
    effective = settings.get_effective_provider()
    assert effective == LLMProvider.TEMPLATE

    provider = get_provider(settings)
    assert isinstance(provider, TemplateProvider)
    assert provider.name == "template"


def test_missing_groq_key_fallback():
    """Verify missing Groq key when Groq requested falls back safely."""
    settings = get_settings(_env_file=None, gemini_api_key="", groq_api_key="", llm_provider=LLMProvider.GROQ)
    assert settings.get_effective_provider() == LLMProvider.TEMPLATE

    provider = get_provider(settings)
    assert isinstance(provider, TemplateProvider)
