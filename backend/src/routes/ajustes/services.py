"""
Ajustes del negocio para calcular precios (Fase C). Una sola fila; el dueño la
edita desde el dashboard. `obtener_ajustes()` es lo que usan otros módulos
(la calculadora de productos) para leer los números como un objeto de dominio.
"""
from decimal import Decimal
from typing import Any, Dict, Optional

from .calibracion import calibrar_envio
from .dto import AjustesNegocio, AjustesRespuestaDTO
from .repository import AjustesNegocioRepository


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


def _a_dominio(fila: Dict[str, Any]) -> AjustesNegocio:
    return AjustesNegocio(
        margen_minimo_pct=Decimal(str(fila["margen_minimo_pct"])),
        margen_objetivo_pct=Decimal(str(fila["margen_objetivo_pct"])),
        envio_estimado=Decimal(str(fila["envio_estimado"])),
        otros_costos_fijos=Decimal(str(fila["otros_costos_fijos"])),
        otros_costos_pct=Decimal(str(fila["otros_costos_pct"])),
        redondeo=fila["redondeo"],
        tope_redacciones_dia=int(fila["tope_redacciones_dia"]),
        confirmado=fila.get("confirmado_en") is not None,
        actualizado_por=fila.get("actualizado_por"),
        actualizado_en=_iso(fila.get("actualizado_en")),
    )


class AjustesService:
    def __init__(self, repo=None):
        self._repo = repo or AjustesNegocioRepository()

    def obtener_ajustes(self) -> AjustesNegocio:
        return _a_dominio(self._repo.obtener())

    def obtener(self) -> AjustesRespuestaDTO:
        return self._a_respuesta(_a_dominio(self._repo.obtener()))

    def guardar(self, datos: Dict[str, Any], usuario: Optional[str]) -> AjustesRespuestaDTO:
        return self._a_respuesta(_a_dominio(self._repo.guardar(datos, usuario)))

    def _a_respuesta(self, a: AjustesNegocio) -> AjustesRespuestaDTO:
        return AjustesRespuestaDTO(
            margen_minimo_pct=f"{a.margen_minimo_pct:.2f}",
            margen_objetivo_pct=f"{a.margen_objetivo_pct:.2f}",
            envio_estimado=f"{a.envio_estimado:.2f}",
            otros_costos_fijos=f"{a.otros_costos_fijos:.2f}",
            otros_costos_pct=f"{a.otros_costos_pct:.2f}",
            redondeo=a.redondeo,
            tope_redacciones_dia=a.tope_redacciones_dia,
            confirmado=a.confirmado,
            actualizado_por=a.actualizado_por,
            actualizado_en=a.actualizado_en,
            calibracion_envio=calibrar_envio(self._repo.listar_minimos_con_costo()),
        )
