"""
Las instrucciones de Victoria (su «system prompt») y cómo se editan desde la app
(ADR-011, docs/PLAN_PARAMETRIZACION.md, fase P3).

El texto ORIGINAL vive en `victoria_system_prompt.txt` (en el código: pasa por revisión
y por los tests). Desde la app se puede publicar una versión propia de las secciones
EDITABLES; el resto del texto está atado al código y no se edita:

  editables  : quién es Victoria, personalidad, objetivo, reglas que nunca rompe y variantes.
  bloqueadas : la ficha del producto, cómo usar las herramientas (nombres de herramientas y
               flujo de cierre de venta, que son código), lo que ya se sabe del cliente y la fecha.

Qué protege esta estructura (los riesgos que se analizaron antes de aprobar la edición):
  - El prompt final se arma con `str.format`: una `{` o `}` suelta dejaría muda a Victoria con
    TODOS los clientes. Por eso las llaves del texto editable se escapan al ensamblar: no pueden
    romper nada (y los huecos del sistema viven en secciones bloqueadas, que nadie puede borrar).
  - Si la lectura o la validación de la versión publicada fallan en producción, Victoria usa el
    archivo del código: NUNCA se queda sin instrucciones.
  - Todo el texto viaja en cada mensaje: hay un largo máximo por sección y total.

Lo que NO cambia: el dinero, el stock, la cantidad y la pausa de productos los decide el código
(ADR-010); un prompt peor puede empeorar el trato, pero no puede saltarse esas reglas.
"""
import logging
import math
import re
import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional

logger = logging.getLogger(__name__)

RUTA_ORIGINAL = Path(__file__).resolve().parent / "victoria_system_prompt.txt"

# Largo máximo del prompt completo ya armado (el original son unos 3.600 caracteres).
MAXIMO_TOTAL = 8000
# Clave de los errores que no son de una sección en particular.
GENERAL = "_general"

# Huecos que el sistema rellena en cada mensaje (ver conversation_service.procesar_turno).
HUECOS = ("contexto_producto", "contexto_lead_actual", "fecha_actual")


@dataclass(frozen=True)
class Seccion:
    id: str
    # Título tal como está en el archivo (sin los «## »); None = el texto del principio, sin título.
    titulo: Optional[str]
    nombre: str
    ayuda: str
    editable: bool
    maximo: int = 0


SECCIONES = (
    Seccion(
        "intro", None, "Quién es Victoria",
        "La primera frase: presenta el rol de Victoria y de qué tienda es.", True, 500,
    ),
    Seccion(
        "personalidad", "Tu personalidad", "Personalidad y tono",
        "Cómo habla Victoria: tono, largo de los mensajes, uso de emojis y qué dice si le preguntan si es un bot.", True, 2000,
    ),
    Seccion(
        "objetivo", "Tu objetivo", "Objetivo y proceso de venta",
        "Qué busca Victoria y los pasos naturales de una venta, de saludar a confirmar el pedido.", True, 1500,
    ),
    Seccion(
        "producto", "Información del producto de esta conversación", "Información del producto",
        "El sistema escribe aquí, en cada mensaje, la ficha del producto del que se habla (precio, entrega, preguntas "
        "frecuentes…). Es lo que sale de tu Catálogo; no se edita aquí.", False,
    ),
    Seccion(
        "reglas", "Reglas que nunca rompes", "Reglas que nunca rompe",
        "Lo que Victoria no debe hacer jamás: inventar datos, ofrecer descuentos, prometer plazos distintos, resolver "
        "devoluciones… y cuándo pasar a una persona.", True, 4000,
    ),
    Seccion(
        "herramientas", "Cómo usar tus herramientas", "Cómo usa sus herramientas",
        "Está atada al código: nombra las herramientas reales de Victoria y el flujo de cierre de una venta (el total lo "
        "calcula el sistema, no ella). Cambiarla sin cambiar el código haría que Victoria se confunda, por eso aquí solo se lee.",
        False,
    ),
    Seccion(
        "variantes", "Sobre variantes (color, talla, etc.)", "Variantes",
        "Qué hace Victoria cuando el producto tiene colores, tallas u otras variantes.", True, 2000,
    ),
    Seccion(
        "clasificacion", "Cómo clasificas a cada cliente", "Cómo clasifica a cada cliente",
        "Qué significa caliente, tibio, frío y perdido para Victoria, y cómo trata a un cliente que ya compró o ya había hablado "
        "con la tienda. Su juicio queda en el panel de Leads para que sepas a quién atender primero.", True, 2500,
    ),
    Seccion(
        "estado", "Estado actual de este lead (lo que ya se sabe de este cliente)", "Lo que ya se sabe del cliente",
        "El sistema escribe aquí, en cada mensaje, los datos que ya se guardaron del cliente y los que faltan. No se edita.", False,
    ),
    Seccion(
        "fecha", "Fecha de hoy", "Fecha de hoy",
        "El sistema escribe aquí la fecha de hoy (hora de Ecuador). No se edita.", False,
    ),
)

