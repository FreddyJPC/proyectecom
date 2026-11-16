"""
Anuncios de Meta (ADR-017): reglas de alerta, cliente de la API de Marketing (sin red), el trabajo con dobles y la API del tablero.
Lo que nunca debe pasar: pausar por rendimiento, pausar dos veces, reactivar, o que el token aparezca en un error.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
import requests
import responses

from src.app import create_app
from src.config.database import get_connection
from src.config.parametros import parametros
from src.integrations.meta import MetaRechazoError, MetaRespuestaDudosaError
from src.integrations.meta.marketing import MetaMarketingClient, anuncio_desde_meta, metrica_desde_meta, normalizar_cuenta
from src.jobs.meta_anuncios.reglas import Umbrales, alerta_de_regateo, evaluar
from src.jobs.meta_anuncios.service import MetaAnunciosService
from tests.conftest import AUTH_HEADER, mock_login_ok

D = Decimal
TOKEN = "token-secreto-de-prueba-marketing"


def _anuncio(id_="1", estado="ACTIVE", sku="A", oferta=None):
    return {"id_anuncio": id_, "nombre": f"Anuncio {id_}", "estado_efectivo": estado, "producto_sku": sku, "oferta_id": oferta}


PRODUCTOS = {"A": {"nombre": "Linterna", "activo": True, "stock_ultimo": 50}, "B": {"nombre": "Cargador", "activo": False, "stock_ultimo": 0}}


class TestReglas:
    def _reglas(self, anuncios, productos=PRODUCTOS, ofertas=None, metricas=None, ventas=None, **umbrales):
        return {a.regla: a for a in evaluar(anuncios, productos, ofertas or {}, metricas or {}, ventas or {}, Umbrales(**umbrales))}

    def test_todo_bien_no_avisa(self):
        assert self._reglas([_anuncio()]) == {}

    def test_r1_producto_agotado_pide_pausar(self):
        r = self._reglas([_anuncio(sku="B")])
        assert r["R1"].pausar and "Cargador" in r["R1"].mensaje

    def test_r2_oferta_terminada_pide_pausar_y_r1_si_un_item_esta_pausado(self):
        ofertas = {7: {"nombre": "Combo", "vendible": False, "motivo": "ya terminó", "skus": ["A", "B"]}}
        r = self._reglas([_anuncio(sku=None, oferta=7)], ofertas=ofertas)
        assert r["R2"].pausar and r["R1"].pausar

    def test_r3_stock_bajo_r7_sin_vinculo_r8_rechazado(self):
        r = self._reglas([_anuncio(sku="A")], productos={"A": {"nombre": "L", "activo": True, "stock_ultimo": 3}})
        assert "R3" in r and not r["R3"].pausar
        assert "R7" in self._reglas([_anuncio(sku=None)])
        assert "R8" in self._reglas([_anuncio(estado="DISAPPROVED")])

    def test_un_anuncio_pausado_no_dispara_reglas_de_venta(self):
        assert self._reglas([_anuncio(sku="B", estado="PAUSED")]) == {}

    def test_reglas_de_gasto_solo_avisan(self):
        metricas = {"1": {"gasto": D("20"), "conversaciones": 10}}
        r = self._reglas([_anuncio()], metricas=metricas, gasto_sin_venta=D("15"), costo_conversacion=D("1.50"), minimo_conversaciones=10)
        assert set(r) == {"R4", "R5"} and not r["R4"].pausar and not r["R5"].pausar
        assert self._reglas([_anuncio()], metricas=metricas) == {}  # umbrales en 0 = apagadas

    def test_r6_costo_por_venta_mayor_que_la_ganancia(self):
        r = self._reglas([_anuncio()], metricas={"1": {"gasto": D("30")}}, ventas={"1": {"ventas": 2, "ganancia": D("20")}})
        assert "R6" in r and "$15.00 por venta" in r["R6"].mensaje
        assert "R6" not in self._reglas([_anuncio()], metricas={"1": {"gasto": D("30")}}, ventas={"1": {"ventas": 2, "ganancia": None}})

    def test_r9_regateo(self):
        filas = [{"sku": "A", "nombre": "L", "ventas": 6, "con_regateo": 4}, {"sku": "B", "ventas": 3, "con_regateo": 3}]
        assert [a.objeto for a in alerta_de_regateo(filas, 50)] == ["A"]
        assert alerta_de_regateo(filas, 0) == []


def _resp(status=200, cuerpo=None):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = cuerpo if cuerpo is not None else {}
    return r


class TestCliente:
    def test_normaliza_la_cuenta_y_convierte_lo_que_lee(self):
        assert normalizar_cuenta(" act_1445 ") == "1445" and normalizar_cuenta("abc") == ""
        a = anuncio_desde_meta({"id": "9", "name": "N", "effective_status": "ACTIVE", "adset": {"daily_budget": "1500"}, "creative": {"title": "T"}})
        assert a["presupuesto_diario"] == D("15.00") and a["titulo"] == "T"
        m = metrica_desde_meta({"ad_id": "9", "date_start": "2026-11-15", "spend": "3.457", "actions": [
            {"action_type": "onsite_conversion.messaging_conversation_started_7d", "value": "4"}]})
        assert (m["gasto"], m["conversaciones"]) == (D("3.46"), 4)

    def test_lee_con_el_token_en_el_encabezado_y_sigue_las_paginas(self):
        c = MetaMarketingClient(TOKEN, "act_123")
        c._session = MagicMock()
        c._session.get.side_effect = [
            _resp(200, {"data": [{"id": "1"}], "paging": {"next": "https://graph.facebook.com/next"}}),
            _resp(200, {"data": [{"id": "2"}]}),
        ]
        assert [a["id_anuncio"] for a in c.listar_anuncios()] == ["1", "2"]
        args, kwargs = c._session.get.call_args_list[0]
        assert "act_123/ads" in args[0] and TOKEN not in args[0] and kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"

    def test_un_error_de_lectura_no_muestra_el_token(self):
        c = MetaMarketingClient(TOKEN, "123")
        c._session = MagicMock()
        c._session.get.side_effect = requests.ReadTimeout(f"https://x/?access_token={TOKEN}")
        with pytest.raises(MetaRechazoError) as exc:
            c.listar_anuncios()
        assert TOKEN not in str(exc.value)

    def test_pausar(self):
        c = MetaMarketingClient(TOKEN, "123")
        c._session = MagicMock()
        c._session.post.return_value = _resp(200, {"success": True})
        c.pausar_anuncio("55")
        assert c._session.post.call_args[1]["data"] == {"status": "PAUSED"}
        c._session.post.return_value = _resp(400, {"error": {"message": "sin permiso", "code": 200}})
        with pytest.raises(MetaRechazoError):
            c.pausar_anuncio("55")
        c._session.post.side_effect = requests.ReadTimeout("lento")
        with pytest.raises(MetaRespuestaDudosaError):
            c.pausar_anuncio("55")


class RepoEnMemoria:
    def __init__(self, anuncios=None):
        self.guardados, self.metricas, self.alertas, self.acciones = [], [], set(), []
        self._anuncios = anuncios or []

    def guardar_anuncios(self, anuncios):
        self.guardados = anuncios
        return len(anuncios)

    def guardar_metricas(self, metricas):
        self.metricas = metricas
        return len(metricas)

    def anuncios_con_vinculo(self):
        return self._anuncios

    def productos(self, skus):
        return {s: PRODUCTOS[s] for s in skus if s in PRODUCTOS}

    def metricas_por_anuncio(self, desde):
        return {}

    def ventas_por_anuncio(self, desde):
        return {}

    def regateo_por_producto(self, desde):
        return []

    def registrar_alerta(self, regla, objeto, mensaje, id_anuncio, fecha):
        clave = (regla, objeto, fecha)
        nueva = clave not in self.alertas
        self.alertas.add(clave)
        return nueva

    def pausas_de_hoy(self, fecha):
        return [{"id_anuncio": a[0], "resultado": a[3]} for a in self.acciones]

    def registrar_accion(self, id_anuncio, regla, motivo, resultado, detalle, usuario):
        self.acciones.append((id_anuncio, regla, motivo, resultado))

    def resumen_del_dia(self, dia):
        return {"gasto": D("10"), "conversaciones": 8, "ventas": 2, "ingreso": D("50"), "ganancia": D("26")}


@pytest.fixture
def con_parametros(monkeypatch):
    valores = {"meta.anuncios_activo": True}
    real = parametros.valor
    monkeypatch.setattr(parametros, "valor", lambda clave: valores[clave] if clave in valores else real(clave))
    return valores


def _servicio(repo, cliente=None, hora=10):
    cliente = cliente or MagicMock()
    if not isinstance(cliente.listar_anuncios.return_value, list):
        cliente.listar_anuncios.return_value = []
        cliente.metricas_diarias.return_value = []
    reloj = lambda: datetime(2026, 11, 16, hora, 0, tzinfo=timezone(timedelta(hours=-5)))  # noqa: E731
    return MetaAnunciosService(repo=repo, cliente=cliente, telegram=MagicMock(), precios=MagicMock(), reloj=reloj), cliente


class TestServicio:
    def test_apagado_no_hace_nada(self):
        repo = RepoEnMemoria()
        servicio, cliente = _servicio(repo)
        assert servicio.ejecutar() == {"estado": "apagado"}
        cliente.listar_anuncios.assert_not_called()

    def test_avisa_una_sola_vez_por_dia_y_no_pausa_si_el_interruptor_esta_apagado(self, con_parametros):
        repo = RepoEnMemoria([_anuncio(sku="B")])
        servicio, cliente = _servicio(repo)
        assert servicio.ejecutar()["alertas"] == 1
        assert servicio.ejecutar()["alertas"] == 0
        cliente.pausar_anuncio.assert_not_called()
        assert servicio._telegram.notificar_aviso.call_count == 1

    def test_con_pausa_automatica_pausa_una_vez_y_registra(self, con_parametros):
        con_parametros["meta.pausa_automatica"] = True
        repo = RepoEnMemoria([_anuncio(sku="B")])
        servicio, cliente = _servicio(repo)
        servicio.ejecutar()
        servicio.ejecutar()
        cliente.pausar_anuncio.assert_called_once_with("1")
        assert repo.acciones == [("1", "R1", repo.acciones[0][2], "hecho")]

    def test_una_pausa_dudosa_no_se_repite(self, con_parametros):
        con_parametros["meta.pausa_automatica"] = True
        repo = RepoEnMemoria([_anuncio(sku="B")])
        cliente = MagicMock()
        cliente.listar_anuncios.return_value, cliente.metricas_diarias.return_value = [], []
        cliente.pausar_anuncio.side_effect = MetaRespuestaDudosaError("cortado")
        servicio, _ = _servicio(repo, cliente)
        servicio.ejecutar()
        servicio.ejecutar()
        assert cliente.pausar_anuncio.call_count == 1 and repo.acciones[0][3] == "dudoso"

    def test_no_pausa_por_rendimiento(self, con_parametros):
        con_parametros.update({"meta.pausa_automatica": True, "meta.alerta_gasto_sin_venta": 1})
        repo = RepoEnMemoria([_anuncio()])
        repo.metricas_por_anuncio = lambda desde: {"1": {"gasto": D("50"), "conversaciones": 0}}
        servicio, cliente = _servicio(repo)
        assert servicio.ejecutar()["alertas"] == 1
        cliente.pausar_anuncio.assert_not_called()

    def test_error_al_leer_avisa_una_vez(self, con_parametros):
        repo = RepoEnMemoria()
        cliente = MagicMock()
        cliente.listar_anuncios.side_effect = MetaRechazoError("Meta rechazó la lectura: sin permiso")
        servicio, _ = _servicio(repo, cliente)
        assert servicio.ejecutar()["estado"] == "error"
        servicio.ejecutar()
        assert servicio._telegram.notificar_aviso.call_count == 1

    def test_resumen_diario_desde_las_8_y_una_vez(self, con_parametros):
        con_parametros["meta.resumen_diario"] = True
        repo = RepoEnMemoria()
        servicio, _ = _servicio(repo, hora=7)
        servicio.ejecutar()
        assert servicio._telegram.notificar_aviso.call_count == 0
        servicio, _ = _servicio(repo, hora=9)
        servicio.ejecutar()
        servicio.ejecutar()
        titulo, cuerpo = servicio._telegram.notificar_aviso.call_args[0]
        assert servicio._telegram.notificar_aviso.call_count == 1 and "15/11" in titulo and "Costo por venta: $5.00" in cuerpo


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture
def base_limpia():
    def _limpiar():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from meta_metricas_diarias where id_anuncio like 'T-%%'")
                cur.execute("delete from meta_anuncios where id_anuncio like 'T-%%'")
                cur.execute("update ajustes_negocio set meta_cuenta_publicitaria = null where id = 1")

    _limpiar()
    yield
    _limpiar()


class TestApi:
    @responses.activate
    def test_cuenta_publicitaria(self, base_limpia):
        mock_login_ok()
        c = _client()
        assert c.put("/meta/cuenta", json={"cuentaPublicitaria": "abc"}, headers=AUTH_HEADER).status_code == 422
        assert c.put("/meta/cuenta", json={"cuentaPublicitaria": "act_1445728047079452"}, headers=AUTH_HEADER).json["cuentaPublicitaria"] == "1445728047079452"
        assert c.get("/meta/cuenta", headers=AUTH_HEADER).json["cuentaPublicitaria"] == "1445728047079452"

    @responses.activate
    def test_tablero_con_gasto(self, base_limpia):
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("insert into meta_anuncios (id_anuncio, nombre, estado_efectivo) values ('T-1', 'Linterna video', 'ACTIVE')")
                cur.execute("insert into meta_metricas_diarias (id_anuncio, fecha, gasto, conversaciones) values ('T-1', current_date, 12.50, 5)")
        mock_login_ok()
        r = _client().get("/meta/anuncios?dias=7", headers=AUTH_HEADER)
        assert r.status_code == 200
        fila = next(a for a in r.json["anuncios"] if a["idAnuncio"] == "T-1")
        assert (fila["gasto"], fila["conversacionesMeta"], fila["costoPorConversacion"], fila["ventas"]) == ("12.50", 5, "2.50", 0)

    @responses.activate
    def test_leer_ahora_apagado_y_pausar_sin_configurar(self, base_limpia, monkeypatch):
        mock_login_ok()
        c = _client()
        assert c.post("/meta/anuncios/leer", headers=AUTH_HEADER).status_code == 409
        falso = MagicMock()
        falso.pausar_manual.return_value = {"resultado": "ok", "mensaje": "Se pausó el anuncio 55."}
        monkeypatch.setattr("src.routes.meta.controllers._servicio_anuncios", lambda: falso)
        assert c.post("/meta/anuncios/55/pausar", headers=AUTH_HEADER).json["mensaje"].startswith("Se pausó")
        assert c.post("/meta/anuncios/abc/pausar", headers=AUTH_HEADER).status_code == 422
