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
import json
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

    def actualizar_producto(self, lead_id, producto_sku, producto_nombre, total, variante=None, cantidad=1):
        lead = self.leads.setdefault(lead_id, {})
        lead["producto_sku"] = producto_sku
        lead["producto_nombre"] = producto_nombre
        lead["total"] = total
        lead["cantidad"] = cantidad
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

    def obtener_por_id(self, conversacion_id):
        return {
            "id": conversacion_id, "contacto_id": 1, "canal": "whatsapp",
            "id_externo": "593987654321", "telefono": "593987654321",
        }

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
        # Igual que el repositorio real: devuelve también los pausados.
        return self.productos.get(sku)

    def listar_activos(self):
        return [p for p in self.productos.values() if p.get("activo", True)]


class FakeStockChecker:
    """`stock=None` significa "no se pudo saber" (Rocketfy no respondió)."""

    def __init__(self, stock=None):
        self.stock = stock
        self.consultas = []

    def stock_de(self, sku, fresco=False):
        self.consultas.append((sku, fresco))
        return self.stock


class FakeMinimoRepository:
    def __init__(self, falla=False):
        self.falla = falla
        self.guardados = []

    def guardar(self, sku, canton, provincia, cantidad, minimo, mensaje):
        if self.falla:
            raise RuntimeError("base caída")
        self.guardados.append(
            {"sku": sku, "canton": canton, "provincia": provincia, "cantidad": cantidad, "minimo": minimo, "mensaje": mensaje}
        )


def _producto(**cambios):
    """Producto de ventas completo, como lo devuelve el repositorio real."""
    producto = {
        "sku": "DEMO-1",
        "nombre": "Producto Demo",
        "descripcion": "Un producto de prueba.",
        "precio": Decimal("24.99"),
        "tiempo_entrega": "2 a 4 días hábiles",
        "metodos_pago_aceptados": "contraentrega, transferencia",
        "max_unidades_por_pedido": 1,
        "activo": True,
    }
    producto.update(cambios)
    return producto


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


def _herramientas(
    lead_repo=None, conv_repo=None, producto_repo=None, pedido_service=None, telegram=None, stock=None, minimos=None
):
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
        # Por defecto "stock desconocido": nunca toca la red en estos tests.
        stock_checker=stock or FakeStockChecker(),
        minimo_repo=minimos or FakeMinimoRepository(),
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


class TestVerFichaProducto:
    def test_devuelve_la_ficha_completa_con_sku_y_maximo_de_unidades(self):
        productos = FakeProductoBotRepository(
            {"DEMO-1": _producto(variantes="negro, blanco", max_unidades_por_pedido=2)}
        )
        herramientas = _herramientas(producto_repo=productos)

        resultado = herramientas.ejecutar(
            "ver_ficha_producto", lead_id=1, conversacion_id=1, entrada={"producto_sku": "DEMO-1"}, id_llamada="toolu_f1"
        )

        assert resultado.id_llamada == "toolu_f1"
        for esperado in ("SKU: DEMO-1", "Producto Demo", "$24.99", "2 a 4 días hábiles", "negro, blanco", "máximas por pedido: 2"):
            assert esperado in resultado.contenido

    def test_acepta_el_nombre_si_el_llm_no_copia_el_sku(self):
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(producto_repo=productos)

        resultado = herramientas.ejecutar(
            "ver_ficha_producto", lead_id=1, conversacion_id=1, entrada={"producto_sku": "producto demo"}, id_llamada="toolu_f2"
        )

        assert "SKU: DEMO-1" in resultado.contenido

    def test_producto_inexistente_devuelve_el_catalogo_disponible(self):
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(producto_repo=productos)

        resultado = herramientas.ejecutar(
            "ver_ficha_producto", lead_id=1, conversacion_id=1, entrada={"producto_sku": "NO-EXISTE"}, id_llamada="toolu_f3"
        )

        assert "no encontré ese producto" in resultado.contenido.lower()
        assert "Producto Demo (DEMO-1)" in resultado.contenido

    def test_un_producto_pausado_no_se_muestra(self):
        productos = FakeProductoBotRepository({"DEMO-1": _producto(activo=False)})
        herramientas = _herramientas(producto_repo=productos)

        resultado = herramientas.ejecutar(
            "ver_ficha_producto", lead_id=1, conversacion_id=1, entrada={"producto_sku": "DEMO-1"}, id_llamada="toolu_f4"
        )

        assert "SKU: DEMO-1" not in resultado.contenido
        assert "no encontré ese producto" in resultado.contenido.lower()
        assert "no hay productos disponibles" in resultado.contenido.lower()


