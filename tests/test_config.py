import pytest

from src.common import config as config_module

_REQUIRED_NON_LLM_VARS = {
    "NOTION_TOKEN": "notion-token",
    "NOTION_DATA_SOURCE_ID": "db-id",
    "GOOGLE_CLIENT_ID": "client-id",
    "GOOGLE_CLIENT_SECRET": "client-secret",
    "GOOGLE_REFRESH_TOKEN": "refresh-token",
}


def _set_env(monkeypatch, **overrides):
    for key, value in _REQUIRED_NON_LLM_VARS.items():
        monkeypatch.setenv(key, value)
    for key, value in overrides.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_defaults_to_anthropic_provider(monkeypatch):
    _set_env(monkeypatch, LLM_PROVIDER=None, ANTHROPIC_API_KEY="sk-ant-123")

    config = config_module.load_config()

    assert config.llm_provider == "anthropic"
    assert config.llm_api_key == "sk-ant-123"
    assert config.llm_model == "claude-sonnet-5"


def test_openai_provider_selection_and_model_default(monkeypatch):
    _set_env(monkeypatch, LLM_PROVIDER="openai", OPENAI_API_KEY="sk-openai-123")

    config = config_module.load_config()

    assert config.llm_provider == "openai"
    assert config.llm_api_key == "sk-openai-123"
    assert config.llm_model == "gpt-4o-mini"


def test_gemini_provider_model_override(monkeypatch):
    _set_env(
        monkeypatch,
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="gm-123",
        GEMINI_MODEL="gemini-custom",
    )

    config = config_module.load_config()

    assert config.llm_provider == "gemini"
    assert config.llm_api_key == "gm-123"
    assert config.llm_model == "gemini-custom"


def test_provider_is_case_insensitive(monkeypatch):
    _set_env(monkeypatch, LLM_PROVIDER="OpenAI", OPENAI_API_KEY="sk-openai-123")

    config = config_module.load_config()

    assert config.llm_provider == "openai"


def test_invalid_provider_raises(monkeypatch):
    _set_env(monkeypatch, LLM_PROVIDER="carrier-pigeon")

    with pytest.raises(RuntimeError, match="Invalid LLM_PROVIDER"):
        config_module.load_config()


def test_missing_selected_provider_api_key_raises(monkeypatch):
    _set_env(monkeypatch, LLM_PROVIDER="anthropic", ANTHROPIC_API_KEY=None)

    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        config_module.load_config()


def test_missing_unselected_provider_api_key_is_fine(monkeypatch):
    # Only the selected provider's key is required -- OPENAI_API_KEY/GEMINI_API_KEY
    # being unset should not block startup when LLM_PROVIDER=anthropic.
    _set_env(
        monkeypatch,
        LLM_PROVIDER="anthropic",
        ANTHROPIC_API_KEY="sk-ant-123",
        OPENAI_API_KEY=None,
        GEMINI_API_KEY=None,
    )

    config_module.load_config()  # should not raise


def test_missing_notion_or_google_vars_raises(monkeypatch):
    _set_env(monkeypatch, ANTHROPIC_API_KEY="sk-ant-123", NOTION_TOKEN=None)

    with pytest.raises(RuntimeError, match="NOTION_TOKEN"):
        config_module.load_config()
