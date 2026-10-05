"""
Tests de las herramientas de Victoria (Tarea 4, Fase 3.2). PedidoService
se ejercita de verdad, con un RocketfyClient real apuntando a un servidor
mockeado con `responses` -- igual que los tests existentes de Rocketfy
(tests/unit/integrations/test_rocketfy_client.py). Solo PedidoRepository
se reemplaza por un fake en memoria para no tocar la tabla `pedidos` real
(y lead/conversación/producto también son fakes, por la misma razón:
estas herramientas no deben depender de una Supabase real para probarse).

Ninguno de estos tests importa nada de `anthropic` -- solo trabajan con
ResultadoHerramienta, el tipo neutral de contratos.py.
"""
from decimal import Decimal
from unittest.mock import MagicMock

import responses

from src.integrations.rocketfy import RocketfyClient
from src.routes.pedidos.services import PedidoService
from src.routes.whatsapp.tools import HerramientasVictoria

BASE_URL = "https://rocket-e.com/api"

LEAD_COMPLETO_CONTRAENTREGA = {
    "nombre_cliente": "Juan Pérez",
    "telefono": "593987654321",
    "direccion": "Av. Siempre Viva 123",
    "canton": "QUITO",
    "provincia": "Pichincha",
    "producto_sku": "DEMO-1",
    "producto_nombre": "Producto Demo",
    "total": Decimal("24.99"),
    "metodo_pago": "contraentrega",
}


class FakeLeadRepository:
    def __init__(self, leads=None):
        self.leads = {k: dict(v) for k, v in (leads or {}).items()}

    def obtener_por_id(self, lead_id):
        return self.leads.get(lead_id)

    def actualizar_datos_cliente(self, lead_id, nombre_cliente=None, direccion=None, canton=None, provincia=None):
        lead = self.leads.setdefault(lead_id, {})
        for campo, valor in (
            ("nombre_cliente", nombre_cliente),
            ("direccion", direccion),
            ("canton", canton),
            ("provincia", provincia),
        ):
            if valor is not None:
                lead[campo] = valor

    def actualizar_producto(self, lead_id, producto_sku, producto_nombre, total, variante=None):
        lead = self.leads.setdefault(lead_id, {})
        lead["producto_sku"] = producto_sku
        lead["producto_nombre"] = producto_nombre
        lead["total"] = total
        if variante is not None:
            lead["producto_variante"] = variante

    def actualizar_metodo_pago(self, lead_id, metodo_pago):
        lead = self.leads.setdefault(lead_id, {})
        lead["metodo_pago"] = metodo_pago
        if metodo_pago == "transferencia":
            lead["estado"] = "esperando_pago"

    def actualizar_despacho(self, lead_id, id_pedido_local, id_pedido_rocketfy):
        lead = self.leads.setdefault(lead_id, {})
        lead["estado"] = "despachado"
        lead["id_pedido_local"] = id_pedido_local
        lead["id_pedido_rocketfy"] = id_pedido_rocketfy


class FakeConversacionRepository:
    def __init__(self, vista_en=None):
        self.estados = {}
        self.vista_en = dict(vista_en or {})

    def actualizar_estado(self, conversacion_id, estado):
        self.estados[conversacion_id] = estado

    def marcar_escalada(self, conversacion_id):
        self.estados[conversacion_id] = "escalada"
        self.vista_en[conversacion_id] = None

    def marcar_esperando_pago(self, conversacion_id):
        self.estados[conversacion_id] = "esperando_pago"


class FakeProductoBotRepository:
    def __init__(self, productos=None):
        self.productos = productos or {}

    def obtener_por_sku(self, sku):
        return self.productos.get(sku)

    def listar_activos(self):
        return list(self.productos.values())


class FakePedidoRepository:
    def __init__(self):
        self.tabla = {}

    def obtener(self, id_local):
        return self.tabla.get(id_local)

    def upsert_pendiente(self, id_local, payload_creacion):
        self.tabla[id_local] = {
            "id_local": id_local,
            "id_rocketfy": None,
            "estado_local": "pendiente_creacion",
            "status_id_rocketfy": None,
            "payload_creacion": payload_creacion,
            "mensaje_error": None,
            "creado_en": None,
            "confirmado_en": None,
            "actualizado_en": None,
        }

    def marcar_creado(self, id_local, id_rocketfy, estado_local):
        self.tabla[id_local]["id_rocketfy"] = id_rocketfy
        self.tabla[id_local]["estado_local"] = estado_local

    def marcar_error_creacion(self, id_local, mensaje):
        self.tabla[id_local]["estado_local"] = "error"
        self.tabla[id_local]["mensaje_error"] = mensaje

    def marcar_confirmado(self, id_local):
        self.tabla[id_local]["estado_local"] = "confirmado"

    def marcar_error_confirmacion(self, id_local, mensaje):
        self.tabla[id_local]["mensaje_error"] = mensaje


