"""
Motor de precios (ADR-017): reglas, cotización y regateo. Todo puro, con `Decimal`.
El primer bloque es la garantía de «no romper lo que funciona»: sin reglas, el total es el de siempre.
"""
from decimal import Decimal

import pytest

from src.routes.entregas.logica import total_con_envio
from src.routes.precios.cotizacion import (
    DatosCotizacion,
    ItemOferta,
    LineaInvalida,
    LineaPedido,
    OfertaPrecio,
    ProductoPrecio,
    Regateo,
    TransferenciaNegocio,
    cotizar,
)
from src.routes.precios.negociacion import (
    ACEPTA,
    CONTRAOFERTA,
    FIRME,
    MINIMO,
    SIN_REGATEO,
    YA_ES_EL_PRECIO,
    negociar,
)
from src.routes.precios.reglas import (
    AjustesPiso,
    Escala,
    limite_regateo,
    piso_del_pedido,
    precio_por_cantidad,
    precio_transferencia,
    redondear_arriba,
)

D = Decimal


def _producto(**cambios):
    datos = dict(sku="A", nombre="Linterna", precio=D("25.00"), costo=D("8.00"))
    datos.update(cambios)
    return ProductoPrecio(**datos)


def _linea(sku="A", cantidad=1, variante=None):
    return LineaPedido(tipo="producto", sku=sku, cantidad=cantidad, variante=variante)


AJUSTES = AjustesPiso(
    confirmado=True, margen_minimo_pct=D("25"), envio_estimado=D("4.00"), otros_costos_fijos=D("0"), otros_costos_pct=D("0")
)


class TestSinReglasEsIgualQueAntes:
    @pytest.mark.parametrize("precio,cantidad", [(D("24.99"), 1), (D("24.99"), 3), (D("19.90"), 2), (D("0.10"), 7)])
    def test_total_igual_a_precio_por_cantidad(self, precio, cantidad):
        c = cotizar(DatosCotizacion(lineas=[_linea(cantidad=cantidad)], productos={"A": _producto(precio=precio)}))
        antes = (precio * cantidad).quantize(D("0.01"))
        assert c.total == antes == c.total_contraentrega == c.total_transferencia
        assert c.descuentos() == []
        assert c.minimo_regateo is None

    def test_con_envio_aparte_igual_que_total_con_envio(self):
        producto = _producto(precio=D("30.00"), envio_incluido=False)
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": producto}, envio_opcion_costo=D("3.50")))
        assert c.total == total_con_envio(D("30.00"), {"costo_cliente": D("3.50")}) == D("33.50")

    def test_envio_aparte_sin_elegir_queda_pendiente(self):
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": _producto(envio_incluido=False)}))
        assert c.envio_pendiente and c.envio == 0 and c.total == D("25.00")

    def test_pedido_vacio_o_producto_desconocido_es_error(self):
        with pytest.raises(LineaInvalida):
            cotizar(DatosCotizacion(lineas=[], productos={}))
        with pytest.raises(LineaInvalida):
            cotizar(DatosCotizacion(lineas=[_linea("X")], productos={}))


class TestEscalas:
    ESCALAS = (Escala(2, D("45.00")), Escala(3, D("60.00")))

    def test_usa_la_escala_exacta(self):
        assert precio_por_cantidad(D("25"), 2, self.ESCALAS) == (D("45.00"), Escala(2, D("45.00")))
        assert precio_por_cantidad(D("25"), 3, self.ESCALAS)[0] == D("60.00")

    def test_mas_unidades_que_la_mayor_escala_al_precio_por_unidad_de_esa_escala(self):
        assert precio_por_cantidad(D("25"), 4, self.ESCALAS)[0] == D("80.00")

    def test_una_unidad_o_escala_que_encarece_usa_la_lista(self):
        assert precio_por_cantidad(D("25"), 1, self.ESCALAS) == (D("25.00"), None)
        assert precio_por_cantidad(D("25"), 2, (Escala(2, D("60")),)) == (D("50.00"), None)

    def test_la_cotizacion_marca_el_descuento_por_escala(self):
        c = cotizar(DatosCotizacion(lineas=[_linea(cantidad=2)], productos={"A": _producto(escalas=self.ESCALAS)}))
        assert c.total == D("45.00")
        assert c.descuentos() == [{"motivo": "escala", "monto": "5.00"}]


