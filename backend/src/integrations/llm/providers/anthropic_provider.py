"""
AnthropicProvider implementa LLMProvider. Este es el ÚNICO archivo del
proyecto que debe importar el paquete `anthropic` o referenciar alguno de
sus tipos -- toda la traducción entre los tipos neutrales de contratos.py
y el formato de wire real de Anthropic vive acá adentro. Si en algún otro
archivo aparece `import anthropic`, algo se filtró (ver el test de
contención en tests/unit/integrations/llm/).

Traducción de entrada (neutral -> Anthropic):
    - HerramientaLLM -> {"name", "description", "input_schema"}
    - MensajeLLM con resultados_herramientas -> mensaje "user" con bloques
      "tool_result" (turno de vuelta de una herramienta)
    - MensajeLLM con llamadas_herramientas -> mensaje "assistant" con
      bloques "text" (si había) + "tool_use" reconstruidos
    - MensajeLLM de texto simple -> {"role", "content": texto}
    - system se pasa tal cual al parámetro `system` de la API

Traducción de salida (Anthropic -> neutral):
    - Bloques "text" concatenados -> RespuestaLLM.texto
    - Bloques "tool_use" -> LlamadaHerramienta(id, nombre, entrada)
    - stop_reason "tool_use" -> "necesita_herramientas"
    - stop_reason "end_turn" (o cualquier otro no reconocido) -> "fin"
    - stop_reason "max_tokens" -> "limite_alcanzado"

Manejo de errores: AuthenticationError/RateLimitError/APIConnectionError
se traducen a sus equivalentes neutrales; cualquier otro APIStatusError
(400, 403, 404, 409, 422, 5xx...) se trata como LLMRequestError -- ver
tools.py/services.py para dónde importa la distinción real (no acá).
"""
from typing import List

import anthropic

from src.integrations.llm.contratos import (
    HerramientaLLM,
    LlamadaHerramienta,
    LLMProvider,
    MensajeLLM,
    RespuestaLLM,
)
from src.integrations.llm.exceptions import LLMAuthError, LLMRateLimitError, LLMRequestError

_RAZONES_DE_PARADA = {
    "tool_use": "necesita_herramientas",
    "max_tokens": "limite_alcanzado",
}


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str, modelo: str):
        # Recibe api_key/modelo ya resueltos desde settings (ver
        # factory.py) -- no lee variables de entorno acá, para que sea
        # fácil de instanciar en tests con valores de prueba.
        self._client = anthropic.Anthropic(api_key=api_key)
        self._modelo = modelo

    def generar_respuesta(
        self,
        system: str,
        mensajes: List[MensajeLLM],
        herramientas: List[HerramientaLLM],
        max_tokens: int = 1024,
    ) -> RespuestaLLM:
        try:
            respuesta = self._client.messages.create(
                model=self._modelo,
                max_tokens=max_tokens,
                system=system,
                messages=self._traducir_mensajes(mensajes),
                tools=self._traducir_herramientas(herramientas),
            )
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMRequestError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise LLMRequestError(str(exc)) from exc

        return self._traducir_respuesta(respuesta)

    @staticmethod
    def _traducir_herramientas(herramientas: List[HerramientaLLM]) -> list:
        return [
            {"name": h.nombre, "description": h.descripcion, "input_schema": h.parametros}
            for h in herramientas
        ]

    @staticmethod
    def _traducir_mensajes(mensajes: List[MensajeLLM]) -> list:
        traducidos = []
        for m in mensajes:
            if m.resultados_herramientas:
                traducidos.append({
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "tool_use_id": r.id_llamada, "content": r.contenido}
                        for r in m.resultados_herramientas
                    ],
                })
            elif m.llamadas_herramientas:
                contenido = []
                if m.texto:
                    contenido.append({"type": "text", "text": m.texto})
                for llamada in m.llamadas_herramientas:
                    contenido.append({
                        "type": "tool_use",
                        "id": llamada.id,
                        "name": llamada.nombre,
                        "input": llamada.entrada,
                    })
                traducidos.append({"role": "assistant", "content": contenido})
            else:
                traducidos.append({"role": m.rol, "content": m.texto or ""})
        return traducidos

    @staticmethod
    def _traducir_respuesta(mensaje) -> RespuestaLLM:
        texto = ""
        llamadas = []
        for bloque in mensaje.content:
            if bloque.type == "text":
                texto += bloque.text
            elif bloque.type == "tool_use":
                llamadas.append(LlamadaHerramienta(id=bloque.id, nombre=bloque.name, entrada=bloque.input))

        razon = _RAZONES_DE_PARADA.get(mensaje.stop_reason, "fin")
        return RespuestaLLM(texto=texto, llamadas_herramientas=llamadas, razon_de_parada=razon)