def _herramientas(lead_repo=None, conv_repo=None, producto_repo=None, pedido_service=None, telegram=None):
    return HerramientasVictoria(
        lead_repo=lead_repo or FakeLeadRepository(),
        conversacion_repo=conv_repo or FakeConversacionRepository(),
        producto_repo=producto_repo or FakeProductoBotRepository(),
        pedido_service=pedido_service
        or PedidoService(
            client=RocketfyClient(BASE_URL, "vendedor@ejemplo.com", "token-de-prueba"),
            repo=FakePedidoRepository(),
        ),
        telegram_notifier=telegram or MagicMock(),
    )


class TestGuardarDatosCliente:
    def test_guarda_los_datos_confirmados_sin_pisar_los_demas(self):
        leads = FakeLeadRepository(leads={1: {"nombre_cliente": "Viejo"}})
        herramientas = _herramientas(lead_repo=leads)

        resultado = herramientas.ejecutar(
            "guardar_datos_cliente",
            lead_id=1,
            conversacion_id=1,
            entrada={"canton": "Quito"},
            id_llamada="toolu_1",
        )

        assert resultado.id_llamada == "toolu_1"
        assert "guardados" in resultado.contenido.lower()
        assert leads.leads[1]["nombre_cliente"] == "Viejo"
        assert leads.leads[1]["canton"] == "Quito"


class TestRegistrarProducto:
    def test_registra_producto_y_convierte_total_a_decimal(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": {"sku": "DEMO-1", "nombre": "Producto Demo"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "total": 24.99},
            id_llamada="toolu_2",
        )

        assert leads.leads[1]["total"] == Decimal("24.99")
        assert isinstance(leads.leads[1]["total"], Decimal)

    def test_corrige_sku_inventado_buscando_por_nombre_en_el_catalogo_real(self):
        """Probado contra la API real: el LLM no siempre copia el SKU tal
        cual aparece en el catálogo -- a veces lo inventa (ej. 'AUD-BT-001'),
        a veces manda un placeholder ('N/A'). Si el sku recibido no
        coincide con ningún producto real, se corrige por nombre (sin
        distinguir tildes/mayúsculas) antes de guardar."""
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository(
            {"10-AUDIFONO-INALAM-TIPRO": {"sku": "10-AUDIFONO-INALAM-TIPRO", "nombre": "Audifonos Bluetooth inalambricos"}}
        )
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "N/A", "producto_nombre": "Audífonos Bluetooth Inalámbricos", "total": 24.99},
            id_llamada="toolu_2b",
        )

        assert leads.leads[1]["producto_sku"] == "10-AUDIFONO-INALAM-TIPRO"

    def test_variante_incluida_se_guarda(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": {"sku": "DEMO-1", "nombre": "Producto Demo"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "variante": "negro", "total": 24.99},
            id_llamada="toolu_2d",
        )

        assert leads.leads[1]["producto_variante"] == "negro"

    def test_sin_variante_la_columna_queda_sin_tocar(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": {"sku": "DEMO-1", "nombre": "Producto Demo"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "total": 24.99},
            id_llamada="toolu_2e",
        )

        assert leads.leads[1].get("producto_variante") is None

    def test_sin_match_de_ningun_producto_real_no_guarda_nada_y_devuelve_catalogo(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository(
            {"DEMO-1": {"sku": "DEMO-1", "nombre": "Producto Demo", "precio": Decimal("24.99")}}
        )
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "N/A", "producto_nombre": "Algo que no existe", "total": 5},
            id_llamada="toolu_2c",
        )

        assert 1 not in leads.leads or "producto_sku" not in leads.leads.get(1, {})
        assert "no encontré ese producto" in resultado.contenido.lower()
        assert "Producto Demo" in resultado.contenido
        assert "DEMO-1" in resultado.contenido


class TestRegistrarMetodoPago:
    def test_transferencia_marca_esperando_pago(self):
        leads = FakeLeadRepository()
        conversaciones = FakeConversacionRepository()
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones)

        herramientas.ejecutar(
            "registrar_metodo_pago",
            lead_id=1,
            conversacion_id=1,
            entrada={"metodo_pago": "transferencia"},
            id_llamada="toolu_3",
        )

        assert leads.leads[1]["metodo_pago"] == "transferencia"
        assert leads.leads[1]["estado"] == "esperando_pago"
        assert conversaciones.estados[1] == "esperando_pago"

    def test_contraentrega_no_cambia_estado(self):
        leads = FakeLeadRepository(leads={1: {"estado": "recopilando_datos"}})
        herramientas = _herramientas(lead_repo=leads)

        herramientas.ejecutar(
            "registrar_metodo_pago",
            lead_id=1,
            conversacion_id=1,
            entrada={"metodo_pago": "contraentrega"},
            id_llamada="toolu_3b",
        )

        assert leads.leads[1]["estado"] == "recopilando_datos"


