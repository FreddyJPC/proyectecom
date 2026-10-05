"""
Tipos neutrales del cerebro conversacional de Victoria y la interfaz que
cualquier proveedor de LLM debe cumplir.

Nada en este archivo conoce el SDK de un proveedor concreto -- ese es
justo el punto de esta capa: VictoriaConversationService, tools.py, y sus
tests solo conocen estos tipos y LLMProvider. La traducción hacia/desde
el formato de wire real de cada proveedor vive exclusivamente en su
adapter bajo providers/ (ver providers/anthropic_provider.py).

Nota de compatibilidad: se usa `Optional[X]` (no `X | None`) porque este
proyecto corre en Python 3.9 -- el operador `|` para anotaciones de tipo
recién existe desde 3.10 (PEP 604) y rompería en tiempo de import acá.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Literal, Optional


@dataclass
class HerramientaLLM:
    """Definición de una herramienta que el LLM puede invocar.
    `parametros` es JSON Schema estándar -- este formato ya es compartido
    entre proveedores, así que se define una sola vez acá. Cada adapter
    lo traduce a su propio formato de wire (Anthropic lo llama
    "input_schema", OpenAI lo envuelve distinto, etc.) -- pero quien
    define la herramienta (tools.py) nunca necesita saberlo."""

    nombre: str
    descripcion: str
    parametros: dict


@dataclass
class LlamadaHerramienta:
    """El LLM pidió ejecutar una herramienta con estos argumentos."""

    id: str
    nombre: str
    entrada: dict


@dataclass
class ResultadoHerramienta:
    """El resultado de haber ejecutado una LlamadaHerramienta, para
    devolverle al LLM en el siguiente turno."""

    id_llamada: str
    contenido: str


@dataclass
class MensajeLLM:
    """Un turno de la conversación, en formato neutral. Por construcción
    (ver VictoriaConversationService) es siempre una de tres formas:
    texto de usuario, texto+llamadas de un turno del asistente, o
    resultados de herramienta como turno de usuario -- nunca una mezcla."""

    rol: Literal["user", "assistant"]
    texto: Optional[str] = None
    llamadas_herramientas: List[LlamadaHerramienta] = field(default_factory=list)
    resultados_herramientas: List[ResultadoHerramienta] = field(default_factory=list)


@dataclass
class RespuestaLLM:
    """Lo que devuelve el proveedor tras un turno."""

    texto: str
    llamadas_herramientas: List[LlamadaHerramienta]
    razon_de_parada: Literal["fin", "necesita_herramientas", "limite_alcanzado"]


class LLMProvider(ABC):
    """Contrato que cualquier proveedor de LLM debe cumplir. El servicio
    de conversación (VictoriaConversationService) SOLO conoce esta
    interfaz -- nunca un SDK concreto. Agregar un proveedor nuevo es
    escribir una clase que implemente esto en providers/, y sumar una
    rama en factory.py -- nada más del proyecto cambia."""

    @abstractmethod
    def generar_respuesta(
        self,
        system: str,
        mensajes: List[MensajeLLM],
        herramientas: List[HerramientaLLM],
        max_tokens: int = 1024,
    ) -> RespuestaLLM:
        ...
