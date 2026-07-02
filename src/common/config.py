"""Loads and validates environment configuration shared by all modules."""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

# Provider registry (api_key env var, model env var, default model) lives in
# config/providers.yaml, not in code -- adding a future provider is a data
# change there plus a matching backend in llm_client.py's _BACKENDS, nothing
# else. Resolved relative to this file, not cwd, so it works regardless of
# where the process is launched from.
_PROVIDERS_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "providers.yaml"


def _load_provider_registry() -> dict[str, tuple[str, str, str]]:
    try:
        with open(_PROVIDERS_CONFIG_PATH, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Provider config file not found at {_PROVIDERS_CONFIG_PATH}. "
            "This file ships with the repo and defines the supported LLM "
            "providers -- if it's missing, check your checkout."
        ) from e

    providers = raw.get("providers") or {}
    return {
        name: (settings["api_key_env"], settings["model_env"], settings["default_model"])
        for name, settings in providers.items()
    }


_PROVIDER_ENV = _load_provider_registry()

_REQUIRED_VARS = [
    "NOTION_TOKEN",
    "NOTION_DATA_SOURCE_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REFRESH_TOKEN",
]


@dataclass(frozen=True)
class Config:
    llm_provider: str
    llm_api_key: str
    llm_model: str
    notion_token: str
    notion_data_source_id: str
    google_client_id: str
    google_client_secret: str
    google_refresh_token: str
    max_emails_per_run: int


def load_config() -> Config:
    llm_provider = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
    if llm_provider not in _PROVIDER_ENV:
        raise RuntimeError(
            f"Invalid LLM_PROVIDER '{llm_provider}'. Must be one of: "
            f"{', '.join(_PROVIDER_ENV)}."
        )
    api_key_var, model_var, default_model = _PROVIDER_ENV[llm_provider]

    missing = [name for name in _REQUIRED_VARS if not os.environ.get(name)]
    if not os.environ.get(api_key_var):
        missing.append(api_key_var)
    if missing:
        raise RuntimeError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Copy .env.example to .env and fill in real values, or set them as "
            "GitHub Actions secrets/variables."
        )

    return Config(
        llm_provider=llm_provider,
        llm_api_key=os.environ[api_key_var],
        llm_model=os.environ.get(model_var, default_model),
        notion_token=os.environ["NOTION_TOKEN"],
        notion_data_source_id=os.environ["NOTION_DATA_SOURCE_ID"],
        google_client_id=os.environ["GOOGLE_CLIENT_ID"],
        google_client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        google_refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        max_emails_per_run=int(os.environ.get("MAX_EMAILS_PER_RUN", "20")),
    )
