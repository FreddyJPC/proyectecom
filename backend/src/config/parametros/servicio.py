"""
Servicio de parámetros: decide qué valor vale para cada parámetro del catálogo y
permite cambiarlo desde la app.

Prioridad (ver catalogo.py): valor guardado en la app > variable del servidor > valor
por defecto del código. Por eso, mientras nadie guarde nada, el sistema se comporta
exactamente igual que antes de existir este módulo.

Por qué NO se consulta la base en cada acción
---------------------------------------------
Los valores guardados caben en una sola consulta (tabla pequeña) y se recuerdan en
memoria `ttl_segundos` (30 s). Guardar o restaurar un valor borra esa memoria al
instante, así que el cambio se nota en el siguiente uso. Producción corre con UN solo
worker de gunicorn (ver gunicorn.conf.py): una memoria por proceso basta; si algún día
hubiera varios, el vencimiento de 30 s acota cuánto tardaría un cambio en verse en
todos. La variable del servidor se lee de `os.environ` en cada uso (es gratis).

Nunca debe tumbar al bot
------------------------
Si la base falla al leer, se sigue con lo último que se leyó (o con nada: variable del
servidor y valor por defecto) y se reintenta en `reintento_segundos`. Un valor
guardado que ya no cumple las reglas del catálogo (alguien tocó la base a mano) se
ignora y se avisa una sola vez en el log.
"""
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

from .catalogo import CATALOGO, Parametro, ValorInvalido, definicion
from .repository import ParametrosRepository

logger = logging.getLogger(__name__)

ORIGEN_APP = "app"
ORIGEN_SERVIDOR = "servidor"
ORIGEN_ORIGINAL = "original"

TTL_SEGUNDOS = 30.0
REINTENTO_SEGUNDOS = 10.0


@dataclass(frozen=True)
class Resolucion:
    """Qué vale un parámetro y de dónde sale ese valor."""

    parametro: Parametro
    valor: Any
    origen: str
    # Lo que hay en cada nivel (None = no hay): sirve para mostrar «el servidor tiene X».
    valor_app: Optional[Any] = None
    valor_servidor: Optional[Any] = None
    actualizado_por: Optional[str] = None
    actualizado_en: Optional[datetime] = None
    avisos: Tuple[str, ...] = field(default_factory=tuple)


