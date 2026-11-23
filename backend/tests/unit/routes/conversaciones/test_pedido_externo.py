"""
«Ya hice el pedido en Rocketfy» (pendiente #89): unir a la venta un pedido que el dueño creó a mano en el panel de Rocketfy.

Lo que se protege: nunca dos pedidos para la misma venta, nunca unir el pedido de OTRO cliente (número mal escrito), nunca crear
nada en Rocketfy (solo se consulta), y lo que no coincide con el chat se avisa sin frenar.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
import responses

from src.app import create_app
from src.config.database import get_connection
from src.integrations.rocketfy import RocketfyBusinessError, RocketfyRequestError
from src.routes.conversaciones.exceptions import ConversacionNoEncontradaError, PedidoYaCerradoError, SinPedidoEnCursoError
from src.routes.conversaciones.pedido_externo import (
    PedidoExternoInvalidoError,
    PedidoExternoService,
    RocketfyNoDisponibleError,
)
from src.routes.pedidos.repository import PedidoRepository
from tests.conftest import AUTH_HEADER, mock_login_ok


# ---------------------------------------------------------------------- dobles de prueba
class ClienteFalso:
    def __init__(self, orden=None, error=None):
        self.orden = orden
        self.error = error
        self.consultas = []
        self.escrituras = []

    def consultar_pedido(self, order_id):
        self.consultas.append(order_id)
        if self.error:
            raise self.error
        return {"ok": 1, "order": self.orden}

    # Si el servicio intentara crear, confirmar o tocar algo en Rocketfy, la prueba lo detecta.
    def crear_pedido(self, *a, **k):
        self.escrituras.append("crear")

    def confirmar_pedido(self, *a, **k):
        self.escrituras.append("confirmar")

    def modificar_pedido(self, *a, **k):
        self.escrituras.append("modificar")

    def rechazar_pedido(self, *a, **k):
        self.escrituras.append("rechazar")


class PedidosFalsos:
    def __init__(self, existentes=None, status=None, ocupados=0):
        self.filas = dict(existentes or {})  # id_rocketfy -> fila
        self.status = status
        self.ocupados = ocupados  # cuántos id_local seguidos ya están tomados
        self.insertados = []

    def obtener_por_id_rocketfy(self, id_rocketfy):
        return self.filas.get(id_rocketfy)

    def insertar_externo(self, id_local, id_rocketfy, estado_local, status_id, payload):
        if self.ocupados > 0:
            self.ocupados -= 1
            return False
        fila = {"id_local": id_local, "id_rocketfy": id_rocketfy, "estado_local": estado_local, "status_id_rocketfy": status_id,
                "payload_creacion": payload}
        self.filas[id_rocketfy] = fila
        self.insertados.append(fila)
        return True

    def ultimo_status_avisado(self, id_rocketfy):
        return self.status

    def sin_vincular(self, dias, limite):
        return []


class LeadsFalsos:
    def __init__(self, lead):
        self.lead = lead
        self.despachos = []

    def obtener_por_conversacion(self, conversacion_id):
        return self.lead

    def obtener_por_id(self, lead_id):
        return self.lead

    def actualizar_despacho(self, lead_id, id_pedido_local, id_pedido_rocketfy):
        self.despachos.append((lead_id, id_pedido_local, id_pedido_rocketfy))
        self.lead = {**self.lead, "estado": "despachado", "id_pedido_local": id_pedido_local}


class ConversacionesFalsas:
    def __init__(self, conversacion):
        self.conversacion = conversacion

    def obtener_por_id(self, conversacion_id):
        return self.conversacion


class MensajesFalsos:
    def __init__(self):
        self.creados = []

    def crear(self, **kwargs):
        self.creados.append(kwargs)
        return kwargs


class ProductosFalsos:
    def __init__(self, productos):
        self.productos = productos

    def obtener_por_sku(self, sku):
        return self.productos.get(sku)


class VentasFalsas:
    def __init__(self):
        self.registradas = []

    def registrar_venta_rocketfy(self, lead, producto, conversacion, entrega, productos=None):
        self.registradas.append((lead, producto, productos))


class EntregasFalsas:
    def obtener(self, opcion_id):
        return None


SKU = "2067-BOWL-COLADORRALLADOR"
PRODUCTO = {"sku": SKU, "nombre": "Set 3 en 1", "proveedor_cierre": "rocketfy"}
ORDEN_ROMULO = {
    "id": 413585, "name": "Rómulo Lorenzo Mora Rea", "phone": "0993669219", "address": "Avenida 5 de Octubre 1418, Naranjito",
    "city": "NARANJITO", "province": "Guayas", "total": "25.00", "confirmed_at": "2026-11-23 09:17:10",
}


def _lead(**cambios):
    base = {
        "id": 40, "estado": "recopilando_datos", "telefono": "593993669219", "producto_sku": SKU,
        "producto_nombre": "Set 3 en 1", "cantidad": 1, "total": Decimal("24.99"), "canton": "Naranjito",
        "provincia": "Guayas", "nombre_cliente": "Rómulo Lorenzo Mora Rea", "entrega_opcion_id": None, "cotizacion": None,
    }
    base.update(cambios)
    return base


def _servicio(orden=ORDEN_ROMULO, lead=None, error=None, existentes=None, status=2, producto=PRODUCTO, ocupados=0,
              conversacion=None):
    piezas = {
        "client": ClienteFalso(orden, error),
        "pedido_repo": PedidosFalsos(existentes, status, ocupados),
        "lead_repo": LeadsFalsos(lead if lead is not None else _lead()),
        "conversacion_repo": ConversacionesFalsas(
            conversacion if conversacion is not None else {"id": 43, "id_externo": "593993669219", "estado": "escalada"}
        ),
        "mensaje_repo": MensajesFalsos(),
        "producto_repo": ProductosFalsos({SKU: producto} if producto else {}),
        "entrega_repo": EntregasFalsas(),
        "ventas": VentasFalsas(),
    }
    return PedidoExternoService(**piezas), piezas


# ---------------------------------------------------------------------- servicio
class TestRegistrar:
    def test_une_el_pedido_cierra_la_venta_y_deja_nota(self):
        servicio, p = _servicio()
        resultado = servicio.registrar(43, 413585, usuario="dueno@ejemplo.com")

        fila = p["pedido_repo"].insertados[0]
        assert fila["id_rocketfy"] == 413585
        assert fila["estado_local"] == "confirmado"  # Rocketfy dice que ya se confirmó
        assert fila["status_id_rocketfy"] == 2  # el último aviso del webhook
        payload = fila["payload_creacion"]
        # Las claves que lee el aviso «paquete en agencia» (webhooks/repository.obtener_datos_pedido).
        assert payload["nombre_cliente"] == "Rómulo Lorenzo Mora Rea"
        assert payload["telefono"] == "0993669219"
        assert payload["canton"] == "NARANJITO"
        assert payload["total"] == "25.00"  # string, nunca float
        assert payload["origen"] == "panel_rocketfy"
        assert payload["lineas"] == [{"sku": SKU, "nombre": "Set 3 en 1", "cantidad": 1}]

        assert p["lead_repo"].despachos == [(40, fila["id_local"], 413585)]
        assert len(p["ventas"].registradas) == 1
        nota = p["mensaje_repo"].creados[0]
        assert nota["rol"] == "sistema" and "413585" in nota["contenido"] and "no crees otro pedido" in nota["contenido"]
        assert resultado["idRocketfy"] == 413585 and resultado["idLocal"] == fila["id_local"]

    def test_nunca_escribe_en_rocketfy(self):
        servicio, p = _servicio()
        servicio.registrar(43, 413585)
        assert p["client"].consultas == [413585]
        assert p["client"].escrituras == []

    def test_avisa_si_el_total_no_coincide_con_lo_acordado(self):
        servicio, _ = _servicio()
        resultado = servicio.registrar(43, 413585)
        assert resultado["avisos"] == ["Rocketfy va a cobrar $25.00; en el chat se acordó $24.99."]

    def test_sin_avisos_si_todo_coincide(self):
        servicio, _ = _servicio(lead=_lead(total=Decimal("25.00")))
        assert servicio.registrar(43, 413585)["avisos"] == []

    def test_avisa_si_la_ciudad_es_otra(self):
        servicio, _ = _servicio(orden={**ORDEN_ROMULO, "city": "MILAGRO"}, lead=_lead(total=Decimal("25.00")))
        assert servicio.registrar(43, 413585)["avisos"] == ["La ciudad en Rocketfy es «MILAGRO» y en el chat «Naranjito»."]

    def test_pedido_sin_confirmar_queda_creado(self):
        servicio, p = _servicio(orden={**ORDEN_ROMULO, "confirmed_at": None})
        servicio.registrar(43, 413585)
        assert p["pedido_repo"].insertados[0]["estado_local"] == "creado"

    def test_pedido_de_otro_cliente_no_se_une(self):
        servicio, p = _servicio(orden={**ORDEN_ROMULO, "phone": "0987654321", "name": "Otra Persona"})
        with pytest.raises(PedidoExternoInvalidoError, match="otro cliente"):
            servicio.registrar(43, 413585)
        assert p["pedido_repo"].insertados == [] and p["lead_repo"].despachos == []

    def test_telefono_con_codigo_de_pais_es_el_mismo(self):
        servicio, p = _servicio(orden={**ORDEN_ROMULO, "phone": "+593 99 366 9219"})
        servicio.registrar(43, 413585)
        assert len(p["pedido_repo"].insertados) == 1

    def test_venta_ya_despachada_no_une_otro(self):
        for estado in ("despachado", "por_gestionar", "cancelado"):
            servicio, p = _servicio(lead=_lead(estado=estado))
            with pytest.raises(PedidoYaCerradoError):
                servicio.registrar(43, 413585)
            assert p["client"].consultas == []

    def test_pedido_ya_registrado_no_se_duplica(self):
        servicio, p = _servicio(existentes={413585: {"id_local": 111, "id_rocketfy": 413585}})
        with pytest.raises(PedidoExternoInvalidoError, match="ya está registrado"):
            servicio.registrar(43, 413585)
        assert p["lead_repo"].despachos == []

    def test_producto_propio_no_va_por_rocketfy(self):
        servicio, p = _servicio(producto={**PRODUCTO, "proveedor_cierre": "manual"})
        with pytest.raises(PedidoExternoInvalidoError, match="propio"):
            servicio.registrar(43, 413585)
        assert p["client"].consultas == []

    def test_sin_venta_en_curso(self):
        servicio, _ = _servicio()
        servicio._leads.lead = None
        with pytest.raises(SinPedidoEnCursoError):
            servicio.registrar(43, 413585)

    def test_conversacion_inexistente(self):
        servicio, _ = _servicio()
        servicio._conversaciones.conversacion = None
        with pytest.raises(ConversacionNoEncontradaError):
            servicio.registrar(43, 413585)

    def test_rocketfy_no_reconoce_el_numero(self):
        servicio, p = _servicio(error=RocketfyBusinessError(message="Pedido no encontrado", code=404))
        with pytest.raises(PedidoExternoInvalidoError, match="no encuentra el pedido"):
            servicio.registrar(43, 999)
        assert p["pedido_repo"].insertados == []

    def test_rocketfy_caido_no_guarda_nada(self):
        servicio, p = _servicio(error=RocketfyRequestError("timeout"))
        with pytest.raises(RocketfyNoDisponibleError):
            servicio.registrar(43, 413585)
        assert p["pedido_repo"].insertados == [] and p["lead_repo"].despachos == []

    def test_respuesta_sin_datos_del_pedido(self):
        servicio, _ = _servicio(orden={})
        with pytest.raises(PedidoExternoInvalidoError):
            servicio.registrar(43, 413585)

    def test_si_el_id_local_esta_ocupado_prueba_el_siguiente(self):
        servicio, p = _servicio(ocupados=2)
        resultado = servicio.registrar(43, 413585)
        assert resultado["idLocal"] == p["pedido_repo"].insertados[0]["id_local"]

    def test_sin_producto_registrado_igual_une_el_pedido(self):
        servicio, p = _servicio(lead=_lead(producto_sku=None, producto_nombre=None), producto=None)
        servicio.registrar(43, 413585)
        assert p["pedido_repo"].insertados[0]["payload_creacion"]["lineas"] == []
        assert p["lead_repo"].despachos and p["ventas"].registradas == []

    def test_si_falla_la_foto_de_la_venta_el_registro_sigue(self):
        servicio, p = _servicio()

        def falla(*a, **k):
            raise RuntimeError("base caída")

        p["ventas"].registrar_venta_rocketfy = falla
        resultado = servicio.registrar(43, 413585)
        assert resultado["idRocketfy"] == 413585 and p["lead_repo"].despachos


# ---------------------------------------------------------------------- repositorio (base de pruebas)
ID_PRUEBA = 990000413585
ID_PRUEBA_2 = 990000413586


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from webhook_events where id_rocketfy = any(%s)", ([ID_PRUEBA, ID_PRUEBA_2],))
            cur.execute("delete from pedidos where id_rocketfy = any(%s)", ([ID_PRUEBA, ID_PRUEBA_2],))


@pytest.fixture
def limpio():
    _limpiar()
    yield
    _limpiar()


def _aviso(id_rocketfy, status_id, fecha, total="25.00"):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into webhook_events (id_rocketfy, status_id, event_date, payload) values (%s, %s, %s, %s::jsonb)",
                (id_rocketfy, status_id, fecha,
                 f'{{"order_id": {id_rocketfy}, "status_id": {status_id}, "status_name": "Estado {status_id}", '
                 f'"shipping_company": "Servientrega", "total": "{total}"}}'),
            )


class TestRepositorio:
    def test_sin_vincular_lista_los_avisos_de_pedidos_que_no_son_nuestros(self, limpio):
        _aviso(ID_PRUEBA, 1, "2026-11-23T14:00:00Z")
        _aviso(ID_PRUEBA, 2, "2026-11-23T14:17:10Z")
        _aviso(ID_PRUEBA_2, 2, "2026-11-23T14:20:00Z")
        repo = PedidoRepository()
        assert repo.insertar_externo(1700000000990, ID_PRUEBA_2, "confirmado", 2, {"total": "10.00"})

        ids = [f["id_rocketfy"] for f in repo.sin_vincular(dias=14, limite=50)]
        assert ID_PRUEBA in ids and ID_PRUEBA_2 not in ids  # el segundo ya es nuestro
        assert repo.ultimo_status_avisado(ID_PRUEBA) == 2

        servicio = PedidoExternoService(pedido_repo=repo, conversacion_repo=ConversacionesFalsas({"id": 1}))
        item = next(i for i in servicio.sin_vincular(1) if i["idRocketfy"] == ID_PRUEBA)
        assert item == {**item, "estado": "Estado 2", "transportadora": "Servientrega", "total": "25.00"}

    def test_insertar_externo_no_pisa_ni_duplica(self, limpio):
        repo = PedidoRepository()
        assert repo.insertar_externo(1700000000991, ID_PRUEBA, "confirmado", 2, {"total": "25.00", "origen": "panel_rocketfy"})
        # Mismo pedido de Rocketfy con otro id_local: no entra (clave única de id_rocketfy).
        assert not repo.insertar_externo(1700000000992, ID_PRUEBA, "confirmado", 2, {"total": "25.00"})
        fila = repo.obtener_por_id_rocketfy(ID_PRUEBA)
        assert fila["id_local"] == 1700000000991 and fila["estado_local"] == "confirmado"
        assert fila["confirmado_en"] is not None and fila["payload_creacion"]["origen"] == "panel_rocketfy"

    def test_el_aviso_paquete_en_agencia_encuentra_al_cliente(self, limpio):
        from src.routes.webhooks.repository import WebhookRepository

        PedidoRepository().insertar_externo(
            1700000000993, ID_PRUEBA, "confirmado", 2, {"nombre_cliente": "Rómulo", "telefono": "0993669219", "canton": "NARANJITO"}
        )
        assert WebhookRepository.obtener_datos_pedido(ID_PRUEBA)["nombre_cliente"] == "Rómulo"


# ---------------------------------------------------------------------- HTTP
def _client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestEndpoints:
    @responses.activate
    def test_registrar_ok(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.PedidoExternoService") as Mock:
            Mock.return_value.registrar.return_value = {"idLocal": 1, "idRocketfy": 413585, "estado": "confirmado", "total": "25.00", "avisos": []}
            resp = _client().post("/conversaciones/43/pedido-rocketfy", json={"idRocketfy": 413585}, headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()["idRocketfy"] == 413585
        Mock.return_value.registrar.assert_called_once()
        assert Mock.return_value.registrar.call_args.args[:2] == (43, 413585)

    @responses.activate
    def test_numero_invalido(self):
        mock_login_ok()
        resp = _client().post("/conversaciones/43/pedido-rocketfy", json={"idRocketfy": "abc"}, headers=AUTH_HEADER)
        assert resp.status_code == 422

    @responses.activate
    def test_errores(self):
        mock_login_ok()
        casos = [
            (ConversacionNoEncontradaError("no"), 404),
            (PedidoYaCerradoError("ya"), 409),
            (PedidoExternoInvalidoError("otro cliente"), 409),
            (RocketfyNoDisponibleError("caído"), 502),
        ]
        for error, codigo in casos:
            with patch("src.routes.conversaciones.controllers.PedidoExternoService") as Mock:
                Mock.return_value.registrar.side_effect = error
                resp = _client().post("/conversaciones/43/pedido-rocketfy", json={"idRocketfy": 1}, headers=AUTH_HEADER)
            assert resp.status_code == codigo, error

    @responses.activate
    def test_lista_sin_vincular(self):
        mock_login_ok()
        with patch("src.routes.conversaciones.controllers.PedidoExternoService") as Mock:
            Mock.return_value.sin_vincular.return_value = [{"idRocketfy": 413585}]
            resp = _client().get("/conversaciones/43/pedidos-rocketfy", headers=AUTH_HEADER)
        assert resp.status_code == 200 and resp.get_json()["items"] == [{"idRocketfy": 413585}]

    @responses.activate
    def test_sin_sesion_no_entra(self):
        resp = _client().post("/conversaciones/43/pedido-rocketfy", json={"idRocketfy": 1})
        assert resp.status_code == 401