class TestRegistrarProducto:
    def test_el_total_lo_calcula_el_sistema_con_el_precio_del_catalogo(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo"},
            id_llamada="toolu_2",
        )

        assert leads.leads[1]["total"] == Decimal("24.99")
        assert isinstance(leads.leads[1]["total"], Decimal)
        assert leads.leads[1]["cantidad"] == 1
        # Victoria recibe el monto exacto que debe comunicar.
        assert "$24.99" in resultado.contenido

    def test_ignora_el_total_que_envie_el_llm_y_lo_avisa_en_el_log(self, caplog):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        with caplog.at_level("WARNING"):
            herramientas.ejecutar(
                "registrar_producto",
                lead_id=1,
                conversacion_id=1,
                entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "total": 1.00},
                id_llamada="toolu_2a",
            )

        assert leads.leads[1]["total"] == Decimal("24.99")
        assert any("el sistema calculó 24.99" in r.getMessage() for r in caplog.records)

    def test_con_el_mismo_total_del_sistema_no_hay_aviso(self, caplog):
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(producto_repo=productos)

        with caplog.at_level("WARNING"):
            herramientas.ejecutar(
                "registrar_producto",
                lead_id=1,
                conversacion_id=1,
                entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "total": 24.99},
                id_llamada="toolu_2h",
            )

        assert not any("el sistema calculó" in r.getMessage() for r in caplog.records)

    def test_varias_unidades_multiplican_el_precio(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=3)})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": 2},
            id_llamada="toolu_2i",
        )

        assert leads.leads[1]["cantidad"] == 2
        assert leads.leads[1]["total"] == Decimal("49.98")
        assert "2 x Producto Demo" in resultado.contenido
        assert "$49.98" in resultado.contenido

    def test_acepta_la_cantidad_como_texto_o_con_decimales_enteros(self):
        for cantidad in ("2", 2.0, " 2 "):
            leads = FakeLeadRepository()
            productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=3)})
            herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

            herramientas.ejecutar(
                "registrar_producto",
                lead_id=1,
                conversacion_id=1,
                entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": cantidad},
                id_llamada="toolu_2j",
            )

            assert leads.leads[1]["cantidad"] == 2, cantidad

    def test_mas_unidades_que_el_maximo_no_registra_nada(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=1)})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": 2},
            id_llamada="toolu_2k",
        )

        assert "producto_sku" not in leads.leads.get(1, {})
        assert "hasta 1 unidad por pedido" in resultado.contenido

    def test_el_maximo_por_defecto_es_una_unidad_aunque_el_producto_no_lo_traiga(self):
        productos = FakeProductoBotRepository({"DEMO-1": {k: v for k, v in _producto().items() if k != "max_unidades_por_pedido"}})
        herramientas = _herramientas(producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": 2},
            id_llamada="toolu_2l",
        )

        assert "hasta 1 unidad por pedido" in resultado.contenido

    def test_cantidades_invalidas_no_registran_nada(self):
        for invalida in (0, -1, 1.5, "dos", True):
            leads = FakeLeadRepository()
            productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=3)})
            herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

            resultado = herramientas.ejecutar(
                "registrar_producto",
                lead_id=1,
                conversacion_id=1,
                entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": invalida},
                id_llamada="toolu_2m",
            )

            assert "producto_sku" not in leads.leads.get(1, {}), invalida
            assert "número entero" in resultado.contenido, invalida

    def test_corrige_sku_inventado_buscando_por_nombre_en_el_catalogo_real(self):
        """Probado contra la API real: el LLM no siempre copia el SKU tal
        cual aparece en el catálogo -- a veces lo inventa (ej. 'AUD-BT-001'),
        a veces manda un placeholder ('N/A'). Si el sku recibido no
        coincide con ningún producto real, se corrige por nombre (sin
        distinguir tildes/mayúsculas) antes de guardar."""
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository(
            {
                "10-AUDIFONO-INALAM-TIPRO": _producto(
                    sku="10-AUDIFONO-INALAM-TIPRO", nombre="Audifonos Bluetooth inalambricos"
                )
            }
        )
        stock = FakeStockChecker(stock=10)
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos, stock=stock)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "N/A", "producto_nombre": "Audífonos Bluetooth Inalámbricos"},
            id_llamada="toolu_2b",
        )

        assert leads.leads[1]["producto_sku"] == "10-AUDIFONO-INALAM-TIPRO"
        # El stock se consulta con el SKU REAL (el corregido), no con el que inventó el LLM.
        assert stock.consultas == [("10-AUDIFONO-INALAM-TIPRO", False)]

    def test_variante_incluida_se_guarda(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "variante": "negro"},
            id_llamada="toolu_2d",
        )

        assert leads.leads[1]["producto_variante"] == "negro"

    def test_sin_variante_la_columna_queda_sin_tocar(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo"},
            id_llamada="toolu_2e",
        )

        assert leads.leads[1].get("producto_variante") is None

    def test_sin_match_de_ningun_producto_real_no_guarda_nada_y_devuelve_catalogo(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "N/A", "producto_nombre": "Algo que no existe"},
            id_llamada="toolu_2c",
        )

        assert 1 not in leads.leads or "producto_sku" not in leads.leads.get(1, {})
        assert "no encontré ese producto" in resultado.contenido.lower()
        assert "Producto Demo" in resultado.contenido
        assert "DEMO-1" in resultado.contenido

    def test_un_producto_pausado_no_se_registra(self):
        """Hueco H6: pausar un producto debe detener las ventas nuevas de verdad."""
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository(
            {
                "VIEJO": _producto(sku="VIEJO", nombre="Producto Viejo", activo=False),
                "NUEVO": _producto(sku="NUEVO", nombre="Producto Nuevo"),
            }
        )
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        # El SKU exacto es el del pausado; el nombre es el de OTRO producto activo:
        # no se debe "corregir" hacia ese otro producto.
        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "VIEJO", "producto_nombre": "Producto Nuevo"},
            id_llamada="toolu_2n",
        )

        assert "producto_sku" not in leads.leads.get(1, {})
        assert "ya no está disponible" in resultado.contenido
        assert "Producto Nuevo (NUEVO)" in resultado.contenido

    def test_stock_parcial_no_registra_y_ofrece_lo_que_queda(self):
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=3)})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos, stock=FakeStockChecker(stock=1))

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo", "cantidad": 2},
            id_llamada="toolu_2o",
        )

        assert "producto_sku" not in leads.leads.get(1, {})
        assert "solo quedan 1 unidad" in resultado.contenido.lower()

    def test_producto_agotado_frena_la_venta_y_avisa_a_una_persona(self):
        leads = FakeLeadRepository(leads={1: {"telefono": "593987654321"}})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(
            lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, telegram=telegram, stock=FakeStockChecker(stock=0)
        )

        resultado = herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=5,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo"},
            id_llamada="toolu_2p",
        )

        assert "producto_sku" not in leads.leads[1]
        assert conversaciones.estados[5] == "escalada"
        telegram.notificar_escalado.assert_called_once()
        assert "Producto sin stock" in telegram.notificar_escalado.call_args.args[2]
        assert "agotado" in resultado.contenido.lower()

    def test_si_no_se_pudo_consultar_el_stock_la_venta_sigue(self):
        """Falla abierto: Rocketfy rechazaría el pedido al confirmar si de verdad no hay."""
        leads = FakeLeadRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos, stock=FakeStockChecker(stock=None))

        herramientas.ejecutar(
            "registrar_producto",
            lead_id=1,
            conversacion_id=1,
            entrada={"producto_sku": "DEMO-1", "producto_nombre": "Producto Demo"},
            id_llamada="toolu_2q",
        )

        assert leads.leads[1]["producto_sku"] == "DEMO-1"


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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, telegram=telegram)

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
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, telegram=telegram)

        resultado = herramientas.ejecutar(
            "cerrar_venta", lead_id=1, conversacion_id=9, entrada={}, id_llamada="toolu_9"
        )

        assert conversaciones.estados[9] == "escalada"
        assert "problema técnico" in resultado.contenido.lower()


