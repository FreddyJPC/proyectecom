from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

from src.integrations.llm.contratos import (
    HerramientaLLM,
    LlamadaHerramienta,
    MensajeLLM,
    ResultadoHerramienta,
)
from src.integrations.llm.exceptions import LLMAuthError, LLMRateLimitError, LLMRequestError
from src.integrations.llm.providers.anthropic_provider import AnthropicProvider


def _provider_con_cliente_falso():
    with patch("src.integrations.llm.providers.anthropic_provider.anthropic.Anthropic") as ClaseCliente:
        cliente_falso = MagicMock()
        ClaseCliente.return_value = cliente_falso
        provider = AnthropicProvider(api_key="sk-test", modelo="claude-sonnet-5")
    return provider, cliente_falso


def _respuesta_http(status_code: int) -> httpx.Response:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return httpx.Response(status_code, request=request, json={"error": {"message": "error de prueba"}})


def _mensaje_anthropic(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class TestTraduccionDeEntrada:
    def test_mensaje_de_texto_simple(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[SimpleNamespace(type="text", text="hola")], stop_reason="end_turn"
        )

        provider.generar_respuesta(
            system="prompt del sistema",
            mensajes=[MensajeLLM(rol="user", texto="Quiero comprar")],
            herramientas=[],
        )

        kwargs = cliente.messages.create.call_args.kwargs
        assert kwargs["model"] == "claude-sonnet-5"
        assert kwargs["system"] == "prompt del sistema"
        assert kwargs["messages"] == [{"role": "user", "content": "Quiero comprar"}]
        assert kwargs["tools"] == []

    def test_herramientas_a_input_schema(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[SimpleNamespace(type="text", text="ok")], stop_reason="end_turn"
        )
        herramienta = HerramientaLLM(
            nombre="registrar_producto",
            descripcion="Registra el producto.",
            parametros={"type": "object", "properties": {"sku": {"type": "string"}}},
        )

        provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[herramienta])

        tools = cliente.messages.create.call_args.kwargs["tools"]
        assert tools == [{
            "name": "registrar_producto",
            "description": "Registra el producto.",
            "input_schema": {"type": "object", "properties": {"sku": {"type": "string"}}},
        }]

    def test_llamada_y_resultado_de_herramienta(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[SimpleNamespace(type="text", text="listo")], stop_reason="end_turn"
        )

        mensajes = [
            MensajeLLM(rol="user", texto="Quiero el producto X"),
            MensajeLLM(
                rol="assistant",
                texto="Anotado",
                llamadas_herramientas=[
                    LlamadaHerramienta(id="toolu_1", nombre="registrar_producto", entrada={"producto_sku": "X"})
                ],
            ),
            MensajeLLM(
                rol="user",
                resultados_herramientas=[
                    ResultadoHerramienta(id_llamada="toolu_1", contenido="Producto registrado.")
                ],
            ),
        ]

        provider.generar_respuesta(system="s", mensajes=mensajes, herramientas=[])

        traducidos = cliente.messages.create.call_args.kwargs["messages"]
        assert traducidos[0] == {"role": "user", "content": "Quiero el producto X"}
        assert traducidos[1] == {
            "role": "assistant",
            "content": [
                {"type": "text", "text": "Anotado"},
                {"type": "tool_use", "id": "toolu_1", "name": "registrar_producto", "input": {"producto_sku": "X"}},
            ],
        }
        assert traducidos[2] == {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "Producto registrado."}],
        }


class TestTraduccionDeSalida:
    def test_respuesta_con_tool_use(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[
                SimpleNamespace(type="text", text="Un momento..."),
                SimpleNamespace(type="tool_use", id="toolu_2", name="cerrar_venta", input={}),
            ],
            stop_reason="tool_use",
        )

        respuesta = provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

        assert respuesta.texto == "Un momento..."
        assert respuesta.llamadas_herramientas == [LlamadaHerramienta(id="toolu_2", nombre="cerrar_venta", entrada={})]
        assert respuesta.razon_de_parada == "necesita_herramientas"

    def test_respuesta_de_fin(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[SimpleNamespace(type="text", text="Gracias por tu compra")], stop_reason="end_turn"
        )

        respuesta = provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

        assert respuesta.texto == "Gracias por tu compra"
        assert respuesta.llamadas_herramientas == []
        assert respuesta.razon_de_parada == "fin"

    def test_respuesta_de_limite_alcanzado(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.return_value = _mensaje_anthropic(
            content=[SimpleNamespace(type="text", text="texto cortado")], stop_reason="max_tokens"
        )

        respuesta = provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

        assert respuesta.razon_de_parada == "limite_alcanzado"


class TestManejoDeErrores:
    def test_error_de_autenticacion_se_traduce(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.side_effect = anthropic.AuthenticationError(
            "invalid x-api-key", response=_respuesta_http(401), body=None
        )

        with pytest.raises(LLMAuthError):
            provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

    def test_rate_limit_se_traduce(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.side_effect = anthropic.RateLimitError(
            "rate limited", response=_respuesta_http(429), body=None
        )

        with pytest.raises(LLMRateLimitError):
            provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

    def test_error_de_conexion_se_traduce(self):
        provider, cliente = _provider_con_cliente_falso()
        request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
        cliente.messages.create.side_effect = anthropic.APIConnectionError(request=request)

        with pytest.raises(LLMRequestError):
            provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])

    def test_otro_error_de_estado_se_traduce_a_request_error(self):
        provider, cliente = _provider_con_cliente_falso()
        cliente.messages.create.side_effect = anthropic.UnprocessableEntityError(
            "regla de negocio violada", response=_respuesta_http(422), body=None
        )

        with pytest.raises(LLMRequestError):
            provider.generar_respuesta(system="s", mensajes=[MensajeLLM(rol="user", texto="hola")], herramientas=[])
