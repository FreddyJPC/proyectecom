import pytest

from src.config.parametros import parametros
from src.integrations.llm.factory import get_llm_client
from src.integrations.llm.providers.anthropic_provider import AnthropicProvider


def test_anthropic_devuelve_instancia_de_anthropic_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")

    cliente = get_llm_client()

    assert isinstance(cliente, AnthropicProvider)
    assert cliente._modelo == "claude-sonnet-5"


def test_sin_nada_configurado_usa_el_modelo_original_del_catalogo(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    assert get_llm_client()._modelo == "claude-sonnet-5"


def test_el_modelo_sale_del_parametro_y_se_nota_en_el_siguiente_uso(monkeypatch):
    """Cambiar el modelo desde la app no exige reiniciar: la fábrica se consulta en cada uso."""
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    assert get_llm_client()._modelo == "claude-sonnet-5"

    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")  # equivale a un cambio de la variable del servidor
    assert get_llm_client()._modelo == "claude-haiku-5-5"


def test_el_mismo_modelo_reutiliza_el_mismo_proveedor(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")

    assert get_llm_client() is get_llm_client()


def test_anthropic_sin_api_key_falla_rapido(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")

    with pytest.raises(ValueError):
        get_llm_client()


def test_proveedor_no_soportado_lanza_value_error(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "otro-no-soportado")

    with pytest.raises(ValueError):
        get_llm_client()


def test_usa_el_modelo_guardado_en_la_app_aunque_el_servidor_diga_otro(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
    monkeypatch.setenv("LLM_MODEL", "claude-sonnet-5")
    try:
        parametros.guardar("llm.modelo", "claude-opus-5", "test@ejemplo.com")
        assert get_llm_client()._modelo == "claude-opus-5"
    finally:
        parametros.restaurar("llm.modelo", "test@ejemplo.com")
    assert get_llm_client()._modelo == "claude-sonnet-5"
