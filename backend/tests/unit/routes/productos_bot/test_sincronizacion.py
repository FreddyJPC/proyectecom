"""
Operación continua (Fase F): sincronización de productos publicados, auto-pausa
por agotado y alerta de margen en riesgo. Con repositorios en memoria, un
Rocketfy y un Telegram falsos: sin base de datos ni red.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.integrations.rocketfy import RocketfyRequestError
from src.routes.ajustes.dto import AjustesNegocio
from src.routes.productos_bot.services import ProductosBotService
from src.routes.productos_bot.sincronizacion import (
    JOB_NAME,
    TIPO_ALERTA_AGOTADO,
    TIPO_ALERTA_MARGEN,
    SincronizacionProductosService,
)
from tests.unit.routes.productos_bot.test_services import AjustesFalsos, MonitoreoFalso, RepoEnMemoria, _fila


class RocketfyPorSku:
    """Catálogo falso: un producto por SKU, y SKUs que fallan o no existen."""

    def __init__(self, productos, fallan=()):
        self.productos = {p["sku"]: p for p in productos}
        self.fallan = set(fallan)
        self.consultas = []

    def listar_productos(self, q=None, page=1):
        self.consultas.append(q)
        if q in self.fallan:
            raise RocketfyRequestError("sin red")
        return {"data": [self.productos[q]] if q in self.productos else []}


def en_rocketfy(sku="DEMO-1", stock=50, costo="10.00", sugerido="29.90"):
    return {"id": 4821, "sku": sku, "name": "Reloj", "stock": stock, "price": costo, "suggested_price": sugerido, "weight": "0.35", "image_url": None}


class AlertasFalsas:
    def __init__(self, falla=False):
        self.alertas = []
        self.falla = falla

    def guardar_alerta(self, sku, tipo, detalle):
        if self.falla:
            raise RuntimeError("base caída")
        self.alertas.append((sku, tipo, detalle))


class TelegramFalso:
    def __init__(self, falla=False):
        self.avisos = []
        self.falla = falla

    def notificar_aviso(self, titulo, detalle):
        if self.falla:
            raise RuntimeError("telegram caído")
        self.avisos.append((titulo, detalle))


def armar(filas, catalogo, ajustes=None, alertas=None, telegram=None, monitoreo=None):
    repo = RepoEnMemoria(filas)
    rocketfy = catalogo
    productos = ProductosBotService(client=rocketfy, repo=repo, monitoreo_repo=MonitoreoFalso(), ajustes_service=AjustesFalsos())
    alertas = alertas or AlertasFalsas()
    telegram = telegram or TelegramFalso()
    monitoreo = monitoreo or MonitoreoFalso(vigilados=[f["sku"] for f in filas])
    servicio = SincronizacionProductosService(
        productos=productos, repo=repo, alertas=alertas, monitoreo=monitoreo,
        ajustes_service=ajustes or AjustesFalsos(confirmado=True), telegram=telegram,
    )
    return servicio, repo, alertas, telegram, monitoreo


def activo(**cambios):
    datos = dict(estado="activo", activo=True, precio=Decimal("34.90"), costo_rocketfy=Decimal("10.00"), stock_ultimo=50)
    datos.update(cambios)
    return _fila(**datos)


class TestSincronizar:
    def test_refresca_costo_precio_sugerido_y_stock(self):
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=7, costo="12.50", sugerido="31.00")]))
        r = s.sincronizar_todos()
        fila = repo.filas["DEMO-1"]
        assert (fila["costo_rocketfy"], fila["precio_sugerido_rocketfy"], fila["stock_ultimo"]) == (Decimal("12.50"), Decimal("31.00"), 7)
        assert (r.revisados, r.actualizados, r.fallidos) == (1, 1, 0)

    def test_si_cambio_el_costo_queda_en_el_historial_como_del_sistema(self):
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="11.00")]))
        s.sincronizar_todos()
        h = [x for x in repo.historial if x["accion"] == "actualizado_rocketfy"]
        assert len(h) == 1 and h[0]["usuario"] is None
        assert h[0]["cambios"]["costo_rocketfy"] == ["10.00", "11.00"]

    def test_sin_cambios_no_llena_el_historial(self):
        s, repo, _, _, _ = armar([activo(precio_sugerido_rocketfy=Decimal("29.90"))], RocketfyPorSku([en_rocketfy()]))
        s.sincronizar_todos()
        assert repo.historial == []

    @pytest.mark.parametrize("estado", ["borrador", "listo", "pausado", "archivado"])
    def test_solo_sincroniza_activos_y_agotados(self, estado):
        catalogo = RocketfyPorSku([en_rocketfy()])
        s, _, _, _, _ = armar([_fila(estado=estado, activo=False)], catalogo)
        r = s.sincronizar_todos()
        assert r.revisados == 0 and catalogo.consultas == []

    def test_un_agotado_si_se_sincroniza_pero_no_se_reanuda_solo(self):
        s, repo, alertas, telegram, _ = armar([_fila(estado="agotado", activo=False, stock_ultimo=0)], RocketfyPorSku([en_rocketfy(stock=40)]))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["stock_ultimo"] == 40
        assert repo.filas["DEMO-1"]["estado"] == "agotado" and repo.filas["DEMO-1"]["activo"] is False
        assert alertas.alertas == [] and telegram.avisos == []

    def test_si_rocketfy_falla_con_uno_sigue_con_los_demas(self):
        filas = [activo(), activo(sku="DEMO-2")]
        catalogo = RocketfyPorSku([en_rocketfy("DEMO-2", stock=9)], fallan=["DEMO-1"])
        s, repo, _, _, _ = armar(filas, catalogo)
        r = s.sincronizar_todos()
        assert (r.revisados, r.actualizados, r.fallidos) == (2, 1, 1)
        assert repo.filas["DEMO-2"]["stock_ultimo"] == 9
        assert repo.filas["DEMO-1"]["stock_ultimo"] == 50  # no se tocó

    def test_un_fallo_de_red_no_pausa_nada(self):
        s, repo, _, telegram, _ = armar([activo()], RocketfyPorSku([], fallan=["DEMO-1"]))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "activo" and telegram.avisos == []

    def test_un_sku_que_ya_no_aparece_no_se_pausa_ni_rompe(self):
        s, repo, _, telegram, _ = armar([activo()], RocketfyPorSku([]))
        r = s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "activo" and telegram.avisos == [] and r.fallidos == 0

    def test_un_error_inesperado_con_un_producto_no_impide_los_demas(self):
        filas = [activo(), activo(sku="DEMO-2")]
        s, repo, _, _, _ = armar(filas, RocketfyPorSku([en_rocketfy(), en_rocketfy("DEMO-2", stock=3)]))
        original = repo.guardar_datos_rocketfy

        def roto(sku, datos):
            if sku == "DEMO-1":
                raise RuntimeError("bug")
            return original(sku, datos)

        repo.guardar_datos_rocketfy = roto
        r = s.sincronizar_todos()
        assert r.fallidos == 1 and repo.filas["DEMO-2"]["stock_ultimo"] == 3


class TestAutoPausaPorAgotado:
    def test_un_activo_sin_stock_pasa_a_agotado_y_se_avisa(self):
        s, repo, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        r = s.sincronizar_todos()

        fila = repo.filas["DEMO-1"]
        assert (fila["estado"], fila["activo"]) == ("agotado", False)  # la regla estado <-> activo se mantiene
        assert r.pausados_por_agotado == 1
        pausa = [h for h in repo.historial if h["accion"] == "agotado"]
        assert len(pausa) == 1 and pausa[0]["usuario"] is None
        assert pausa[0]["cambios"] == {"estado": ["activo", "agotado"], "motivo": "Rocketfy reporta 0 unidades"}
        assert alertas.alertas == [("DEMO-1", TIPO_ALERTA_AGOTADO, {"stock": 0})]
        assert len(telegram.avisos) == 1
        assert "sin stock" in telegram.avisos[0][0].lower() and "DEMO-1" in telegram.avisos[0][1]
        assert "reanúdalo" in telegram.avisos[0][1]

    def test_con_una_sola_unidad_sigue_activo(self):
        s, repo, alertas, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=1)]))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "activo" and alertas.alertas == []

    def test_si_rocketfy_no_dice_cuanto_hay_no_se_pausa(self):
        producto = en_rocketfy()
        producto["stock"] = None
        s, repo, _, telegram, _ = armar([activo()], RocketfyPorSku([producto]))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "activo" and telegram.avisos == []

    def test_si_una_persona_lo_pauso_en_el_medio_no_se_pisa_su_decision(self):
        s, repo, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        original = repo.guardar_datos_rocketfy

        def mientras_tanto_lo_pausan(sku, datos):
            fila = original(sku, datos)
            repo.filas[sku]["estado"], repo.filas[sku]["activo"] = "pausado", False
            return fila

        repo.guardar_datos_rocketfy = mientras_tanto_lo_pausan
        r = s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "pausado" and r.pausados_por_agotado == 0
        assert alertas.alertas == [] and telegram.avisos == []

    def test_un_fallo_de_telegram_no_deshace_la_pausa(self):
        s, repo, alertas, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]), telegram=TelegramFalso(falla=True))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "agotado" and len(alertas.alertas) == 1

    def test_un_fallo_al_guardar_la_alerta_no_deshace_la_pausa_y_el_telegram_sale(self):
        s, repo, _, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]), alertas=AlertasFalsas(falla=True))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["estado"] == "agotado" and len(telegram.avisos) == 1

    def test_la_alerta_exige_que_el_sku_este_en_vigilados_y_se_agrega_si_falta(self):
        s, _, alertas, _, monitoreo = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]), monitoreo=MonitoreoFalso(vigilados=[]))
        s.sincronizar_todos()
        assert monitoreo.upserts and monitoreo.upserts[0][0] == "DEMO-1" and len(alertas.alertas) == 1

    def test_ya_vigilado_no_se_vuelve_a_agregar_ni_se_pisa_su_umbral(self):
        s, _, _, _, monitoreo = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        s.sincronizar_todos()
        assert monitoreo.upserts == []

    def test_correr_dos_veces_no_repite_el_aviso(self):
        s, _, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        s.sincronizar_todos()
        s.sincronizar_todos()  # ya está agotado: se refresca, pero no se vuelve a pausar ni a avisar
        assert len(alertas.alertas) == 1 and len(telegram.avisos) == 1


class TestLosAutomatismosSeApaganDesdeParametros:
    @staticmethod
    def _apagar(monkeypatch, *claves):
        from src.config.parametros import parametros

        real = parametros.valor
        monkeypatch.setattr(parametros, "valor", lambda clave: False if clave in claves else real(clave))

    def test_sin_autopausa_un_producto_agotado_sigue_activo_pero_los_datos_se_actualizan(self, monkeypatch):
        self._apagar(monkeypatch, "sync.autopausa_agotado")
        s, repo, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        r = s.sincronizar_todos()

        fila = repo.filas["DEMO-1"]
        assert (fila["estado"], fila["stock_ultimo"]) == ("activo", 0)  # no se pausó, pero el stock se refrescó
        assert r.actualizados == 1 and r.pausados_por_agotado == 0
        assert alertas.alertas == [] and telegram.avisos == []

    def test_sin_alerta_de_margen_no_se_avisa_aunque_el_margen_caiga(self, monkeypatch):
        self._apagar(monkeypatch, "sync.alerta_margen")
        s, repo, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="22.00")]))
        r = s.sincronizar_todos()

        assert repo.filas["DEMO-1"]["costo_rocketfy"] == Decimal("22.00")  # el costo sí se actualiza
        assert r.alertas_de_margen == 0 and alertas.alertas == [] and telegram.avisos == []

    def test_apagar_una_no_apaga_la_otra(self, monkeypatch):
        self._apagar(monkeypatch, "sync.alerta_margen")
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        assert s.sincronizar_todos().pausados_por_agotado == 1


class TestAlertaDeMargenEnRiesgo:
    # Con los ajustes de prueba (envío $5, mínimo 25 %) y precio $34.90:
    #   costo 10 -> ganancia 19.90 (57 %)   costo 22 -> ganancia 7.90 (22.6 %, bajo el mínimo)
    def test_avisa_cuando_el_costo_sube_y_el_margen_cae_bajo_el_minimo(self):
        s, repo, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="22.00")]))
        r = s.sincronizar_todos()

        assert r.alertas_de_margen == 1
        sku, tipo, detalle = alertas.alertas[0]
        assert (sku, tipo) == ("DEMO-1", TIPO_ALERTA_MARGEN)
        assert detalle == {"costoAnterior": "10.00", "costoActual": "22.00", "precio": "34.90", "margenPct": "22.6", "margenMinimoPct": "25.00"}
        assert "Margen en riesgo" in telegram.avisos[0][0] and "$10.00 a $22.00" in telegram.avisos[0][1]
        assert "No se cambió el precio" in telegram.avisos[0][1]

    def test_nunca_cambia_el_precio(self):
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="40.00")]))
        s.sincronizar_todos()
        assert repo.filas["DEMO-1"]["precio"] == Decimal("34.90")

    def test_si_pierde_dinero_lo_dice(self):
        s, _, _, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="40.00")]))
        s.sincronizar_todos()
        assert "pierdes dinero" in telegram.avisos[0][1]

    def test_si_el_margen_sigue_sano_no_avisa(self):
        s, _, alertas, telegram, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="12.00")]))
        s.sincronizar_todos()
        assert alertas.alertas == [] and telegram.avisos == []

    def test_se_avisa_al_cruzar_el_umbral_y_no_en_cada_corrida(self):
        s, repo, alertas, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="22.00")]))
        s.sincronizar_todos()
        s.sincronizar_todos()  # mismo costo: ya estaba en riesgo, no se repite
        assert len(alertas.alertas) == 1

    def test_si_ya_estaba_en_riesgo_y_el_costo_sigue_subiendo_no_se_repite(self):
        s, _, alertas, _, _ = armar([activo(costo_rocketfy=Decimal("23.00"))], RocketfyPorSku([en_rocketfy(costo="25.00")]))
        s.sincronizar_todos()
        assert alertas.alertas == []

    def test_si_vuelve_a_cruzar_despues_de_recuperarse_avisa_de_nuevo(self):
        catalogo = RocketfyPorSku([en_rocketfy(costo="22.00")])
        s, _, alertas, _, _ = armar([activo()], catalogo)
        s.sincronizar_todos()
        catalogo.productos["DEMO-1"]["price"] = "12.00"
        s.sincronizar_todos()
        catalogo.productos["DEMO-1"]["price"] = "23.00"
        s.sincronizar_todos()
        assert len(alertas.alertas) == 2

    def test_con_ajustes_de_partida_sin_confirmar_no_se_juzga(self):
        s, _, alertas, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(costo="40.00")]), ajustes=AjustesFalsos(confirmado=False))
        s.sincronizar_todos()
        assert alertas.alertas == []

    def test_si_el_costo_no_cambia_no_se_evalua(self):
        s, _, alertas, _, _ = armar([activo(costo_rocketfy=Decimal("22.00"))], RocketfyPorSku([en_rocketfy(costo="22.00")]))
        s.sincronizar_todos()
        assert alertas.alertas == []

    def test_un_costo_que_aparece_por_primera_vez_y_ya_es_riesgoso_avisa(self):
        s, _, alertas, _, _ = armar([activo(costo_rocketfy=None)], RocketfyPorSku([en_rocketfy(costo="22.00")]))
        s.sincronizar_todos()
        assert len(alertas.alertas) == 1 and alertas.alertas[0][2]["costoAnterior"] is None


class TestEjecutar:
    def test_sin_lock_no_corre(self):
        s, _, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        with patch("src.routes.productos_bot.sincronizacion.acquire_lock", return_value=False) as lock, \
             patch("src.routes.productos_bot.sincronizacion.release_lock") as soltar:
            assert s.ejecutar() is None
        lock.assert_called_once_with(JOB_NAME)
        soltar.assert_not_called()

    def test_con_lock_corre_y_siempre_lo_suelta(self):
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy(stock=0)]))
        with patch("src.routes.productos_bot.sincronizacion.acquire_lock", return_value=True), \
             patch("src.routes.productos_bot.sincronizacion.release_lock") as soltar:
            r = s.ejecutar()
        assert r.pausados_por_agotado == 1 and repo.filas["DEMO-1"]["estado"] == "agotado"
        soltar.assert_called_once_with(JOB_NAME)

    def test_si_la_corrida_revienta_el_lock_igual_se_suelta(self):
        s, repo, _, _, _ = armar([activo()], RocketfyPorSku([en_rocketfy()]))
        repo.listar = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("base caída"))
        with patch("src.routes.productos_bot.sincronizacion.acquire_lock", return_value=True), \
             patch("src.routes.productos_bot.sincronizacion.release_lock") as soltar:
            with pytest.raises(RuntimeError):
                s.ejecutar()
        soltar.assert_called_once_with(JOB_NAME)
