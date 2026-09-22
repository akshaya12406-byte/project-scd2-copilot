"""Application configuration via pydantic-settings.

Loads settings from .env file and environment variables.
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from pathlib import Path

# pyrefly: ignore [missing-import]
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    """Supported LLM provider identifiers."""

    GEMINI = "gemini"
    GROQ = "groq"
    TEMPLATE = "template"


# ── Active LLM Model Chains (Centralized) ───────────────
GEMINI_MODEL_CHAIN: list[str] = [
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
]

GROQ_MODEL_CHAIN: list[str] = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]


class Settings(BaseSettings):
    """Application-wide settings loaded from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── LLM provider keys ──────────────────────────────
    gemini_api_key: str = ""
    groq_api_key: str = ""
    openrouter_api_key: str = ""

    # ── LLM selection ──────────────────────────────────
    llm_provider: LLMProvider = LLMProvider.TEMPLATE

    # ── App settings ───────────────────────────────────
    app_env: str = "development"
    default_timezone: str = "UTC"

    # ── SCD2 defaults ──────────────────────────────────
    processing_date: date = date.today()

    @property
    def has_gemini_key(self) -> bool:
        return bool(self.gemini_api_key)

    @property
    def has_groq_key(self) -> bool:
        return bool(self.groq_api_key)

    def get_effective_provider(self) -> LLMProvider:
        """Return the best available provider based on config and keys."""
        if self.llm_provider == LLMProvider.GEMINI and self.has_gemini_key:
            return LLMProvider.GEMINI
        if self.llm_provider == LLMProvider.GROQ and self.has_groq_key:
            return LLMProvider.GROQ
        # Fallback chain: try gemini, then groq, then template
        if self.has_gemini_key:
            return LLMProvider.GEMINI
        if self.has_groq_key:
            return LLMProvider.GROQ
        return LLMProvider.TEMPLATE


# ── Paths ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_DATA_DIR = PROJECT_ROOT / "sample-data"


def _extract_streamlit_secrets() -> dict[str, Any]:
    """Safely extract configuration values from st.secrets if running within Streamlit."""
    secrets_dict: dict[str, Any] = {}
    try:
        import sys
        if "streamlit" not in sys.modules:
            return secrets_dict

        import streamlit as st
        if not hasattr(st, "secrets"):
            return secrets_dict

        field_candidates = {
            "gemini_api_key": ("GEMINI_API_KEY", "gemini_api_key"),
            "groq_api_key": ("GROQ_API_KEY", "groq_api_key"),
            "openrouter_api_key": ("OPENROUTER_API_KEY", "openrouter_api_key"),
            "llm_provider": ("LLM_PROVIDER", "llm_provider"),
            "app_env": ("APP_ENV", "app_env"),
            "default_timezone": ("DEFAULT_TIMEZONE", "default_timezone"),
        }

        for field_name, candidates in field_candidates.items():
            for candidate in candidates:
                try:
                    if candidate in st.secrets:
                        val = st.secrets[candidate]
                        if val is not None and str(val).strip():
                            secrets_dict[field_name] = str(val).strip()
                            break
                except Exception:
                    continue
    except Exception:
        pass
    return secrets_dict


def get_settings(**kwargs: Any) -> Settings:
    """Factory that creates a Settings instance with Streamlit secrets support.

    Precedence:
    1. Explicit kwargs passed to get_settings()
    2. Streamlit Cloud Secrets (st.secrets)
    3. Environment variables / .env file
    4. Safe defaults defined in Settings class
    """
    env_file = kwargs.pop("_env_file", ".env")
    try:
        base = Settings(_env_file=env_file)
        base_dict = base.model_dump()
    except Exception:
        base_dict = {}

    # Layer Streamlit secrets
    st_secrets = _extract_streamlit_secrets()
    for k, v in st_secrets.items():
        if v:
            base_dict[k] = v

    # Layer explicit runtime overrides
    for k, v in kwargs.items():
        if v is not None:
            base_dict[k] = v

    return Settings(**base_dict)
