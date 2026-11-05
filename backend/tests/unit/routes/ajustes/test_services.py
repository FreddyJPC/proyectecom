"""Servicio de ajustes con un repositorio en memoria: sin base de datos."""
from datetime import datetime, timezone
from decimal import Decimal

from src.routes.ajustes.services import AjustesService

AHORA = datetime(2026, 11, 5, 22, 0, tzinfo=timezone.utc)


def _fila(**cambios):
    fila = {
        "margen_minimo_pct": Decimal("25.00"),
        "margen_objetivo_pct": Decimal("35.00"),
        "envio_estimado": Decimal("5.00"),
        "otros_costos_fijos": Decimal("0.00"),
        "otros_costos_pct": Decimal("0.00"),
        "redondeo": "terminado_99",
        "confirmado_en": None,
        "actualizado_por": None,
        "actualizado_en": AHORA,
    }
    fila.update(cambios)
    return fila


class RepoEnMemoria:
    def __init__(self, fila=None, minimos=()):
        self.fila = fila or _fila()
        self.minimos = list(minimos)
        self.guardados = []

    def obtener(self):
        return dict(self.fila)

    def guardar(self, datos, usuario):
        self.guardados.append((datos, usuario))
        self.fila.update(datos, actualizado_por=usuario, confirmado_en=self.fila["confirmado_en"] or AHORA)
        return dict(self.fila)

    def listar_minimos_con_costo(self, limite=100):
        return self.minimos


def test_los_valores_de_partida_salen_sin_confirmar():
    r = AjustesService(RepoEnMemoria()).obtener()
    assert (r.margen_minimo_pct, r.margen_objetivo_pct, r.envio_estimado) == ("25.00", "35.00", "5.00")
    assert (r.otros_costos_fijos, r.otros_costos_pct, r.redondeo) == ("0.00", "0.00", "terminado_99")
    assert r.confirmado is False and r.calibracion_envio is None


def test_guardar_los_deja_confirmados_y_registra_quien():
    repo = RepoEnMemoria()
    datos = {
        "margen_minimo_pct": Decimal("30.00"), "margen_objetivo_pct": Decimal("40.00"), "envio_estimado": Decimal("6.50"),
        "otros_costos_fijos": Decimal("1.00"), "otros_costos_pct": Decimal("3.00"), "redondeo": "ninguno",
    }

    r = AjustesService(repo).guardar(datos, "freddy@ejemplo.com")

    assert repo.guardados == [(datos, "freddy@ejemplo.com")]
    assert r.confirmado is True and r.actualizado_por == "freddy@ejemplo.com"
    assert (r.margen_minimo_pct, r.envio_estimado, r.otros_costos_pct, r.redondeo) == ("30.00", "6.50", "3.00", "ninguno")


def test_el_objeto_de_dominio_usa_decimal_y_refleja_si_esta_confirmado():
    sin = AjustesService(RepoEnMemoria()).obtener_ajustes()
    con = AjustesService(RepoEnMemoria(_fila(confirmado_en=AHORA))).obtener_ajustes()
    assert isinstance(sin.envio_estimado, Decimal) and isinstance(sin.margen_minimo_pct, Decimal)
    assert (sin.confirmado, con.confirmado) == (False, True)


def test_incluye_la_calibracion_del_envio_si_hay_observaciones():
    minimos = [{"sku": "X", "cantidad": 1, "minimo": Decimal("18.47"), "costo_rocketfy": Decimal("10.00"), "creado_en": AHORA}]
    r = AjustesService(RepoEnMemoria(minimos=minimos)).obtener()
    assert (r.calibracion_envio.observaciones, r.calibracion_envio.mediana) == (1, "8.47")
