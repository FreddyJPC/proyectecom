"""
Cuentas para transferir (pendiente #76): Victoria pregunta el banco, reconoce lo que el cliente escriba (con faltas), da la cuenta que
coincide y, si el banco no está entre los registrados, ofrece los que sí. El mensaje con los datos lo arma el código, nunca la IA.
Las cuentas de estas pruebas son ficticias.
"""
from decimal import Decimal

import pytest

from src.routes.whatsapp.cuentas import bancos_registrados, elegir_banco, nombre_corto, respuesta_para_victoria, texto_de_cuentas
from src.routes.whatsapp.tools import HerramientasVictoria, herramientas_de_victoria
from tests.unit.routes.whatsapp.test_tools import FakeLeadRepository, FakeProductoBotRepository, _herramientas
from tests.unit.routes.whatsapp.test_tools import LEAD_COMPLETO_CONTRAENTREGA


def _cuenta(banco, numero, tipo="Cuenta de ahorros", titular="Ana Prueba", identificacion="0900000000"):
    return {"banco": banco, "tipo_cuenta": tipo, "numero": numero, "titular": titular, "identificacion": identificacion}


CUENTAS = [
    _cuenta("Banco Pichincha", "1111111111", "Cuenta de ahorro transaccional"),
    _cuenta("Banco Guayaquil", "2222222222"),
    _cuenta("Produbanco", "3333333333", "Cuenta digital"),
    _cuenta("Cooperativa JEP", "4444444444", "AhorrosJEP"),
]


def _banco_de(dicho):
    return [c["banco"] for c in elegir_banco(dicho, CUENTAS).cuentas]


class TestReconocerElBanco:
    @pytest.mark.parametrize("dicho", ["Pichincha", "banco pichincha", "Banco del Pichincha", "Bano Pichncha", "el pichincha", "pichinca", "ptchincha", "pich", "BANCO PICHINCHA"])
    def test_pichincha_aunque_lo_escriban_mal(self, dicho):
        assert _banco_de(dicho) == ["Banco Pichincha"]

    @pytest.mark.parametrize("dicho", ["guayaquil", "Banco de Guayaquil", "bco guayaquil", "guayakil", "bancp guayaquil", "guay"])
    def test_guayaquil(self, dicho):
        assert _banco_de(dicho) == ["Banco Guayaquil"]

    @pytest.mark.parametrize("dicho", ["produbanco", "produ banco", "banco produbanco", "Prodobanco"])
    def test_produbanco(self, dicho):
        assert _banco_de(dicho) == ["Produbanco"]

    @pytest.mark.parametrize("dicho", ["jep", "la jep", "coop jep", "Cooperativa JEP", "Cooperativa de Ahorro y Credito JEP"])
    def test_cooperativa_jep(self, dicho):
        assert _banco_de(dicho) == ["Cooperativa JEP"]

    @pytest.mark.parametrize("dicho", ["rumiñahui", "banco rumiñahui", "Banco del Pacífico", "bolivariano", "internacional", "banco", "", None])
    def test_un_banco_que_no_tenemos_no_se_confunde_con_otro(self, dicho):
        assert _banco_de(dicho) == []

    def test_dos_cuentas_del_mismo_banco_se_dan_juntas(self):
        cuentas = [*CUENTAS, _cuenta("Banco Pichincha", "5555555555")]
        eleccion = elegir_banco("pichincha", cuentas)
        assert [c["numero"] for c in eleccion.cuentas] == ["1111111111", "5555555555"]

    def test_los_bancos_registrados_no_se_repiten(self):
        cuentas = [*CUENTAS, _cuenta("Banco Pichincha", "5555555555")]
        assert bancos_registrados(cuentas) == ["Banco Pichincha", "Banco Guayaquil", "Produbanco", "Cooperativa JEP"]

    def test_nombre_corto_quita_banco_y_cooperativa(self):
        assert nombre_corto("Banco del Pichincha") == "pichincha"
        assert nombre_corto("Cooperativa de Ahorro y Crédito JEP") == "jep"


