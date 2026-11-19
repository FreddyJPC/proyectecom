"""
Victoria con el motor de precios (ADR-017): precio por transferencia, precio por cantidad, regateo, varios productos y ofertas,
de punta a punta por las herramientas reales, con repositorios en memoria (sin base de datos ni Rocketfy).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.config.parametros import parametros
from src.routes.ajustes.dto import AjustesNegocio
from src.routes.precios.servicio import CotizadorServicio
from src.routes.productos_bot.simulacion import (
    ConversacionesEnMemoria,
    EntregasEnEnsayo,
    GestionEnEnsayo,
    LeadsEnMemoria,
    MensajesEnMemoria,
    StockEnEnsayo,
    TelegramGrabador,
    VentasEnEnsayo,
    lead_inicial,
)
from src.routes.whatsapp.tools import HerramientasVictoria

D = Decimal
AHORA = datetime.now(timezone.utc)


def _producto(sku, nombre, precio, **extra):
    base = {
        "id": 1, "sku": sku, "nombre": nombre, "descripcion": "", "precio": D(precio), "variantes": None, "tiempo_entrega": "2 días",
        "metodos_pago_aceptados": "contraentrega, transferencia", "max_unidades_por_pedido": 3, "activo": True, "estado": "activo",
        "proveedor_id": 1, "proveedor_clave": "rocketfy", "proveedor_cierre": "rocketfy", "costo_rocketfy": D("8.00"), "costo_propio": None,
        "controla_stock": False, "stock_ultimo": None, "envio_incluido": True, "categoria_id": None, "categoria_nombre": None,
    }
    base.update(extra)
    return base


LINTERNA = _producto("LIN", "Linterna", "25.00")
CARGADOR = _producto("CAR", "Cargador", "12.00")
PROPIO = _producto("PROP-1", "Zapatos", "30.00", proveedor_id=2, proveedor_clave="propio", proveedor_cierre="manual")


class ProductosEnMemoria:
    def __init__(self, *productos):
        self.filas = {p["sku"]: dict(p) for p in productos}

    def obtener_por_sku(self, sku):
        fila = self.filas.get(sku)
        return dict(fila) if fila else None

    def listar_activos(self):
        return [dict(p) for p in self.filas.values() if p.get("activo", True)]

    def obtener_por_id_anuncio(self, id_anuncio):
        return None


class PreciosEnMemoria:
    def __init__(self, escalas=None, ofertas=None, vinculos=None, ventas_oferta=0):
        self.escalas = escalas or {}
        self._ofertas = ofertas or {}
        self.vinculos = vinculos or {}
        self.ventas_oferta = ventas_oferta

    def escalas_de(self, skus):
        return {s: self.escalas[s] for s in skus if s in self.escalas}

    def transferencia_negocio(self):
        return {"tipo": None, "valor": None}

    def ofertas(self, ids=None, incluir_archivadas=False):
        return [dict(o) for i, o in self._ofertas.items() if ids is None or i in set(ids)]

    def ofertas_publicas(self):
        return [dict(o) for o in self._ofertas.values() if o["visibilidad"] == "publica" and o["estado"] == "activa"]

    def vinculo_de_anuncio(self, id_anuncio):
        return self.vinculos.get(id_anuncio)

    def ventas_de_oferta(self, oferta_id, contacto_id=None):
        return self.ventas_oferta


class AjustesFijos:
    def obtener_ajustes(self):
        return AjustesNegocio(confirmado=True, margen_minimo_pct=D("25"), envio_estimado=D("4.00"))


def _oferta(**cambios):
    base = {
        "id": 7, "nombre": "Linterna + cargador", "precio": D("30.00"), "envio_incluido": True, "desde": None, "hasta": None,
        "cupo": None, "maximo_por_cliente": 2, "visibilidad": "anuncio", "regateo_tipo": None, "regateo_valor": None,
        "transferencia_tipo": None, "transferencia_valor": None, "estado": "activa",
        "items": [{"producto_sku": "LIN", "cantidad": 1, "variante": None}, {"producto_sku": "CAR", "cantidad": 1, "variante": None}],
    }
    base.update(cambios)
    return base


class Escena:
    def __init__(self, productos=(LINTERNA, CARGADOR), precios=None, desde_anuncio=False, lead=None):
        self.lead = {**lead_inicial(), **(lead or {})}
        self.conversaciones = ConversacionesEnMemoria(desde_anuncio=desde_anuncio)
        self.leads = LeadsEnMemoria(self.lead)
        self.telegram = TelegramGrabador()
        self.gestion = GestionEnEnsayo(self.telegram)
        self.ventas = VentasEnEnsayo(self.lead, self.gestion, self.conversaciones)
        self.pedidos = MagicMock(name="PedidoService")
        self.pedidos.crear_y_confirmar.return_value = SimpleNamespace(id_local=10, id_rocketfy=99)
        self.productos = ProductosEnMemoria(*productos)
        self.precios = precios or PreciosEnMemoria()
        entregas = EntregasEnEnsayo([])
        self.herramientas = HerramientasVictoria(
            lead_repo=self.leads, conversacion_repo=self.conversaciones, producto_repo=self.productos, pedido_service=self.pedidos,
            telegram_notifier=self.telegram, stock_checker=StockEnEnsayo(None), minimo_repo=MagicMock(),
            mensaje_repo=MensajesEnMemoria([], "hola"), canales=MagicMock(), enviar_fotos=False, entrega_repo=entregas,
            gestion_service=self.gestion, ventas_service=self.ventas,
            cotizador=CotizadorServicio(productos=self.productos, precios=self.precios, entregas=entregas, ajustes=AjustesFijos()),
        )

    def usar(self, herramienta, **entrada):
        return self.herramientas.ejecutar(herramienta, 1, 1, entrada, "id-1").contenido

    def datos(self):
        self.usar("guardar_datos_cliente", nombre_cliente="Ana", direccion="Calle 1", canton="Quito", provincia="Pichincha")

    def pedido_enviado(self):
        return self.pedidos.crear_y_confirmar.call_args[0][0]


@pytest.fixture
def con_parametros(monkeypatch):
    """Fija algunos parámetros para una prueba (los demás, con su valor real)."""
    valores = {}
    real = parametros.valor
    monkeypatch.setattr(parametros, "valor", lambda clave: valores[clave] if clave in valores else real(clave))
    return valores


class TestTransferencia:
    def _escena(self):
        return Escena(productos=(_producto("LIN", "Linterna", "25.00", transferencia_tipo="precio", transferencia_valor=D("20.00")),))

    def test_victoria_sabe_el_precio_por_transferencia_y_el_total_sigue_siendo_contra_entrega(self):
        e = self._escena()
        mensaje = e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "Total a cobrar: $25.00" in mensaje and "transferencia el total baja a $20.00" in mensaje
        assert e.lead["total"] == D("25.00") and e.lead["total_transferencia"] == D("20.00")

    def test_al_elegir_transferencia_el_total_baja_y_rocketfy_lo_recibe_prepagado(self):
        e = self._escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        e.datos()
        mensaje = e.usar("registrar_metodo_pago", metodo_pago="transferencia")
        assert "$20.00" in mensaje and e.lead["total"] == D("20.00")
        e.lead["estado_pago"] = "confirmado"  # el dueño confirmó el comprobante

        assert "Pedido confirmado" in e.usar("cerrar_venta")
        dto = e.pedido_enviado()
        assert dto.total == D("20.00") and dto.no_contra_entrega is True

    def test_contra_entrega_cobra_el_precio_normal(self):
        e = self._escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        e.datos()
        assert e.usar("registrar_metodo_pago", metodo_pago="contraentrega").startswith("Método de pago registrado.")
        e.usar("cerrar_venta")
        assert e.pedido_enviado().total == D("25.00") and e.pedido_enviado().no_contra_entrega is False


class TestPrecioPorCantidad:
    def test_menciona_la_escala_y_la_aplica(self):
        e = Escena(precios=PreciosEnMemoria(escalas={"LIN": [{"cantidad": 2, "precio_total": D("45.00")}]}))
        assert "2 por $45.00" in e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "Total a cobrar: $45.00" in e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna", cantidad=2)

    def test_no_menciona_una_escala_mayor_al_maximo_por_pedido(self):
        e = Escena(
            productos=(_producto("LIN", "Linterna", "25.00", max_unidades_por_pedido=1),),
            precios=PreciosEnMemoria(escalas={"LIN": [{"cantidad": 2, "precio_total": D("45.00")}]}),
        )
        assert "por $45" not in e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")


class TestRegateo:
    def _escena(self):
        return Escena(productos=(_producto("LIN", "Linterna", "50.00", regateo_tipo="monto", regateo_valor=D("10.00")),))

    def test_ejemplo_de_freddy(self, con_parametros):
        con_parametros["precios.regateo_estrategia"] = "contraoferta"
        e = self._escena()
        assert "negociar_precio" in e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        primera = e.usar("negociar_precio", precio="45")
        assert "Ofrécele $48.00" in primera and e.lead["total"] == D("50.00")
        segunda = e.usar("negociar_precio", precio="45")
        assert "ACEPTADO" in segunda and e.lead["total"] == D("45.00")
        e.datos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert "Pedido confirmado" in e.usar("cerrar_venta")
        assert e.pedido_enviado().total == D("45.00")

    def test_nunca_baja_del_limite(self):
        e = self._escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        mensaje = e.usar("negociar_precio", precio="$30")
        assert "$40.00" in mensaje and "mínimo" in mensaje and e.lead["total"] == D("50.00")

    def test_aceptar_directo(self, con_parametros):
        con_parametros["precios.regateo_estrategia"] = "aceptar"
        e = self._escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "ACEPTADO" in e.usar("negociar_precio", precio="45") and e.lead["total"] == D("45.00")

    def test_producto_sin_regateo(self):
        e = Escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "no tiene rebaja" in e.usar("negociar_precio", precio="20") and e.lead["total"] == D("25.00")

    def test_cambiar_el_pedido_anula_lo_acordado(self, con_parametros):
        con_parametros["precios.regateo_estrategia"] = "aceptar"
        e = self._escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        e.usar("negociar_precio", precio="45")
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna", cantidad=2)
        assert e.lead["total"] == D("100.00")


class TestVariosProductos:
    def test_apagado_no_deja_agregar(self):
        e = Escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "un solo producto" in e.usar("registrar_producto", producto_sku="CAR", producto_nombre="Cargador", agregar=True)
        assert e.lead["producto_sku"] == "LIN"

    def test_encendido_suma_y_rocketfy_recibe_las_dos_lineas(self, con_parametros):
        con_parametros["precios.varios_productos"] = True
        e = Escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        mensaje = e.usar("registrar_producto", producto_sku="CAR", producto_nombre="Cargador", agregar=True)
        assert "TOTAL contra entrega: $37.00" in mensaje and e.lead["total"] == D("37.00")
        assert len(e.lead["lineas"]) == 2 and e.lead["cantidad"] == 2
        e.datos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert "Pedido confirmado" in e.usar("cerrar_venta")
        dto = e.pedido_enviado()
        assert [(l.sku, l.cantidad) for l in dto.lineas] == [("LIN", 1), ("CAR", 1)] and dto.total == D("37.00")

    def test_quitar_un_producto(self, con_parametros):
        con_parametros["precios.varios_productos"] = True
        e = Escena()
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        e.usar("registrar_producto", producto_sku="CAR", producto_nombre="Cargador", agregar=True)
        assert "se quitó" in e.usar("quitar_producto", producto_sku="CAR")
        assert e.lead["total"] == D("25.00") and e.lead["lineas"] is None and e.lead["producto_sku"] == "LIN"
        assert "único" in e.usar("quitar_producto", producto_sku="LIN")

    def test_p5_no_mezcla_rocketfy_con_propio(self, con_parametros):
        con_parametros["precios.varios_productos"] = True
        e = Escena(productos=(LINTERNA, PROPIO))
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        assert "dos pedidos" in e.usar("registrar_producto", producto_sku="PROP-1", producto_nombre="Zapatos", agregar=True)
        assert e.lead["total"] == D("25.00")


class TestOfertas:
    def _escena(self, **oferta):
        precios = PreciosEnMemoria(ofertas={7: _oferta(**oferta)}, vinculos={"ANUNCIO-PRUEBA": {"oferta_id": 7}})
        e = Escena(precios=precios, desde_anuncio=True)
        e.conversaciones.id_anuncio = "ANUNCIO-PRUEBA"
        return e

    def test_combo_del_anuncio_de_punta_a_punta(self):
        e = self._escena()
        mensaje = e.usar("aplicar_oferta", oferta_id=7)
        assert "Oferta registrada" in mensaje and "TOTAL contra entrega: $30.00" in mensaje
        assert e.lead["total"] == D("30.00") and e.lead["producto_nombre"] == "1 x Linterna + cargador"
        e.datos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert "Pedido confirmado" in e.usar("cerrar_venta")
        dto = e.pedido_enviado()
        assert [(l.sku, l.cantidad) for l in dto.lineas] == [("LIN", 1), ("CAR", 1)] and dto.total == D("30.00")

    def test_oferta_vencida(self):
        e = self._escena(hasta=AHORA - timedelta(days=1))
        assert "ya no está disponible" in e.usar("aplicar_oferta", oferta_id=7)
        assert e.lead["total"] is None

    def test_oferta_vencida_puede_pasar_al_dueno(self, con_parametros):
        con_parametros["precios.oferta_terminada"] = "dueno"
        e = self._escena(hasta=AHORA - timedelta(days=1))
        assert "se avisó a un asesor" in e.usar("aplicar_oferta", oferta_id=7) and e.conversaciones.escalada

    def test_p6_una_oferta_de_otro_anuncio_no_se_puede_pedir(self):
        e = Escena(precios=PreciosEnMemoria(ofertas={7: _oferta()}))
        assert "no tiene ofertas disponibles" in e.usar("aplicar_oferta", oferta_id=7)

    def test_oferta_publica_la_puede_pedir_cualquiera(self):
        e = Escena(precios=PreciosEnMemoria(ofertas={7: _oferta(visibilidad="publica")}))
        assert "Oferta registrada" in e.usar("aplicar_oferta", nombre="linterna + cargador")

    def test_maximo_por_cliente_y_cupo(self):
        e = self._escena(maximo_por_cliente=1)
        assert "como máximo 1" in e.usar("aplicar_oferta", oferta_id=7, cantidad=2)
        e = self._escena(cupo=5)
        e.precios.ventas_oferta = 5
        assert "agotó su cupo" in e.usar("aplicar_oferta", oferta_id=7)

    def test_si_la_oferta_termina_antes_de_cerrar_no_se_cierra(self):
        e = self._escena()
        e.usar("aplicar_oferta", oferta_id=7)
        e.datos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        e.precios._ofertas[7]["estado"] = "pausada"
        assert "inconveniente con la oferta" in e.usar("cerrar_venta")
        e.pedidos.crear_y_confirmar.assert_not_called()

    def test_combo_propio_guarda_la_venta_con_sus_lineas_y_descuento(self):
        propio_b = _producto("PROP-2", "Medias", "10.00", proveedor_id=2, proveedor_clave="propio", proveedor_cierre="manual")
        precios = PreciosEnMemoria(
            ofertas={8: _oferta(id=8, nombre="Zapatos + medias", precio=D("35.00"), visibilidad="publica",
                                items=[{"producto_sku": "PROP-1", "cantidad": 1, "variante": None},
                                       {"producto_sku": "PROP-2", "cantidad": 1, "variante": None}])},
        )
        e = Escena(productos=(PROPIO, propio_b), precios=precios)
        e.usar("aplicar_oferta", oferta_id=8)
        e.datos()
        e.usar("registrar_metodo_pago", metodo_pago="contraentrega")
        assert "¡Pedido registrado!" in e.usar("cerrar_venta")
        venta = e.ventas.venta
        assert [l["producto_sku"] for l in venta["lineas"]] == ["PROP-1", "PROP-2"]
        assert all(l["oferta_id"] == 8 for l in venta["lineas"])
        assert venta["descuento_total"] == D("5.00") and venta["total"] == D("35.00")


class TestLoQueVictoriaVe:
    def test_sin_reglas_no_se_agrega_nada(self):
        assert Escena().herramientas.reglas_para_victoria(LINTERNA) == ""

    def test_precios_especiales_del_producto(self):
        producto = _producto(
            "LIN", "Linterna", "25.00", transferencia_tipo="monto", transferencia_valor=D("5"), regateo_tipo="porcentaje",
            regateo_valor=D("10"),
        )
        e = Escena(productos=(producto,), precios=PreciosEnMemoria(escalas={"LIN": [{"cantidad": 2, "precio_total": D("45")}]}))
        texto = e.herramientas.reglas_para_victoria(producto)
        assert "2 por $45.00" in texto and "transferencia: $20.00 por unidad" in texto and "negociar_precio" in texto
        assert "mínimo" not in texto  # el límite del regateo nunca se le muestra

    def test_el_descuento_por_transferencia_se_ofrece_una_vez_y_como_oportunidad(self):
        producto = _producto("LIN", "Linterna", "25.00", transferencia_tipo="monto", transferencia_valor=D("5"))
        texto = Escena(productos=(producto,)).herramientas.reglas_para_victoria(producto)
        assert "descuento especial" in texto and "UNA sola vez" in texto and "prefiere pagar al recibir" in texto
        assert "sin volver a mencionar" in texto

    def test_con_el_interruptor_apagado_solo_lo_dice_si_preguntan(self, monkeypatch):
        from src.routes.whatsapp import tools

        original = tools.parametros.valor
        monkeypatch.setattr(tools.parametros, "valor", lambda clave, *a, **k: False if clave == "precios.mencionar_transferencia" else original(clave, *a, **k))
        producto = _producto("LIN", "Linterna", "25.00", transferencia_tipo="monto", transferencia_valor=D("5"))
        texto = Escena(productos=(producto,)).herramientas.reglas_para_victoria(producto)
        assert "UNA sola vez" not in texto and "si el cliente pregunta" in texto

    def test_la_oferta_del_anuncio_va_primero_con_su_texto(self):
        precios = PreciosEnMemoria(
            ofertas={7: _oferta(texto_anuncio="Linterna + cargador a solo $30"), 9: _oferta(id=9, nombre="Pack doble", visibilidad="publica")},
            vinculos={"AD": {"oferta_id": 7}},
        )
        e = Escena(precios=precios)
        texto = e.herramientas.ofertas_para_victoria({"id_anuncio": "AD"}, {})
        assert texto.index("#7") < texto.index("#9") and "OFERTA DEL ANUNCIO" in texto and "a solo $30" in texto

    def test_oferta_del_anuncio_vencida_se_avisa(self):
        precios = PreciosEnMemoria(ofertas={7: _oferta(hasta=AHORA - timedelta(hours=1))}, vinculos={"AD": {"oferta_id": 7}})
        texto = Escena(precios=precios).herramientas.ofertas_para_victoria({"id_anuncio": "AD"}, {})
        assert "YA TERMINÓ" in texto and "precio normal" in texto and "#7" not in texto

    def test_pedido_actual_en_palabras(self):
        from src.routes.precios.servicio import describir_cotizacion_guardada

        e = Escena(productos=(_producto("LIN", "Linterna", "25.00", transferencia_tipo="precio", transferencia_valor=D("20")),))
        e.usar("registrar_producto", producto_sku="LIN", producto_nombre="Linterna")
        texto = describir_cotizacion_guardada(e.lead["cotizacion"])
        assert "Total contra entrega: $25.00" in texto and "transferencia: $20.00" in texto
        assert describir_cotizacion_guardada(None) == ""