class TestTransferencia:
    def test_reglas(self):
        assert precio_transferencia(D("25"), 1, "precio", D("20")) == D("20.00")
        assert precio_transferencia(D("50"), 2, "precio", D("20")) == D("40.00")
        assert precio_transferencia(D("25"), 1, "porcentaje", D("20")) == D("20.00")
        assert precio_transferencia(D("50"), 2, "monto", D("5")) == D("40.00")
        assert precio_transferencia(D("25"), 1, None, None) is None

    def test_nunca_encarece_ni_llega_a_cero(self):
        assert precio_transferencia(D("25"), 1, "precio", D("30")) == D("25")
        assert precio_transferencia(D("5"), 1, "monto", D("5")) is None

    def test_producto_25_contraentrega_20_transferencia(self):
        p = _producto(transferencia_tipo="precio", transferencia_valor=D("20"))
        datos = DatosCotizacion(lineas=[_linea()], productos={"A": p})
        c = cotizar(datos)
        assert (c.total_contraentrega, c.total_transferencia, c.total) == (D("25.00"), D("20.00"), D("25.00"))
        assert c.hay_precio_por_transferencia
        datos.metodo_pago = "transferencia"
        c = cotizar(datos)
        assert c.total == D("20.00")
        assert c.descuentos() == [{"motivo": "transferencia", "monto": "5.00"}]

    def test_regla_del_negocio_si_el_producto_no_tiene(self):
        c = cotizar(
            DatosCotizacion(
                lineas=[_linea()], productos={"A": _producto()}, transferencia_negocio=TransferenciaNegocio("porcentaje", D("10"))
            )
        )
        assert c.total_transferencia == D("22.50")

    def test_la_regla_del_producto_manda_sobre_la_del_negocio(self):
        p = _producto(transferencia_tipo="monto", transferencia_valor=D("2"))
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": p}, transferencia_negocio=TransferenciaNegocio("monto", D("5"))))
        assert c.total_transferencia == D("23.00")


class TestPisoYRegateo:
    def test_piso(self):
        # (8 + 4) / 0.75 = 16.00
        assert piso_del_pedido([D("8.00")], AJUSTES) == D("16.00")
        assert piso_del_pedido([D("8.00"), None], AJUSTES) is None
        assert piso_del_pedido([D("8.00")], None) is None
        sin_confirmar = AjustesPiso(False, D("25"), D("4"), D("0"), D("0"))
        assert piso_del_pedido([D("8.00")], sin_confirmar) is None

    def test_limite(self):
        assert limite_regateo(D("50"), 1, "monto", D("10")) == D("10.00")
        assert limite_regateo(D("50"), 1, "porcentaje", D("20")) == D("10.00")
        assert limite_regateo(D("100"), 2, "monto", D("10")) == D("20.00")
        assert limite_regateo(D("50"), 1, None, None) == 0

    def test_minimo_es_el_mayor_entre_limite_y_piso(self):
        p = _producto(precio=D("50"), regateo_tipo="monto", regateo_valor=D("10"))
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": p}, ajustes=AJUSTES))
        assert c.minimo_regateo == D("40.00")  # piso 16 < 40
        caro = _producto(precio=D("50"), costo=D("30"), regateo_tipo="monto", regateo_valor=D("20"))
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": caro}, ajustes=AJUSTES))
        assert c.minimo_regateo == D("45.34")  # piso (30+4)/0.75 = 45.34 manda sobre 30

    def test_sin_regateo_configurado_no_hay_minimo(self):
        c = cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": _producto()}, ajustes=AJUSTES))
        assert c.minimo_regateo is None

    def test_regateo_acordado_se_aplica_solo_si_el_pedido_no_cambio(self):
        p = _producto(precio=D("50"), regateo_tipo="monto", regateo_valor=D("10"))
        datos = DatosCotizacion(lineas=[_linea()], productos={"A": p}, regateo=Regateo(acordado=D("45"), base=D("50.00")))
        c = cotizar(datos)
        assert c.total == D("45.00") and c.regateo_vigente
        assert c.descuentos() == [{"motivo": "regateo", "monto": "5.00"}]
        datos.lineas = [_linea(cantidad=2)]
        assert cotizar(datos).regateo_vigente is False

    def test_p2_regateo_y_transferencia_no_se_suman(self):
        p = _producto(precio=D("50"), regateo_tipo="monto", regateo_valor=D("10"), transferencia_tipo="precio", transferencia_valor=D("44"))
        datos = DatosCotizacion(
            lineas=[_linea()], productos={"A": p}, regateo=Regateo(acordado=D("45"), base=D("50")), metodo_pago="transferencia"
        )
        assert cotizar(datos).total == D("44.00")  # el mejor de los dos, no 39
        datos.regateo = Regateo(acordado=D("42"), base=D("50"))
        assert cotizar(datos).total == D("42.00")

    def test_la_escala_consume_el_margen_de_regateo(self):
        p = _producto(precio=D("25"), regateo_tipo="monto", regateo_valor=D("2"), escalas=(Escala(2, D("45")),))
        c = cotizar(DatosCotizacion(lineas=[_linea(cantidad=2)], productos={"A": p}))
        # lista 50, límite 4 -> no menos de 46; la escala ya cobra 45: no queda regateo.
        assert c.minimo_regateo is None


