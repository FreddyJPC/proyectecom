"""
Victoria con productos PROPIOS (ADR-012): envío por producto, avisos de gestión y cierre manual.

Se usan los dobles en memoria de «Probar con Victoria» (simulacion.py): son los mismos repositorios que ve el
cerebro real, sin base de datos. Lo que SÍ toca la base (la transacción del cierre) se prueba aparte en
tests/unit/routes/ventas/test_repository.py. Aquí se vigila sobre todo que un producto propio NUNCA llegue a Rocketfy.
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.routes.productos_bot.simulacion import (
    ConversacionesEnMemoria,
    EntregasEnEnsayo,
    GestionEnEnsayo,
    LeadsEnMemoria,
    MensajesEnMemoria,
    ProductosEnEnsayo,
    StockEnEnsayo,
    TelegramGrabador,
    VentasEnEnsayo,
    lead_inicial,
)
from src.routes.whatsapp.tools import HerramientasVictoria

PROPIO = {
    "id": 2, "sku": "PROP-0001", "nombre": "Zapatos de cuero", "descripcion": "Hechos a mano.",
    "precio": Decimal("30.00"), "variantes": "talla 38 a 42", "tiempo_entrega": "2 días",
    "metodos_pago_aceptados": "contraentrega, transferencia", "preguntas_frecuentes": None, "temas_no_responder": None,
    "max_unidades_por_pedido": 2, "activo": True, "estado": "activo", "proveedor_id": 2, "proveedor_clave": "propio",
    "proveedor_cierre": "manual", "categoria_id": 3, "categoria_nombre": "Calzado", "costo_rocketfy": None,
    "costo_propio": Decimal("18.00"), "controla_stock": True, "stock_ultimo": 5, "envio_incluido": False,
    "costo_flete_estimado": None, "imagen_url": None,
}
ROCKETFY = {
    **PROPIO, "id": 1, "sku": "R-1", "nombre": "Audífonos", "precio": Decimal("24.99"), "proveedor_id": 1,
    "proveedor_clave": "rocketfy", "proveedor_cierre": "rocketfy", "categoria_id": None, "categoria_nombre": None,
    "costo_rocketfy": Decimal("12.00"), "costo_propio": None, "envio_incluido": True, "max_unidades_por_pedido": 1,
}


def _opcion(id, nombre, tipo="envio", costo="2.00", cantones=(), resto=False, direccion=None, negocio=None, activo=True):
    return {
        "id": id, "producto_sku": "PROP-0001", "nombre": nombre, "tipo": tipo, "costo_cliente": Decimal(costo),
        "costo_negocio": Decimal(negocio) if negocio else None, "cantones": list(cantones), "provincias": [],
        "resto_del_pais": resto, "direccion_retiro": direccion, "tiempo_entrega": None, "activo": activo, "orden": id,
    }


ENTREGAS = [
    _opcion(1, "Envío en Cuenca", cantones=["Cuenca"]),
    _opcion(2, "Retiro en tienda", tipo="retiro", costo="0.00", direccion="Calle Larga 1-23"),
    _opcion(3, "Envío al resto del país", costo="5.00", resto=True),
]


class Escena:
    """Una conversación de prueba lista para ejecutar herramientas."""

    def __init__(self, producto=PROPIO, entregas=ENTREGAS, lead=None):
        self.lead = {**lead_inicial(), **(lead or {})}
        self.conversaciones = ConversacionesEnMemoria(desde_anuncio=False)
        self.leads = LeadsEnMemoria(self.lead)
        self.telegram = TelegramGrabador()
        self.gestion = GestionEnEnsayo(self.telegram)
        self.ventas = VentasEnEnsayo(self.lead, self.gestion, self.conversaciones)
        self.pedidos = MagicMock(name="PedidoService")
        self.productos = ProductosEnEnsayo(producto)
        self.herramientas = HerramientasVictoria(
            lead_repo=self.leads, conversacion_repo=self.conversaciones, producto_repo=self.productos,
            pedido_service=self.pedidos, telegram_notifier=self.telegram, stock_checker=StockEnEnsayo(None),
            minimo_repo=MagicMock(), mensaje_repo=MensajesEnMemoria([], "hola"), canales=MagicMock(),
            enviar_fotos=False, entrega_repo=EntregasEnEnsayo(entregas), gestion_service=self.gestion, ventas_service=self.ventas,
        )

    def usar(self, nombre, **entrada):
        return self.herramientas.ejecutar(nombre, 1, 1, entrada, "id-1").contenido

    def registrar_producto(self, cantidad=2, sku="PROP-0001", nombre="Zapatos de cuero", **extra):
        return self.usar("registrar_producto", producto_sku=sku, producto_nombre=nombre, cantidad=cantidad, **extra)

    def datos_completos(self, canton="Cuenca", provincia="Azuay"):
        self.usar("guardar_datos_cliente", nombre_cliente="Ana", direccion="Calle 1 y Av. 2", canton=canton, provincia=provincia)


class TestRegistrarProductoPropio:
    def test_con_envio_aparte_el_total_es_solo_el_subtotal_y_se_le_dice_a_victoria(self):
        e = Escena()
        mensaje = e.registrar_producto(cantidad=2)

        assert "Subtotal: $60.00, SIN el envío" in mensaje and "registrar_entrega" in mensaje
        assert (e.lead["total"], e.lead["subtotal"]) == (Decimal("60.00"), Decimal("60.00"))

    def test_con_envio_incluido_el_mensaje_es_el_de_siempre(self):
        e = Escena(producto={**PROPIO, "envio_incluido": True})
        assert "Total a cobrar: $60.00" in e.registrar_producto(cantidad=2)

    def test_el_stock_se_mira_en_la_ficha_propia_no_en_rocketfy(self):
        e = Escena(producto={**PROPIO, "stock_ultimo": 1, "max_unidades_por_pedido": 5})
        mensaje = e.registrar_producto(cantidad=2)
        assert "Solo quedan 1 unidad" in mensaje
        e.pedidos.assert_not_called()

    def test_sin_control_de_stock_no_hay_limite_de_unidades_en_la_ficha(self):
        e = Escena(producto={**PROPIO, "controla_stock": False, "stock_ultimo": None})
        assert "Producto registrado" in e.registrar_producto(cantidad=2)

    def test_sin_stock_escala_y_el_motivo_no_menciona_rocketfy(self):
        e = Escena(producto={**PROPIO, "stock_ultimo": 0})
        e.registrar_producto(cantidad=1)
        assert e.conversaciones.escalada
        assert any("Producto sin stock:" in a["texto"] and "Rocketfy" not in a["texto"] for a in e.telegram.avisos)


class TestRegistrarEntrega:
    def test_pide_primero_el_producto(self):
        assert "registrar_producto" in Escena().usar("registrar_entrega")

    def test_pide_el_canton_si_no_se_sabe(self):
        e = Escena()
        e.registrar_producto()
        assert "cantón y la provincia" in e.usar("registrar_entrega")

    def test_lista_solo_las_opciones_que_aplican_al_destino(self):
        e = Escena()
        e.registrar_producto()
        e.datos_completos(canton="Cuenca", provincia="Azuay")

        texto = e.usar("registrar_entrega")

        assert "1) Envío en Cuenca: $2.00" in texto and "2) Retiro en tienda" in texto
        assert "resto del país" not in texto and "subtotal de los productos: $60.00" in texto

    def test_fuera_de_cuenca_ofrece_el_resto_del_pais(self):
        e = Escena()
        e.registrar_producto()
        e.datos_completos(canton="Quito", provincia="Pichincha")
        texto = e.usar("registrar_entrega")
        assert "Envío al resto del país: $5.00" in texto and "Envío en Cuenca" not in texto

    def test_elegir_una_opcion_calcula_el_total_con_el_envio(self):
        e = Escena()
        e.registrar_producto(cantidad=2)
        e.datos_completos()

        mensaje = e.usar("registrar_entrega", opcion="1")

        assert "Total a cobrar: $62.00" in mensaje and "productos $60.00 + envío $2.00" in mensaje
        assert (e.lead["total"], e.lead["costo_envio"], e.lead["entrega_nombre"], e.lead["entrega_opcion_id"]) == (
            Decimal("62.00"), Decimal("2.00"), "Envío en Cuenca", 1,
        )

    def test_cambiar_de_opcion_recalcula_desde_el_subtotal_no_acumula(self):
        e = Escena()
        e.registrar_producto(cantidad=2)
        e.datos_completos()
        e.usar("registrar_entrega", opcion="1")
        e.usar("registrar_entrega", opcion="retiro")
        assert e.lead["total"] == Decimal("60.00") and e.lead["entrega_tipo"] == "retiro"

    def test_una_opcion_que_no_existe_no_cambia_nada(self):
        e = Escena()
        e.registrar_producto()
        e.datos_completos()
        assert "No reconocí esa opción" in e.usar("registrar_entrega", opcion="paloma mensajera")
        assert e.lead["entrega_opcion_id"] is None

    def test_cambiar_cantidad_o_producto_borra_la_entrega_elegida(self):
        e = Escena()
        e.registrar_producto(cantidad=1)
        e.datos_completos()
        e.usar("registrar_entrega", opcion="1")
        e.registrar_producto(cantidad=2)
        assert e.lead["entrega_opcion_id"] is None and e.lead["total"] == Decimal("60.00")

    def test_sin_cobertura_avisa_al_dueno_y_pasa_la_conversacion(self):
        solo_cuenca = [ENTREGAS[0]]
        e = Escena(entregas=solo_cuenca)
        e.registrar_producto()
        e.datos_completos(canton="Quito", provincia="Pichincha")

        mensaje = e.usar("registrar_entrega")

        assert "no tiene una entrega disponible para Quito, Pichincha" in mensaje
        assert e.conversaciones.en_gestion
        assert [s["tipo"] for s in e.gestion.solicitudes] == ["sin_cobertura"]
        assert any("Destino sin cobertura" in a["texto"] for a in e.telegram.avisos)

    def test_con_envio_incluido_no_hay_nada_que_elegir(self):
        e = Escena(producto={**PROPIO, "envio_incluido": True})
        e.registrar_producto(cantidad=1)
        assert "incluye el envío" in e.usar("registrar_entrega")

    def test_cambiar_de_canton_despues_de_elegir_borra_la_entrega_que_ya_no_aplica(self):
        e = Escena()
        e.registrar_producto(cantidad=1)
        e.datos_completos(canton="Cuenca", provincia="Azuay")
        e.usar("registrar_entrega", opcion="1")

        respuesta = e.usar("guardar_datos_cliente", canton="Quito", provincia="Pichincha")

        assert "ya no aplica al nuevo destino" in respuesta
        assert e.lead["entrega_opcion_id"] is None and e.lead["total"] == Decimal("30.00")

    def test_cambiar_de_canton_a_otro_que_tambien_aplica_conserva_la_entrega(self):
        e = Escena()
        e.registrar_producto(cantidad=1)
        e.datos_completos(canton="Quito", provincia="Pichincha")
        e.usar("registrar_entrega", opcion="Envío al resto del país")
        assert e.usar("guardar_datos_cliente", canton="Loja", provincia="Loja") == "Datos guardados correctamente."
        assert e.lead["entrega_opcion_id"] == 3


class TestSolicitarGestion:
    def test_quiere_comprar_avisa_pero_victoria_sigue(self):
        e = Escena()
        mensaje = e.usar("solicitar_gestion", tipo="quiere_comprar", detalle="lo quiere en talla 40")

        assert "sigue tomando los datos" in mensaje and not e.conversaciones.en_gestion
        assert e.telegram.avisos == [{"canal": "telegram", "texto": "Cierre previo: Quiere comprar. lo quiere en talla 40"}]

    def test_quiere_ver_el_producto_pasa_la_conversacion_al_dueno(self):
        e = Escena()
        mensaje = e.usar("solicitar_gestion", tipo="quiere_ver_producto", detalle="quiere verlo mañana")

        assert "último mensaje" in mensaje and e.conversaciones.en_gestion

    def test_no_se_avisa_dos_veces_por_lo_mismo_pero_si_al_subir_de_categoria(self):
        e = Escena()
        e.usar("solicitar_gestion", tipo="quiere_comprar")
        e.usar("solicitar_gestion", tipo="quiere_pagar")
        assert len(e.telegram.avisos) == 1
        e.usar("solicitar_gestion", tipo="quiere_negociar", detalle="pide rebaja")
        assert len(e.telegram.avisos) == 2 and e.conversaciones.en_gestion

    def test_un_tipo_desconocido_cae_en_otro_y_pasa_al_dueno(self):
        e = Escena()
        e.usar("solicitar_gestion", tipo="inventado")
        assert e.gestion.solicitudes[0]["tipo"] == "otro" and e.conversaciones.en_gestion

    def test_un_producto_de_rocketfy_no_usa_esta_herramienta(self):
        e = Escena(producto=ROCKETFY)
        e.registrar_producto(cantidad=1, sku="R-1", nombre="Audífonos")
        assert "se cierra solo" in e.usar("solicitar_gestion", tipo="quiere_comprar")
        assert e.gestion.solicitudes == [] and e.telegram.avisos == []


def _aviso_de_pedido(e):
    """El aviso «Pedido cerrado» (puede haber otros, p. ej. «quedan pocas unidades»)."""
    return next(a["texto"] for a in e.telegram.avisos if "Pedido cerrado" in a["texto"])


def _listo_para_cerrar(e, opcion="1", metodo="contraentrega", cantidad=2):
    e.registrar_producto(cantidad=cantidad)
    e.datos_completos()
    if opcion is not None:
        e.usar("registrar_entrega", opcion=opcion)
    e.usar("registrar_metodo_pago", metodo_pago=metodo)


class TestCerrarVentaPropia:
    def test_pasa_el_pedido_al_dueno_y_nunca_llama_a_rocketfy(self):
        e = Escena()
        _listo_para_cerrar(e)

        mensaje = e.usar("cerrar_venta")

        assert "¡Pedido registrado!" in mensaje and "último mensaje" in mensaje
        e.pedidos.crear_y_confirmar.assert_not_called()
        assert e.pedidos.method_calls == []  # ni crear ni confirmar ni consultar nada
        assert e.lead["estado"] == "por_gestionar" and e.conversaciones.en_gestion
        assert e.lead["id_pedido_rocketfy"] is None

    def test_avisa_por_telegram_con_todos_los_datos(self):
        e = Escena()
        _listo_para_cerrar(e)
        e.usar("cerrar_venta")

        texto = _aviso_de_pedido(e)
        assert "Pedido cerrado, gestionar envío" in texto
        assert "2 x Zapatos de cuero" in texto and "total $62.00" in texto and "entrega: Envío en Cuenca" in texto
        assert "pago: contraentrega" in texto and "Ana" in texto

    def test_la_venta_guarda_precio_costo_y_envio_congelados(self):
        e = Escena()
        _listo_para_cerrar(e)
        e.usar("cerrar_venta")

        venta = e.ventas.venta
        assert (venta["subtotal"], venta["costo_envio_cliente"], venta["total"]) == (Decimal("60.00"), Decimal("2.00"), Decimal("62.00"))
        assert venta["costo_productos"] == Decimal("36.00")
        assert venta["lineas"][0]["categoria_nombre"] == "Calzado"

    def test_con_transferencia_no_espera_comprobante_y_lo_deja_dicho_al_dueno(self):
        e = Escena()
        _listo_para_cerrar(e, metodo="transferencia")

        assert e.lead["estado"] == "recopilando_datos"  # no quedó «esperando_pago»
        assert not e.conversaciones.esperando_pago
        assert "¡Pedido registrado!" in e.usar("cerrar_venta")
        assert "pago: transferencia" in _aviso_de_pedido(e)

    def test_si_falta_elegir_la_entrega_la_pide_y_no_cierra(self):
        e = Escena()
        _listo_para_cerrar(e, opcion=None)
        assert "Falta elegir la entrega" in e.usar("cerrar_venta")
        assert e.lead["estado"] != "por_gestionar" and e.ventas.venta is None

    def test_con_envio_incluido_no_hace_falta_elegir_entrega(self):
        e = Escena(producto={**PROPIO, "envio_incluido": True})
        _listo_para_cerrar(e, opcion=None)
        assert "¡Pedido registrado!" in e.usar("cerrar_venta")
        assert e.ventas.venta["entrega_nombre"] == "Envío incluido en el precio"

    def test_faltan_datos(self):
        e = Escena()
        e.registrar_producto()
        assert "Faltan datos" in e.usar("cerrar_venta")

    def test_no_cierra_dos_veces(self):
        e = Escena()
        _listo_para_cerrar(e)
        e.usar("cerrar_venta")
        assert "ya quedó registrado" in e.usar("cerrar_venta")

    def test_tras_cancelar_la_venta_un_pedido_nuevo_lo_gestiona_el_dueno_y_no_se_cierra_otra_venta(self):
        # El dueño canceló el pedido anterior de esta conversación (el lead quedó «cancelado»). Cada lead tiene una
        # sola venta, así que si el cliente quiere comprar otra vez no se cierra una segunda: se avisa al dueño.
        e = Escena()
        _listo_para_cerrar(e)
        e.lead["estado"] = "cancelado"
        e.ventas.venta = None

        mensaje = e.usar("cerrar_venta")

        assert "se canceló" in mensaje and "dueño" in mensaje and "último mensaje" in mensaje
        assert e.ventas.venta is None  # no se cerró otra venta
        e.pedidos.crear_y_confirmar.assert_not_called()
        assert e.pedidos.method_calls == []
        assert e.gestion.solicitudes[-1]["tipo"] == "otro" and "nuevo pedido" in e.gestion.solicitudes[-1]["detalle"]
        assert e.conversaciones.en_gestion  # la conversación pasa al dueño: no se pierde el cliente

    def test_si_el_precio_cambio_se_escala_y_no_se_cierra(self):
        e = Escena()
        _listo_para_cerrar(e)
        e.productos._producto["precio"] = Decimal("35.00")

        mensaje = e.usar("cerrar_venta")

        assert "inconveniente con el precio" in mensaje and e.conversaciones.escalada and e.ventas.venta is None

    def test_si_la_opcion_de_entrega_cambio_de_costo_se_escala(self):
        entregas = [dict(o) for o in ENTREGAS]
        e = Escena(entregas=entregas)
        _listo_para_cerrar(e)
        e.herramientas._entregas = EntregasEnEnsayo([{**entregas[0], "costo_cliente": Decimal("3.00")}, *entregas[1:]])

        assert "inconveniente con la entrega" in e.usar("cerrar_venta")
        assert e.conversaciones.escalada and e.ventas.venta is None

    def test_si_la_opcion_de_entrega_se_desactivo_se_escala(self):
        entregas = [dict(o) for o in ENTREGAS]
        e = Escena(entregas=entregas)
        _listo_para_cerrar(e)
        e.herramientas._entregas = EntregasEnEnsayo([{**entregas[0], "activo": False}, *entregas[1:]])
        assert "inconveniente con la entrega" in e.usar("cerrar_venta")

    def test_si_el_stock_cambio_y_ya_no_alcanza_se_escala(self):
        e = Escena()
        _listo_para_cerrar(e, cantidad=2)
        e.productos._producto["stock_ultimo"] = 1
        assert "inconveniente con el stock" in e.usar("cerrar_venta")
        assert e.conversaciones.escalada

    def test_la_ultima_unidad_avisa_que_se_agoto(self):
        e = Escena(producto={**PROPIO, "stock_ultimo": 2})
        _listo_para_cerrar(e, cantidad=2)
        e.usar("cerrar_venta")
        assert any("Producto agotado" in a["texto"] for a in e.telegram.avisos)

    def test_si_la_base_falla_al_cerrar_se_escala_en_vez_de_perder_el_pedido(self):
        e = Escena()
        _listo_para_cerrar(e)
        e.ventas.cerrar_manual = MagicMock(side_effect=RuntimeError("base caída"))

        mensaje = e.usar("cerrar_venta")

        assert "problema técnico" in mensaje and e.conversaciones.escalada


class TestRocketfySigueIgual:
    """Un producto de Rocketfy conserva su camino: pedido real en Rocketfy, comprobante si es transferencia."""

    def _escena(self, **cambios):
        e = Escena(producto={**ROCKETFY, **cambios}, entregas=[])
        e.ventas = MagicMock(name="VentasService")
        e.herramientas._ventas = e.ventas
        e.pedidos.crear_y_confirmar.return_value = SimpleNamespace(id_local=11, id_rocketfy=99)
        return e

    def _preparar(self, e, metodo="contraentrega"):
        e.registrar_producto(cantidad=1, sku="R-1", nombre="Audífonos")
        e.datos_completos()
        e.usar("registrar_metodo_pago", metodo_pago=metodo)

    def test_crea_el_pedido_en_rocketfy_y_deja_la_foto_de_la_venta(self):
        e = self._escena()
        self._preparar(e)

        assert "¡Pedido confirmado!" in e.usar("cerrar_venta")

        e.pedidos.crear_y_confirmar.assert_called_once()
        assert e.lead["estado"] == "despachado" and e.lead["id_pedido_rocketfy"] == 99
        e.ventas.registrar_venta_rocketfy.assert_called_once()
        lead, producto, _conv, entrega = e.ventas.registrar_venta_rocketfy.call_args.args
        assert lead["id_pedido_rocketfy"] == 99 and producto["sku"] == "R-1" and entrega is None
        assert not e.conversaciones.en_gestion

    def test_si_guardar_la_foto_de_la_venta_falla_el_pedido_igual_queda_confirmado(self):
        e = self._escena()
        self._preparar(e)
        e.ventas.registrar_venta_rocketfy.side_effect = RuntimeError("base caída")

        assert "¡Pedido confirmado!" in e.usar("cerrar_venta")
        assert e.lead["estado"] == "despachado"

    def test_nunca_crea_dos_pedidos_para_el_mismo_lead(self):
        e = self._escena()
        self._preparar(e)
        e.usar("cerrar_venta")

        assert "ya quedó registrado" in e.usar("cerrar_venta")
        e.pedidos.crear_y_confirmar.assert_called_once()

    def test_la_transferencia_sigue_esperando_el_comprobante(self):
        e = self._escena()
        self._preparar(e, metodo="transferencia")

        assert e.lead["estado"] == "esperando_pago" and e.conversaciones.esperando_pago
        assert "foto del comprobante" in e.usar("cerrar_venta")
        e.pedidos.crear_y_confirmar.assert_not_called()

    def test_con_envio_cobrado_aparte_el_total_que_va_a_rocketfy_incluye_el_envio(self):
        entregas = [_opcion(1, "Envío nacional", costo="4.00", resto=True)]
        e = Escena(producto={**ROCKETFY, "envio_incluido": False}, entregas=entregas)
        e.ventas = MagicMock()
        e.herramientas._ventas = e.ventas
        e.pedidos.crear_y_confirmar.return_value = SimpleNamespace(id_local=11, id_rocketfy=99)
        e.registrar_producto(cantidad=1, sku="R-1", nombre="Audífonos")
        e.datos_completos(canton="Quito", provincia="Pichincha")
        e.usar("registrar_entrega", opcion="1")
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")

        assert "¡Pedido confirmado!" in e.usar("cerrar_venta")

        dto = e.pedidos.crear_y_confirmar.call_args.args[0]
        assert dto.total == Decimal("28.99")  # 24.99 + 4.00


class TestMetodoDePagoYFicha:
    def test_ver_ficha_incluye_el_envio_y_el_cierre_manual(self):
        e = Escena()
        ficha = e.usar("ver_ficha_producto", producto_sku="PROP-0001")
        assert "se cobra aparte" in ficha and "Envío en Cuenca" in ficha
        assert "Cierre de la venta: MANUAL" in ficha and "solicitar_gestion" in ficha

    def test_ver_ficha_de_rocketfy_no_habla_de_cierre_manual(self):
        e = Escena(producto=ROCKETFY, entregas=[])
        ficha = e.usar("ver_ficha_producto", producto_sku="R-1")
        assert "INCLUIDO en el precio" in ficha and "MANUAL" not in ficha
