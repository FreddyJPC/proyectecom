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
    - system: un texto se pasa tal cual (sin caché). Una lista de BloqueSistema se manda como bloques de texto; si alguno
      pide caché, se activa el «caché de instrucciones» de Anthropic (prompt caching, entrada 0.0.161):
        * marca en la ÚLTIMA herramienta (las herramientas van primero y no cambian entre mensajes);
        * marca en el último bloque de system con cachear=True (la parte fija de las instrucciones + la ficha);
        * caché automático (`cache_control` de primer nivel) para la conversación, que se reaprovecha entre las
          vueltas de herramientas de un mismo mensaje.
      Lo leído de caché se cobra a una fracción del precio; el texto que ve el modelo es idéntico.

    - forzar_herramienta=<nombre> -> tool_choice {"type": "tool", "name": <nombre>}
      (sin forzar, NO se manda tool_choice: el modelo decide, como siempre)

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
import logging
from typing import List, Optional, Union

import anthropic

from src.integrations.llm.contratos import (
    BloqueSistema,
    HerramientaLLM,
    LlamadaHerramienta,
    LLMProvider,
    MensajeLLM,
    RespuestaLLM,
)
from src.integrations.llm.exceptions import LLMAuthError, LLMRateLimitError, LLMRequestError

logger = logging.getLogger(__name__)

_CACHE = {"type": "ephemeral"}  # 5 minutos (se renueva con cada lectura)

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
        system: Union[str, List[BloqueSistema]],
        mensajes: List[MensajeLLM],
        herramientas: List[HerramientaLLM],
        max_tokens: int = 1024,
        forzar_herramienta: Optional[str] = None,
    ) -> RespuestaLLM:
        cachear = isinstance(system, list) and any(b.cachear for b in system)
        parametros = dict(
            model=self._modelo,
            max_tokens=max_tokens,
            system=self._traducir_system(system),
            messages=self._traducir_mensajes(mensajes),
            tools=self._traducir_herramientas(herramientas, cachear),
        )
        if cachear:
            parametros["cache_control"] = _CACHE
        if forzar_herramienta is not None:
            if forzar_herramienta not in {h.nombre for h in herramientas}:
                raise ValueError(f"No se puede forzar la herramienta '{forzar_herramienta}': no está en la lista.")
            parametros["tool_choice"] = {"type": "tool", "name": forzar_herramienta}

        try:
            respuesta = self._client.messages.create(**parametros)
        except anthropic.AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except anthropic.RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMRequestError(str(exc)) from exc
        except anthropic.APIStatusError as exc:
            raise LLMRequestError(str(exc)) from exc

        traducida = self._traducir_respuesta(respuesta)
        traducida.uso = self._uso(respuesta)
        if traducida.uso:
            # Para medir el costo real por conversación desde los logs (Railway).
            logger.info("Uso de la IA: %s", traducida.uso)
        return traducida

    @staticmethod
    def _uso(respuesta) -> Optional[dict]:
        uso = getattr(respuesta, "usage", None)
        if uso is None:
            return None
        return {
            "entrada": getattr(uso, "input_tokens", 0) or 0,
            "escrito_en_cache": getattr(uso, "cache_creation_input_tokens", 0) or 0,
            "leido_de_cache": getattr(uso, "cache_read_input_tokens", 0) or 0,
            "salida": getattr(uso, "output_tokens", 0) or 0,
        }

    @staticmethod
    def _traducir_system(system: Union[str, List[BloqueSistema]]):
        if isinstance(system, str):
            return system
        bloques = [b for b in system if b.texto]
        # Máximo 4 marcas por llamada: 1 en herramientas, 1 automática para la conversación y 1 aquí (la del ÚLTIMO bloque
        # cacheable, que cubre todo lo anterior).
        ultimo = max((i for i, b in enumerate(bloques) if b.cachear), default=None)
        traducidos = []
        for i, b in enumerate(bloques):
            bloque = {"type": "text", "text": b.texto}
            if i == ultimo:
                bloque["cache_control"] = _CACHE
            traducidos.append(bloque)
        return traducidos

    @staticmethod
    def _traducir_herramientas(herramientas: List[HerramientaLLM], cachear: bool = False) -> list:
        traducidas = [
            {"name": h.nombre, "description": h.descripcion, "input_schema": h.parametros}
            for h in herramientas
        ]
        if cachear and traducidas:
            traducidas[-1] = {**traducidas[-1], "cache_control": _CACHE}
        return traducidas

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
            elif m.adjuntos:
                # Primero los archivos y después el texto (así lo recomienda Anthropic para imágenes y PDF).
                contenido = [
                    {"type": "image", "source": {"type": "base64", "media_type": a.mime, "data": a.datos_base64}}
                    if a.tipo == "imagen"
                    else {"type": "document", "source": {"type": "base64", "media_type": a.mime, "data": a.datos_base64}}
                    for a in m.adjuntos
                ]
                contenido.append({"type": "text", "text": m.texto or "(el cliente envió el archivo sin texto)"})
                traducidos.append({"role": m.rol, "content": contenido})
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