EDITABLES = tuple(s for s in SECCIONES if s.editable)
_POR_ID = {s.id: s for s in SECCIONES}


class InstruccionesInvalidas(ValueError):
    """Las secciones no cumplen las reglas. `errores`: {id de la sección o «_general»: [mensajes]}."""

    def __init__(self, errores: Dict[str, List[str]]):
        super().__init__("; ".join(m for mensajes in errores.values() for m in mensajes))
        self.errores = errores


class SinBorradorError(Exception):
    """Se pidió algo que necesita un borrador (publicarlo, probarlo) y no hay ninguno."""


class ArchivoOriginalInvalido(RuntimeError):
    """El archivo del código no tiene las secciones que `SECCIONES` espera (se detecta en los tests)."""


# ----------------------------------------------------------------------------
# El archivo original, partido en secciones
# ----------------------------------------------------------------------------
@lru_cache(maxsize=1)
def texto_original() -> str:
    return RUTA_ORIGINAL.read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _trozos() -> Dict[str, str]:
    """Cada sección tal como está en el archivo, con su título y sus saltos de línea, de modo que
    unir los trozos en orden devuelve el archivo idéntico."""
    trozos = re.split(r"(?m)^(?=## )", texto_original())
    if len(trozos) != len(SECCIONES):
        raise ArchivoOriginalInvalido(f"El prompt original tiene {len(trozos)} secciones y se esperaban {len(SECCIONES)}.")
    for seccion, trozo in zip(SECCIONES, trozos):
        if seccion.titulo is not None and not trozo.startswith(f"## {seccion.titulo}\n"):
            raise ArchivoOriginalInvalido(f"Se esperaba la sección «{seccion.titulo}» y el archivo trae otra.")
    return {s.id: t for s, t in zip(SECCIONES, trozos)}


def _cuerpo_de(seccion: Seccion, trozo: str) -> str:
    """El texto de la sección sin su título ni los saltos de línea de los bordes."""
    if seccion.titulo is not None:
        trozo = trozo[len(f"## {seccion.titulo}\n"):]
    return trozo.strip()


def secciones_originales() -> Dict[str, str]:
    """El texto original de cada sección EDITABLE (id -> cuerpo)."""
    trozos = _trozos()
    return {s.id: _cuerpo_de(s, trozos[s.id]) for s in EDITABLES}


def cuerpo_fijo(id_seccion: str) -> str:
    """El texto de una sección bloqueada, tal como está en el código."""
    seccion = _POR_ID[id_seccion]
    return _cuerpo_de(seccion, _trozos()[id_seccion])


# ----------------------------------------------------------------------------
# Ensamblar y validar
# ----------------------------------------------------------------------------
def _escapar(texto: str) -> str:
    """Las llaves del texto escrito por una persona no son huecos del sistema: se escapan para
    que `str.format` las deje tal cual y no pueda fallar por ellas."""
    return texto.replace("{", "{{").replace("}", "}}")


def ensamblar(secciones: Optional[Mapping[str, str]] = None) -> str:
    """El prompt completo, con los huecos `{contexto_producto}`… todavía sin rellenar, listo para
    `.format(...)`. Las secciones editables que no vengan en `secciones` quedan como en el original."""
    secciones = secciones or {}
    partes = []
    for seccion in SECCIONES:
        trozo = _trozos()[seccion.id]
        if not seccion.editable or seccion.id not in secciones:
            partes.append(trozo)
            continue
        cola = trozo[len(trozo.rstrip()):]  # los saltos de línea con que terminaba, para conservar el formato
        titulo = f"## {seccion.titulo}\n" if seccion.titulo is not None else ""
        partes.append(f"{titulo}{_escapar(str(secciones[seccion.id]).strip())}{cola}")
    return "".join(partes)