class TestCerrarVentaProtecciones:
    """Fase A del plan de gestión de productos: última revisión antes de crear
    un pedido REAL. Ninguno de estos casos debe llegar a Rocketfy."""

    def _mock_rocketfy_ok(self, id_rocketfy=6001):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": id_rocketfy, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 1, "code": 200, "message": "ok"}, status=200
        )

    @responses.activate
    def test_varias_unidades_viajan_en_la_linea_y_el_total_es_precio_por_cantidad(self):
        self._mock_rocketfy_ok()
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, cantidad=2, total=Decimal("49.98"))
        leads = FakeLeadRepository(leads={1: lead})
        productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=3)})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_c1")

        payload_enviado = json.loads(responses.calls[0].request.body)
        assert json.loads(payload_enviado["order_details"])[0]["quantity"] == 2
        assert payload_enviado["total"] == "49.98"
        assert "pedido confirmado" in resultado.contenido.lower()

    @responses.activate
    def test_sin_cantidad_en_el_lead_se_envia_una_unidad(self):
        self._mock_rocketfy_ok()
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})  # sin la clave "cantidad"
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_c2")

        payload_enviado = json.loads(responses.calls[0].request.body)
        assert json.loads(payload_enviado["order_details"])[0]["quantity"] == 1

    @responses.activate
    def test_producto_pausado_frena_el_cierre_sin_llamar_a_rocketfy(self):
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(activo=False)})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, telegram=telegram)

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=4, entrada={}, id_llamada="toolu_c3")

        assert len(responses.calls) == 0
        assert conversaciones.estados[4] == "escalada"
        assert "ya no está disponible" in telegram.notificar_escalado.call_args.args[2]
        assert "no se pudo cerrar la venta" in resultado.contenido.lower()
        assert leads.leads[1].get("estado") != "despachado"

    @responses.activate
    def test_producto_borrado_frena_el_cierre_sin_llamar_a_rocketfy(self):
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=FakeProductoBotRepository())

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=4, entrada={}, id_llamada="toolu_c3b")

        assert len(responses.calls) == 0
        assert conversaciones.estados[4] == "escalada"

    @responses.activate
    def test_precio_que_cambio_despues_de_cotizar_frena_el_cierre(self):
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})  # cotizado a 24.99
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(precio=Decimal("29.99"))})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, telegram=telegram)

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=4, entrada={}, id_llamada="toolu_c4")

        assert len(responses.calls) == 0
        assert conversaciones.estados[4] == "escalada"
        motivo = telegram.notificar_escalado.call_args.args[2]
        assert "cotizado $24.99" in motivo and "actual $29.99" in motivo
        assert "el precio" in resultado.contenido.lower()

    @responses.activate
    def test_cantidad_mayor_al_maximo_actual_frena_el_cierre(self):
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, cantidad=3, total=Decimal("74.97"))
        leads = FakeLeadRepository(leads={1: lead})
        conversaciones = FakeConversacionRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(max_unidades_por_pedido=2)})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=4, entrada={}, id_llamada="toolu_c5")

        assert len(responses.calls) == 0
        assert conversaciones.estados[4] == "escalada"

    @responses.activate
    def test_sin_stock_suficiente_al_cerrar_frena_el_cierre_con_dato_fresco(self):
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        stock = FakeStockChecker(stock=0)
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, stock=stock)

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=4, entrada={}, id_llamada="toolu_c6")

        assert len(responses.calls) == 0
        assert conversaciones.estados[4] == "escalada"
        # Justo antes de crear un pedido real se pide el stock SIN caché.
        assert stock.consultas == [("DEMO-1", True)]
        assert "el stock" in resultado.contenido.lower()

    @responses.activate
    def test_si_no_se_pudo_consultar_el_stock_al_cerrar_el_pedido_sigue(self):
        self._mock_rocketfy_ok()
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos, stock=FakeStockChecker(stock=None))

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=1, entrada={}, id_llamada="toolu_c7")

        assert leads.leads[1]["estado"] == "despachado"