class TestOfertas:
    def _datos(self, **oferta):
        productos = {"A": _producto(), "B": _producto(sku="B", nombre="Cargador", precio=D("12.00"), costo=D("3.00"))}
        base = dict(id=7, nombre="Linterna + cargador", precio=D("30.00"), items=(ItemOferta("A"), ItemOferta("B")))
        base.update(oferta)
        return DatosCotizacion(lineas=[LineaPedido(tipo="oferta", oferta_id=7)], productos=productos, ofertas={7: OfertaPrecio(**base)})

    def test_combo_cobra_su_precio_y_lista_sus_productos(self):
        c = cotizar(self._datos())
        assert c.total == D("30.00")
        assert c.subtotal_lista == D("37.00")
        assert [(i.sku, i.cantidad, i.oferta_id) for i in c.items] == [("A", 1, 7), ("B", 1, 7)]
        assert c.descuentos() == [{"motivo": "oferta", "monto": "7.00"}]

    def test_dos_combos(self):
        datos = self._datos()
        datos.lineas = [LineaPedido(tipo="oferta", oferta_id=7, cantidad=2)]
        c = cotizar(datos)
        assert c.total == D("60.00") and c.unidades == 4

    def test_p7_combo_sin_regateo_por_defecto(self):
        assert cotizar(self._datos()).minimo_regateo is None

    def test_combo_con_regateo_permitido(self):
        assert cotizar(self._datos(regateo_tipo="monto", regateo_valor=D("3"))).minimo_regateo == D("27.00")

    def test_combo_y_producto_suelto(self):
        datos = self._datos()
        datos.lineas = [LineaPedido(tipo="oferta", oferta_id=7), _linea("B")]
        assert cotizar(datos).total == D("42.00")


class TestEnvioGratis:
    def test_desde_unidades(self):
        p = _producto(envio_incluido=False, envio_gratis_desde_unidades=2)
        datos = DatosCotizacion(lineas=[_linea(cantidad=2)], productos={"A": p}, envio_opcion_costo=D("3.00"))
        c = cotizar(datos)
        assert c.envio == 0 and c.envio_gratis and c.total == D("50.00")
        datos.lineas = [_linea(cantidad=1)]
        assert cotizar(datos).total == D("28.00")

    def test_desde_monto(self):
        p = _producto(envio_incluido=False, envio_gratis_desde_monto=D("40"))
        c = cotizar(DatosCotizacion(lineas=[_linea(cantidad=2)], productos={"A": p}, envio_opcion_costo=D("3.00")))
        assert c.envio_gratis

    def test_gratis_igual_pide_elegir_la_entrega(self):
        p = _producto(envio_incluido=False, envio_gratis_desde_unidades=1)
        assert cotizar(DatosCotizacion(lineas=[_linea()], productos={"A": p})).envio_pendiente


class TestNegociacion:
    def test_ejemplo_de_freddy_contraoferta_primero(self):
        r = negociar(D("50"), D("40"), D("45"))
        assert (r.decision, r.precio, r.rondas) == (CONTRAOFERTA, D("48.00"), 1)
        r2 = negociar(D("50"), D("40"), D("45"), rondas_hechas=r.rondas, ultima_contraoferta=r.precio)
        assert (r2.decision, r2.precio) == (ACEPTA, D("45.00"))

    def test_acepta_la_contraoferta(self):
        assert negociar(D("50"), D("40"), D("48"), rondas_hechas=1, ultima_contraoferta=D("48")).decision == ACEPTA

    def test_estrategia_aceptar(self):
        r = negociar(D("50"), D("40"), D("45"), estrategia="aceptar")
        assert (r.decision, r.precio) == (ACEPTA, D("45.00"))

    def test_bajo_el_minimo_ofrece_el_minimo(self):
        r = negociar(D("50"), D("40"), D("35"))
        assert (r.decision, r.precio) == (MINIMO, D("40.00"))
        assert negociar(D("50"), D("40"), D("40"), rondas_hechas=1, ultima_contraoferta=D("40")).decision == ACEPTA

    def test_despues_de_las_rondas_maximas_se_mantiene_firme(self):
        r = negociar(D("50"), D("40"), D("30"), rondas_hechas=3, ultima_contraoferta=D("40"), rondas_maximas=3)
        assert (r.decision, r.precio) == (FIRME, D("40"))

    def test_sin_margen_o_pidiendo_el_precio(self):
        assert negociar(D("50"), None, D("45")).decision == SIN_REGATEO
        assert negociar(D("50"), D("40"), D("50")).decision == YA_ES_EL_PRECIO

    def test_el_minimo_redondeado_no_supera_el_precio(self):
        r = negociar(D("40.50"), D("40.20"), D("30"))
        assert r.decision == MINIMO and D("40.20") <= r.precio < D("40.50")

    def test_redondeos(self):
        assert redondear_arriba(D("47.50"), "dolar") == D("48.00")
        assert redondear_arriba(D("47.20"), "medio") == D("47.50")
        assert redondear_arriba(D("47.201"), "centavo") == D("47.21")
