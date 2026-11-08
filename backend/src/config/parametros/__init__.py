"""
Parámetros del sistema controlados desde la app (ADR-011).

Uso desde cualquier módulo:

    from src.config.parametros import parametros
    limite = parametros.valor("bot.max_mensajes_historial")

Qué vale cada parámetro, de más fuerte a más débil: lo guardado desde la app, la
variable del servidor equivalente y el valor por defecto del catálogo.
"""
from .catalogo import (
    CATALOGO,
    GRUPOS,
    MODELO_POR_DEFECTO,
    Grupo,
    Opcion,
    Parametro,
    ParametroDesconocidoError,
    ValorInvalido,
    definicion,
)
from .servicio import ORIGEN_APP, ORIGEN_ORIGINAL, ORIGEN_SERVIDOR, ParametrosService, Resolucion

# Instancia única del proceso: la memoria de 30 s y los avisos de cambio se comparten.
parametros = ParametrosService()

__all__ = [
    "CATALOGO",
    "GRUPOS",
    "MODELO_POR_DEFECTO",
    "ORIGEN_APP",
    "ORIGEN_ORIGINAL",
    "ORIGEN_SERVIDOR",
    "Grupo",
    "Opcion",
    "Parametro",
    "ParametroDesconocidoError",
    "ParametrosService",
    "Resolucion",
    "ValorInvalido",
    "definicion",
    "parametros",
]