class TestElTextoQueSeLeMandaAlCliente:
    def test_lleva_todos_los_datos_y_el_valor_a_transferir(self):
        texto = texto_de_cuentas([CUENTAS[0]], Decimal("24.99"))
        for esperado in ("Banco Pichincha", "Cuenta de ahorro transaccional", "1111111111", "Ana Prueba", "Cédula: 0900000000", "Valor a transferir: $24.99", "comprobante"):
            assert esperado in texto

    def test_sin_identificacion_no_se_inventa_la_linea_de_cedula(self):
        sin_cedula = {**CUENTAS[0], "identificacion": None}
        assert "Cédula" not in texto_de_cuentas([sin_cedula])

    def test_sin_total_no_se_menciona_un_valor(self):
        assert "Valor a transferir" not in texto_de_cuentas([CUENTAS[0]], None)


class TestLoQueRecibeVictoria:
    def test_sin_banco_primero_se_le_pregunta_al_cliente(self):
        r = respuesta_para_victoria(None, False, CUENTAS)
        assert "desde qué banco" in r and "1111111111" not in r

    def test_con_un_banco_nuestro_se_da_esa_cuenta_y_solo_esa(self):
        r = respuesta_para_victoria("Bano Pichncha", False, CUENTAS, Decimal("24.99"))
        assert "1111111111" in r and "2222222222" not in r and "$24.99" in r and "TAL CUAL" in r

    def test_un_banco_que_no_tenemos_ofrece_los_que_si_y_no_da_ninguna_cuenta(self):
        r = respuesta_para_victoria("tengo el banco rumiñahui", False, CUENTAS)
        assert "No tenemos cuenta" in r
        for banco in ("Banco Pichincha", "Banco Guayaquil", "Produbanco", "Cooperativa JEP"):
            assert banco in r
        assert not any(c["numero"] in r for c in CUENTAS)

    def test_cualquiera_da_la_cuenta_principal(self):
        r = respuesta_para_victoria(None, True, CUENTAS)
        assert "1111111111" in r and "2222222222" not in r

    def test_sin_cuentas_configuradas_se_escala(self):
        r = respuesta_para_victoria("pichincha", False, [])
        assert "escalar_a_humano" in r


class _Cuentas:
    def __init__(self, cuentas):
        self.cuentas = cuentas

    def listar(self, solo_activas=False):
        return [c for c in self.cuentas if not solo_activas or c.get("activa", True)]


def _con_cuentas(cuentas, producto=None, lead=None):
    producto = producto or {"sku": "DEMO-1", "nombre": "Producto Demo", "metodos_pago_aceptados": "contraentrega, transferencia", "envio_incluido": True}
    h = _herramientas(
        lead_repo=FakeLeadRepository(leads={1: {**LEAD_COMPLETO_CONTRAENTREGA, "metodo_pago": "transferencia", **(lead or {})}}),
        producto_repo=FakeProductoBotRepository(productos={"DEMO-1": producto}),
    )
    h._cuentas = _Cuentas(cuentas)
    return h


def _pedir(h, **entrada):
    return h.ejecutar("enviar_cuenta_para_transferir", lead_id=1, conversacion_id=1, entrada=entrada, id_llamada="x").contenido


class TestLaHerramienta:
    def test_esta_entre_las_que_se_le_ofrecen_a_victoria(self):
        assert "enviar_cuenta_para_transferir" in {h.nombre for h in herramientas_de_victoria(enviar_fotos=False)}

    def test_da_la_cuenta_del_banco_con_el_total_del_pedido(self):
        r = _pedir(_con_cuentas(CUENTAS), banco="pichncha")
        assert "1111111111" in r and "Valor a transferir: $24.99" in r

    def test_las_cuentas_apagadas_no_se_dan(self):
        cuentas = [{**CUENTAS[0], "activa": False}, CUENTAS[1]]
        r = _pedir(_con_cuentas(cuentas), banco="pichincha")
        assert "1111111111" not in r and "No tenemos cuenta" in r and "Banco Guayaquil" in r

    def test_un_producto_de_cierre_manual_no_da_cuentas(self):
        propio = {"sku": "DEMO-1", "nombre": "Propio", "metodos_pago_aceptados": "transferencia", "proveedor_cierre": "manual", "envio_incluido": True}
        r = _pedir(_con_cuentas(CUENTAS, producto=propio), banco="pichincha")
        assert "1111111111" not in r and "dueño" in r

    def test_un_producto_que_no_acepta_transferencia_no_da_cuentas(self):
        solo_contra = {"sku": "DEMO-1", "nombre": "Demo", "metodos_pago_aceptados": "contraentrega", "rocketfy_product_id": 9, "envio_incluido": True}
        r = _pedir(_con_cuentas(CUENTAS, producto=solo_contra), banco="pichincha")
        assert "1111111111" not in r and "no acepta" in r
