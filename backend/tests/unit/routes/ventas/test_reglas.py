"""Reglas puras de cobrar y cancelar una venta (ADR-012): se prueban con diccionarios, sin base de datos."""
import pytest

from src.routes.ventas.reglas import (
    acciones_disponibles,
    motivo_para_no_cancelar,
    motivo_para_no_cobrar,
    motivo_para_no_deshacer_cobro,
)

AHORA = "2026-11-08T12:00:00"


def _venta(**cambios):
    venta = {"estado": "gestionada", "cobrada_en": None, "proveedor_cierre": "manual"}
    venta.update(cambios)
    return venta


class TestCobrar:
    @pytest.mark.parametrize("estado", ["por_gestionar", "gestionada"])
    def test_se_puede_cobrar_una_venta_propia_abierta(self, estado):
        assert motivo_para_no_cobrar(_venta(estado=estado)) is None

    def test_una_venta_de_rocketfy_no_se_cobra_aqui(self):
        assert "Rocketfy" in motivo_para_no_cobrar(_venta(proveedor_cierre="rocketfy", estado="despachada"))

    def test_una_venta_cancelada_no_se_cobra(self):
        assert "cancelada" in motivo_para_no_cobrar(_venta(estado="cancelada"))

    def test_no_se_cobra_dos_veces(self):
        assert "ya estaba marcada como cobrada" in motivo_para_no_cobrar(_venta(cobrada_en=AHORA))


class TestDeshacerCobro:
    def test_se_puede_si_estaba_cobrada(self):
        assert motivo_para_no_deshacer_cobro(_venta(cobrada_en=AHORA)) is None

    def test_no_si_no_estaba_cobrada(self):
        assert "no estaba marcada" in motivo_para_no_deshacer_cobro(_venta())

    def test_no_en_una_venta_de_rocketfy(self):
        assert motivo_para_no_deshacer_cobro(_venta(proveedor_cierre="rocketfy", cobrada_en=AHORA)) is not None


class TestCancelar:
    @pytest.mark.parametrize("estado", ["por_gestionar", "gestionada"])
    def test_se_puede_cancelar_una_venta_propia_abierta(self, estado):
        assert motivo_para_no_cancelar(_venta(estado=estado)) is None

    def test_una_venta_de_rocketfy_se_cancela_desde_su_pedido(self):
        assert "Rocketfy" in motivo_para_no_cancelar(_venta(proveedor_cierre="rocketfy", estado="despachada"))

    def test_no_se_cancela_dos_veces(self):
        assert "ya estaba cancelada" in motivo_para_no_cancelar(_venta(estado="cancelada"))

    def test_una_venta_cobrada_pide_deshacer_primero_el_cobro(self):
        motivo = motivo_para_no_cancelar(_venta(cobrada_en=AHORA))
        assert "deshaz primero el cobro" in motivo

    def test_un_estado_desconocido_no_se_cancela(self):
        assert "despachada" in motivo_para_no_cancelar(_venta(estado="despachada"))


class TestAccionesDisponibles:
    def test_venta_propia_abierta_sin_cobrar(self):
        assert acciones_disponibles(_venta()) == {"puede_cobrar": True, "puede_deshacer_cobro": False, "puede_cancelar": True}

    def test_venta_propia_cobrada_solo_deja_deshacer_el_cobro(self):
        assert acciones_disponibles(_venta(cobrada_en=AHORA)) == {
            "puede_cobrar": False, "puede_deshacer_cobro": True, "puede_cancelar": False,
        }

    def test_venta_cancelada_no_deja_nada(self):
        assert acciones_disponibles(_venta(estado="cancelada")) == {
            "puede_cobrar": False, "puede_deshacer_cobro": False, "puede_cancelar": False,
        }

    def test_venta_de_rocketfy_no_deja_nada(self):
        assert acciones_disponibles(_venta(proveedor_cierre="rocketfy", estado="despachada")) == {
            "puede_cobrar": False, "puede_deshacer_cobro": False, "puede_cancelar": False,
        }