class ParametrosService:
    def __init__(
        self,
        repo=None,
        reloj: Callable[[], float] = time.monotonic,
        ttl_segundos: float = TTL_SEGUNDOS,
        reintento_segundos: float = REINTENTO_SEGUNDOS,
        entorno: Optional[Mapping[str, str]] = None,
    ):
        self._repo = repo or ParametrosRepository()
        self._reloj = reloj
        self._ttl = ttl_segundos
        self._reintento = reintento_segundos
        self._entorno = entorno
        self._lock = threading.Lock()
        self._filas: Optional[Dict[str, Dict[str, Any]]] = None
        self._vence = 0.0
        self._avisados: set = set()
        self._suscriptores: List[Tuple[str, Callable[[str], None]]] = []

    # ------------------------------------------------------------------
    # Lectura (lo que usa el resto del sistema)
    # ------------------------------------------------------------------
    def valor(self, clave: str) -> Any:
        """El valor vigente del parámetro. `ParametroDesconocidoError` si la clave no existe
        (es un error de programación: se quiere que falle fuerte en los tests)."""
        return self.resolver(clave).valor

    def resolver(self, clave: str) -> Resolucion:
        p = definicion(clave)
        fila = self._valores_guardados().get(clave)
        avisos: List[str] = []

        valor_app = None
        if fila is not None:
            try:
                valor_app = p.desde_texto(fila["valor"])
            except ValorInvalido as exc:
                avisos.append(f"El valor guardado en la app ya no es válido y se ignora ({exc}).")
                self._avisar_una_vez(("app", clave, fila["valor"]), "Parámetro '%s': el valor guardado %r no es válido (%s); se ignora", clave, fila["valor"], exc)

        valor_servidor = None
        if p.variable_servidor:
            texto = self._variables().get(p.variable_servidor)
            if texto is not None and texto.strip() != "":
                try:
                    valor_servidor = p.desde_texto(texto, del_servidor=True)
                except ValorInvalido as exc:
                    avisos.append(f"La variable {p.variable_servidor} del servidor tiene un valor no válido y se ignora ({exc}).")
                    self._avisar_una_vez(
                        ("servidor", clave, texto),
                        "Parámetro '%s': la variable %s del servidor vale %r y no es válida (%s); se ignora", clave, p.variable_servidor, texto, exc,
                    )

        if valor_app is not None:
            valor, origen = valor_app, ORIGEN_APP
        elif valor_servidor is not None:
            valor, origen = valor_servidor, ORIGEN_SERVIDOR
        else:
            valor, origen = p.defecto, ORIGEN_ORIGINAL

        return Resolucion(
            parametro=p,
            valor=valor,
            origen=origen,
            valor_app=valor_app,
            valor_servidor=valor_servidor,
            actualizado_por=fila["actualizado_por"] if fila is not None and valor_app is not None else None,
            actualizado_en=fila["actualizado_en"] if fila is not None and valor_app is not None else None,
            avisos=tuple(avisos),
        )

    def listar(self) -> List[Resolucion]:
        return [self.resolver(p.clave) for p in CATALOGO]

    def historial(self, limite: int = 50) -> List[Dict[str, Any]]:
        return self._repo.historial(limite)

    # ------------------------------------------------------------------
    # Escritura (la pantalla de Parámetros)
    # ------------------------------------------------------------------
    def guardar(self, clave: str, crudo: Any, usuario: Optional[str]) -> Resolucion:
        """Valida contra el catálogo y guarda. `ValorInvalido` si no cumple las reglas;
        nada se escribe en ese caso."""
        p = definicion(clave)
        valor = p.desde_json(crudo)
        cambio = self._repo.guardar(clave, p.a_texto(valor), usuario)
        self.invalidar()
        if cambio:
            self._notificar(clave)
        return self.resolver(clave)

    def restaurar(self, clave: str, usuario: Optional[str]) -> Resolucion:
        """Quita el valor guardado en la app: vuelve a valer el de la variable del servidor o,
        si no hay, el del código."""
        definicion(clave)
        cambio = self._repo.restaurar(clave, usuario)
        self.invalidar()
        if cambio:
            self._notificar(clave)
        return self.resolver(clave)

    def invalidar(self) -> None:
        """Olvida lo recordado: la próxima lectura vuelve a consultar la base."""
        with self._lock:
            self._filas = None
            self._vence = 0.0

    def suscribir(self, prefijo: str, callback: Callable[[str], None]) -> None:
        """`callback(clave)` se llama (en el hilo que guardó) cada vez que cambia un
        parámetro cuya clave empieza por `prefijo`. Lo usa el scheduler para
        reprogramar los intervalos en vivo. Suscribir dos veces lo mismo cuenta una sola vez."""
        if (prefijo, callback) not in self._suscriptores:
            self._suscriptores.append((prefijo, callback))

    # ------------------------------------------------------------------
    def _variables(self) -> Mapping[str, str]:
        return self._entorno if self._entorno is not None else os.environ

    def _valores_guardados(self) -> Dict[str, Dict[str, Any]]:
        ahora = self._reloj()
        with self._lock:
            if self._filas is not None and ahora < self._vence:
                return self._filas
            try:
                self._filas = self._repo.listar()
                self._vence = ahora + self._ttl
            except Exception:
                # Nunca tumbar al bot por esto: se sigue con lo último conocido (o con nada).
                logger.warning("No se pudieron leer los parámetros guardados; se usa lo último conocido", exc_info=True)
                if self._filas is None:
                    self._filas = {}
                self._vence = ahora + self._reintento
            return self._filas

    def _notificar(self, clave: str) -> None:
        for prefijo, callback in list(self._suscriptores):
            if clave.startswith(prefijo):
                try:
                    callback(clave)
                except Exception:
                    logger.exception("Falló un aviso de cambio del parámetro '%s'", clave)

    def _avisar_una_vez(self, marca: tuple, mensaje: str, *args) -> None:
        """Un valor inválido se pide en cada mensaje: se avisa una vez, no cien."""
        if marca not in self._avisados:
            self._avisados.add(marca)
            logger.warning(mensaje, *args)