class TestCerrarVenta:
    def test_datos_incompletos_no_llama_a_rocketfy(self):
        leads = FakeLeadRepository(leads={1: {"nombre_cliente": "Juan"}})
        herramientas = _herramientas(lead_repo=leads)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_4"
        )

        assert "faltan datos" in resultado.contenido.lower()
        assert leads.leads[1].get("estado") != "despachado"

    def test_transferencia_no_llama_a_rocketfy_pide_comprobante(self):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, metodo_pago="transferencia")
        leads = FakeLeadRepository(leads={1: lead})
        herramientas = _herramientas(lead_repo=leads)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_5"
        )

        assert "comprobante" in resultado.contenido.lower()
        assert leads.leads[1].get("estado") != "despachado"

    @responses.activate
    def test_contraentrega_exitoso_confirma_pedido(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 5001, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "ok"},
            status=200,
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        productos = FakeProductoBotRepository({"DEMO-1": {"tiempo_entrega": "2 a 4 días hábiles"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_6"
        )

        assert "pedido confirmado" in resultado.contenido.lower()
        assert "2 a 4 días hábiles" in resultado.contenido
        assert leads.leads[1]["estado"] == "despachado"
        assert leads.leads[1]["id_pedido_rocketfy"] == 5001

    @responses.activate
    def test_variante_se_incluye_en_el_nombre_de_la_linea_enviada_a_rocketfy(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 5004, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "ok"},
            status=200,
        )
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, producto_variante="negro")
        leads = FakeLeadRepository(leads={1: lead})
        productos = FakeProductoBotRepository({"DEMO-1": {"tiempo_entrega": "2 a 4 días hábiles"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_6c")

        import json

        payload_enviado = json.loads(responses.calls[0].request.body)
        lineas_enviadas = json.loads(payload_enviado["order_details"])
        assert lineas_enviadas[0]["name"] == "Producto Demo - negro"

    @responses.activate
    def test_sin_variante_el_nombre_de_la_linea_es_solo_el_del_producto(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 5005, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "ok"},
            status=200,
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        productos = FakeProductoBotRepository({"DEMO-1": {"tiempo_entrega": "2 a 4 días hábiles"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_6d")

        import json

        payload_enviado = json.loads(responses.calls[0].request.body)
        lineas_enviadas = json.loads(payload_enviado["order_details"])
        assert lineas_enviadas[0]["name"] == "Producto Demo"

    @responses.activate
    def test_telefono_se_convierte_a_formato_local_para_rocketfy(self):
        """Probado contra la API real: Rocketfy rechaza el formato
        internacional con código de país que entrega WhatsApp
        (593XXXXXXXXX) -- exige formato local (9-10 dígitos)."""
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 5003, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 1, "code": 200, "message": "ok"},
            status=200,
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA, telefono="593987654321")})
        productos = FakeProductoBotRepository({"DEMO-1": {"tiempo_entrega": "2 a 4 días hábiles"}})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_6b")

        import json

        payload_enviado = json.loads(responses.calls[0].request.body)
        assert payload_enviado["phone"] == "987654321"

    @responses.activate
    def test_contraentrega_con_error_de_negocio_escala_automaticamente(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 5002, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/confirm",
            json={"ok": 0, "code": 422, "message": "Sin cobertura para esta zona"},
            status=200,
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, telegram=telegram)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=7, entrada={}, id_llamada="toolu_7"
        )

        assert conversaciones.estados[7] == "escalada"
        telegram.notificar_escalado.assert_called_once()
        assert "problema técnico" in resultado.contenido.lower()
        assert leads.leads[1].get("estado") != "despachado"

    def test_ubicacion_no_resuelta_escala_sin_llamar_a_rocketfy(self):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, canton="CIUDAD-INVENTADA-XYZ", provincia="Provincia Inventada")
        leads = FakeLeadRepository(leads={1: lead})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, telegram=telegram)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=9, entrada={}, id_llamada="toolu_9"
        )

        assert conversaciones.estados[9] == "escalada"
        assert "problema técnico" in resultado.contenido.lower()


class TestEscalarAHumano:
    def test_marca_conversacion_escalada_y_notifica(self):
        leads = FakeLeadRepository(leads={1: {"telefono": "593987654321"}})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, telegram=telegram)

        resultado = herramientas.ejecutar(
            "escalar_a_humano",
            lead_id=1,
            conversacion_id=3,
            entrada={"motivo": "Cliente pidió hablar con una persona"},
            id_llamada="toolu_8",
        )

        assert conversaciones.estados[3] == "escalada"
        telegram.notificar_escalado.assert_called_once_with(3, "593987654321", "Cliente pidió hablar con una persona")
        assert "asesor" in resultado.contenido.lower()

    def test_reescalar_limpia_vista_en_de_una_escalada_anterior(self):
        """Módulo de Conversaciones, Tarea 2: si ya se había visto una
        escalada anterior, una nueva escalada debe volver a aparecer como
        sin revisar."""
        from datetime import datetime, timezone

        leads = FakeLeadRepository(leads={1: {"telefono": "593987654321"}})
        conversaciones = FakeConversacionRepository(vista_en={3: datetime.now(timezone.utc)})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, telegram=MagicMock())

        herramientas.ejecutar(
            "escalar_a_humano", lead_id=1, conversacion_id=3, entrada={"motivo": "de nuevo"}, id_llamada="toolu_8b"
        )

        assert conversaciones.vista_en[3] is None