def validar(secciones: Any) -> Dict[str, str]:
    """Comprueba las secciones editables y las devuelve limpias (con los espacios de los bordes
    recortados). Deben venir TODAS las editables y ninguna otra. `InstruccionesInvalidas` si no cumplen."""
    errores: Dict[str, List[str]] = {}

    def anotar(clave: str, mensaje: str) -> None:
        errores.setdefault(clave, []).append(mensaje)

    if not isinstance(secciones, Mapping):
        raise InstruccionesInvalidas({GENERAL: ["Las instrucciones deben venir como un conjunto de secciones."]})

    for clave in secciones:
        if clave not in {s.id for s in EDITABLES}:
            anotar(GENERAL, f"La sección «{clave}» no existe o no se puede editar.")

    limpias: Dict[str, str] = {}
    for seccion in EDITABLES:
        if seccion.id not in secciones:
            anotar(seccion.id, "Falta esta sección.")
            continue
        crudo = secciones[seccion.id]
        if not isinstance(crudo, str):
            anotar(seccion.id, "Debe ser un texto.")
            continue
        texto = crudo.strip()
        if not texto:
            anotar(seccion.id, "No puede quedar vacía.")
        if len(texto) > seccion.maximo:
            anotar(seccion.id, f"Es demasiado larga: máximo {seccion.maximo} caracteres (tiene {len(texto)}).")
        if re.search(r"(?m)^#{1,6}\s", texto):
            anotar(seccion.id, "No uses títulos con «#»: los títulos de cada sección los pone el sistema.")
        if "\x00" in texto:
            anotar(seccion.id, "Contiene caracteres no permitidos.")
        limpias[seccion.id] = texto

    if not errores:
        total = ensamblar(limpias)
        if len(total) > MAXIMO_TOTAL:
            anotar(GENERAL, f"Las instrucciones completas miden {len(total)} caracteres y el máximo es {MAXIMO_TOTAL}: se envían en cada mensaje.")
        else:
            try:
                total.format(**{h: "" for h in HUECOS})
            except (KeyError, IndexError, ValueError) as exc:  # red de seguridad: por construcción no debería pasar
                anotar(GENERAL, f"No se pudo armar el texto final ({exc}).")

    if errores:
        raise InstruccionesInvalidas(errores)
    return limpias


def estimar_tokens(texto: str) -> int:
    """Estimación gruesa (≈ 4 caracteres por token) para que se vea cuánto pesa."""
    return math.ceil(len(texto) / 4)


def caracteres_fijos() -> int:
    """Largo de todo lo que no se edita (títulos, secciones bloqueadas y los saltos de línea):
    sumado a lo que se escriba en las editables da el largo total aproximado."""
    return len(ensamblar({s.id: "" for s in EDITABLES}))


# ----------------------------------------------------------------------------
# Lo que usa Victoria en cada mensaje
# ----------------------------------------------------------------------------
class InstruccionesVigentes:
    """La plantilla del prompt que rige HOY: la versión publicada desde la app o, si no hay (o algo
    falla), el archivo original. Se recuerda 30 s en memoria y se olvida al publicar o volver a la
    original, igual que los parámetros (ver src/config/parametros/servicio.py)."""

    def __init__(
        self,
        repo=None,
        reloj: Callable[[], float] = time.monotonic,
        ttl_segundos: float = 30.0,
        reintento_segundos: float = 10.0,
    ):
        self._repo = repo
        self._reloj = reloj
        self._ttl = ttl_segundos
        self._reintento = reintento_segundos
        self._lock = threading.Lock()
        self._texto: Optional[str] = None
        self._vence = 0.0

    def plantilla(self) -> str:
        ahora = self._reloj()
        with self._lock:
            if self._texto is not None and ahora < self._vence:
                return self._texto
            try:
                publicada = self._repositorio().publicada()
                self._texto = ensamblar(validar(publicada["secciones"])) if publicada else texto_original()
                self._vence = ahora + self._ttl
            except Exception:
                # Nunca dejar a Victoria sin instrucciones: lo último que funcionó, o el archivo del código.
                logger.exception("No se pudo leer la versión publicada de las instrucciones; se usa la última conocida o la original")
                if self._texto is None:
                    self._texto = texto_original()
                self._vence = ahora + self._reintento
            return self._texto

    def invalidar(self) -> None:
        with self._lock:
            self._texto = None
            self._vence = 0.0

    def _repositorio(self):
        if self._repo is None:
            from .instrucciones_repository import InstruccionesRepository

            self._repo = InstruccionesRepository()
        return self._repo


# Instancia única del proceso (la memoria de 30 s se comparte).
instrucciones_vigentes = InstruccionesVigentes()
