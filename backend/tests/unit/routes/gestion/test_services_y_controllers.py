"""«Por gestionar» (ADR-012): el servicio con repositorio y Telegram falsos, y la capa HTTP."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
import responses

from src.app import create_app
from src.routes.gestion.repository import ResultadoUpsert
from src.routes.gestion.services import (
    EstadoInvalidoError,
    GestionService,
    SolicitudNoEncontradaError,
    SolicitudYaAtendidaError,
)
from tests.conftest import AUTH_HEADER, mock_login_ok

AHORA = datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def _fila(**cambios):
    fila = {
        "id": 1, "conversacion_id": 7, "tipo": "pedido_cerrado", "detalle": "2 x Zapatos", "estado": "pendiente",
        "nota_atencion": None, "atendida_por": None, "creada_en": AHORA, "atendida_en": None,
        "telefono": "593987654321", "estado_conversacion": "en_gestion", "nombre_cliente": "Ana", "direccion": "Calle 1",
        "canton": "Cuenca", "provincia": "Azuay", "producto_nombre": "Zapatos", "producto_variante": "talla 40",
        "cantidad": 2, "metodo_pago": "contraentrega", "entrega_nombre": "Envío en Cuenca", "entrega_tipo": "envio",
        "costo_envio": 2, "venta_id": 5, "venta_total": 62, "venta_estado": "por_gestionar", "proveedor_nombre": "Producto propio",
    }
    fila.update(cambios)
    return fila


class RepoFalso:
    def __init__(self, filas=(), resultado=None):
        self.filas = list(filas)
        self.resultado = resultado or ResultadoUpsert(id=1, creada=True, tipo="quiere_comprar", tipo_anterior=None)
        self.solicitadas = []
        self.atendidas = []

    def solicitar(self, conversacion_id, lead_id, tipo, detalle, venta_id=None):
        self.solicitadas.append((conversacion_id, lead_id, tipo, detalle))
        return self.resultado

    def listar(self, estado="pendiente", limite=100):
        return [f for f in self.filas if f["estado"] == estado]

    def obtener(self, solicitud_id):
        return next((f for f in self.filas if f["id"] == solicitud_id), None)

    def contar_pendientes(self):
        return len([f for f in self.filas if f["estado"] == "pendiente"])

    def atender(self, solicitud_id, usuario, nota):
        fila = self.obtener(solicitud_id)
        if fila is None or fila["estado"] != "pendiente":
            return None
        fila.update(estado="atendida", atendida_por=usuario, nota_atencion=nota, atendida_en=AHORA)
        self.atendidas.append(solicitud_id)
        return fila


class TelegramFalso:
    def __init__(self, falla=False):
        self.gestiones, self.cerrados, self.falla = [], [], falla

    def notificar_gestion(self, etiqueta, conversacion_id, telefono, detalle=""):
        if self.falla:
            raise RuntimeError("telegram caído")
        self.gestiones.append((etiqueta, conversacion_id, telefono, detalle))

    def notificar_pedido_cerrado(self, datos):
        if self.falla:
            raise RuntimeError("telegram caído")
        self.cerrados.append(datos)


class TestSolicitar:
    def test_la_primera_vez_guarda_y_avisa(self):
        repo, telegram = RepoFalso(), TelegramFalso()
        resultado = GestionService(repo, telegram).solicitar(7, 3, "quiere_comprar", " lo quiere ", "593987654321")

        assert repo.solicitadas == [(7, 3, "quiere_comprar", "lo quiere")]
        assert telegram.gestiones == [("Quiere comprar", 7, "593987654321", "lo quiere")]
        assert resultado.traspasa is False and resultado.etiqueta == "Quiere comprar"

    def test_repetir_lo_mismo_no_vuelve_a_avisar(self):
        repo = RepoFalso(resultado=ResultadoUpsert(id=1, creada=False, tipo="quiere_comprar", tipo_anterior="quiere_comprar"))
        telegram = TelegramFalso()
        GestionService(repo, telegram).solicitar(7, 3, "quiere_comprar", None, "593")
        assert telegram.gestiones == []

    def test_subir_de_categoria_si_avisa_con_la_nueva_etiqueta(self):
        repo = RepoFalso(resultado=ResultadoUpsert(id=1, creada=False, tipo="quiere_ver_producto", tipo_anterior="quiere_comprar"))
        telegram = TelegramFalso()
        resultado = GestionService(repo, telegram).solicitar(7, 3, "quiere_ver_producto", "quiere verlos", "593")
        assert telegram.gestiones[0][0] == "Quiere ver el producto" and resultado.traspasa is True

    def test_si_telegram_falla_la_solicitud_igual_queda_guardada(self):
        repo = RepoFalso()
        GestionService(repo, TelegramFalso(falla=True)).solicitar(7, 3, "otro", None, "593")  # no debe lanzar
        assert len(repo.solicitadas) == 1

    def test_el_detalle_se_recorta(self):
        repo = RepoFalso()
        GestionService(repo, TelegramFalso()).solicitar(7, 3, "otro", "x" * 900, "593")
        assert len(repo.solicitadas[0][3]) == 500

    def test_avisar_pedido_cerrado_no_lanza_si_telegram_falla(self):
        GestionService(RepoFalso(), TelegramFalso(falla=True)).avisar_pedido_cerrado({"cliente": "Ana"})


class TestLeerYAtender:
    def test_listar_traduce_la_fila_para_la_app(self):
        item = GestionService(RepoFalso([_fila()]), TelegramFalso()).listar("pendiente")[0]
        assert (item["tipo"], item["tipo_etiqueta"]) == ("pedido_cerrado", "Pedido cerrado")
        assert item["total"] == "62.00" and item["producto"] == "Zapatos" and item["tiene_pedido"] is True
        assert item["creada_en"] == AHORA.isoformat()

    def test_estado_invalido(self):
        with pytest.raises(EstadoInvalidoError):
            GestionService(RepoFalso(), TelegramFalso()).listar("cualquiera")

    def test_atender_guarda_quien_y_la_nota(self):
        repo = RepoFalso([_fila()])
        atendida = GestionService(repo, TelegramFalso()).atender(1, "ana@ejemplo.com", "  ya la llamé ")
        assert atendida["estado"] == "atendida" and atendida["atendida_por"] == "ana@ejemplo.com"
        assert atendida["nota_atencion"] == "ya la llamé"

    def test_atender_una_inexistente_o_ya_atendida(self):
        servicio = GestionService(RepoFalso([_fila(id=2, estado="atendida")]), TelegramFalso())
        with pytest.raises(SolicitudNoEncontradaError):
            servicio.atender(99, "x", None)
        with pytest.raises(SolicitudYaAtendidaError):
            servicio.atender(2, "x", None)

    def test_pendientes(self):
        assert GestionService(RepoFalso([_fila(), _fila(id=2, estado="atendida")]), TelegramFalso()).pendientes() == 1


SERVICIO = "src.routes.gestion.controllers.GestionService"


def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestHTTP:
    def test_sin_login_no_se_ve_nada(self):
        assert _client().get("/gestion").status_code == 401

    @responses.activate
    def test_lista_las_pendientes_en_camel_case(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.listar.return_value = [GestionService._a_dto(_fila())]
            r = _client().get("/gestion", headers=AUTH_HEADER)

        assert r.status_code == 200
        item = r.get_json()[0]
        assert item["tipoEtiqueta"] == "Pedido cerrado" and item["nombreCliente"] == "Ana" and item["tienePedido"] is True
        assert item["metodoPago"] == "contraentrega" and item["conversacionId"] == 7 and item["total"] == "62.00"
        servicio.return_value.listar.assert_called_once_with("pendiente")

    @responses.activate
    def test_estado_invalido_es_422(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.listar.side_effect = EstadoInvalidoError("El estado debe ser uno de: pendiente, atendida.")
            assert _client().get("/gestion?estado=x", headers=AUTH_HEADER).status_code == 422

    @responses.activate
    def test_resumen(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.pendientes.return_value = 3
            r = _client().get("/gestion/resumen", headers=AUTH_HEADER)
        assert r.get_json() == {"pendientes": 3}

    @responses.activate
    def test_atender_pasa_el_correo_del_usuario_y_la_nota(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.atender.return_value = GestionService._a_dto(_fila(estado="atendida"))
            r = _client().post("/gestion/1/atender", json={"nota": "ya la llamé"}, headers=AUTH_HEADER)

        assert r.status_code == 200 and r.get_json()["estado"] == "atendida"
        servicio.return_value.atender.assert_called_once_with(1, "freddyjavier556@gmail.com", "ya la llamé")

    @responses.activate
    def test_atender_inexistente_404_y_ya_atendida_409(self):
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.atender.side_effect = SolicitudNoEncontradaError("No existe")
            assert _client().post("/gestion/9/atender", json={}, headers=AUTH_HEADER).status_code == 404
        mock_login_ok()
        with patch(SERVICIO) as servicio:
            servicio.return_value.atender.side_effect = SolicitudYaAtendidaError("Ya estaba atendida")
            assert _client().post("/gestion/9/atender", json={}, headers=AUTH_HEADER).status_code == 409

    @responses.activate
    def test_nota_demasiado_larga_es_422(self):
        mock_login_ok()
        r = _client().post("/gestion/1/atender", json={"nota": "x" * 501}, headers=AUTH_HEADER)
        assert r.status_code == 422
