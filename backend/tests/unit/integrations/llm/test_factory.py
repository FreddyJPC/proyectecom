import pytest

from src.integrations.llm.factory import get_llm_client
from src.integrations.llm.providers.anthropic_provider import AnthropicProvider


def test_anthropic_devuelve_instancia_de_anthropic_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    get_llm_client.cache_clear()

    cliente = get_llm_client()

    assert isinstance(cliente, AnthropicProvider)
    get_llm_client.cache_clear()


def test_anthropic_sin_api_key_falla_rapido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_llm_client.cache_clear()

    with pytest.raises(ValueError):
        get_llm_client()
    get_llm_client.cache_clear()


def test_proveedor_no_soportado_lanza_value_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "otro-no-soportado")
    get_llm_client.cache_clear()

    with pytest.raises(ValueError):
        get_llm_client()
    get_llm_client.cache_clear()