class TestMinimosObservadosDeRocketfy:
    MENSAJE_REAL = "El importe mínimo del pedido debe ser el del valor de los productos + el costo del envío ($18.47)"

    @responses.activate
    def test_guarda_el_minimo_que_exigio_rocketfy_y_aun_asi_escala(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 7001, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 0, "code": 422, "message": self.MENSAJE_REAL}, status=200
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        minimos = FakeMinimoRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, minimos=minimos)

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=8, entrada={}, id_llamada="toolu_m1")

        assert conversaciones.estados[8] == "escalada"
        assert "problema técnico" in resultado.contenido.lower()
        assert len(minimos.guardados) == 1
        guardado = minimos.guardados[0]
        assert guardado["minimo"] == Decimal("18.47")
        assert (guardado["sku"], guardado["canton"], guardado["provincia"], guardado["cantidad"]) == (
            "DEMO-1", "QUITO", "Pichincha", 1,
        )
        assert "importe mínimo" in guardado["mensaje"]

    @responses.activate
    def test_otro_error_de_rocketfy_no_guarda_nada(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 7002, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 0, "code": 422, "message": "Sin cobertura para esta zona"}, status=200
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        minimos = FakeMinimoRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(lead_repo=leads, producto_repo=productos, minimos=minimos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=8, entrada={}, id_llamada="toolu_m2")

        assert minimos.guardados == []

    @responses.activate
    def test_el_error_local_del_recaudo_minimo_no_se_confunde_con_una_observacion_de_rocketfy(self):
        """El mensaje local ("... recaudo mínimo que exige Rocketfy ... ($10.00)") también
        menciona un mínimo y un monto: solo cuentan los errores que vienen de Rocketfy."""
        lead = dict(LEAD_COMPLETO_CONTRAENTREGA, total=Decimal("5.00"))
        leads = FakeLeadRepository(leads={1: lead})
        conversaciones = FakeConversacionRepository()
        minimos = FakeMinimoRepository()
        productos = FakeProductoBotRepository({"DEMO-1": _producto(precio=Decimal("5.00"))})
        herramientas = _herramientas(lead_repo=leads, conv_repo=conversaciones, producto_repo=productos, minimos=minimos)

        herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=8, entrada={}, id_llamada="toolu_m3")

        assert len(responses.calls) == 0
        assert conversaciones.estados[8] == "escalada"
        assert minimos.guardados == []

    @responses.activate
    def test_si_falla_guardar_el_minimo_el_escalado_sigue_funcionando(self):
        responses.add(
            responses.POST,
            f"{BASE_URL}/orders/create",
            json={"ok": 1, "code": 200, "message": "ok", "id": 7003, "products_stock": [{"id": 1, "stock": 10}]},
            status=200,
        )
        responses.add(
            responses.POST, f"{BASE_URL}/orders/confirm", json={"ok": 0, "code": 422, "message": self.MENSAJE_REAL}, status=200
        )
        leads = FakeLeadRepository(leads={1: dict(LEAD_COMPLETO_CONTRAENTREGA)})
        conversaciones = FakeConversacionRepository()
        telegram = MagicMock()
        productos = FakeProductoBotRepository({"DEMO-1": _producto()})
        herramientas = _herramientas(
            lead_repo=leads,
            conv_repo=conversaciones,
            producto_repo=productos,
            telegram=telegram,
            minimos=FakeMinimoRepository(falla=True),
        )

        resultado = herramientas.ejecutar("cerrar_venta", lead_id=1, conversacion_id=8, entrada={}, id_llamada="toolu_m4")

        assert conversaciones.estados[8] == "escalada"
        telegram.notificar_escalado.assert_called_once()
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
        telegram.notificar_escalado.assert_called_once()
        assert telegram.notificar_escalado.call_args.args == (3, "WhatsApp · 593987654321", "Cliente pidió hablar con una persona")
        assert "origen" in telegram.notificar_escalado.call_args.kwargs  # de dónde viene el cliente, para el aviso
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
