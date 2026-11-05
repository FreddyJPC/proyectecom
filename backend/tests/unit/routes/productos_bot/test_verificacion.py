from decimal import Decimal

import pytest

from src.routes.productos_bot.verificacion import (
    avisos_de,
    bloqueos_de_contenido,
    bloqueos_de_disponibilidad,
    metodos_de_pago,
    piso_de_precio,
    verificar_producto,
)


def _producto(**cambios):
    producto = {
        "nombre": "Producto Demo",
        "descripcion": "Un buen producto.",
        "precio": Decimal("24.99"),
        "costo_rocketfy": Decimal("10.00"),
        "tiempo_entrega": "2 a 4 días hábiles",
        "metodos_pago_aceptados": "contraentrega",
        "preguntas_frecuentes": "¿Trae cargador? Sí.",
        "variantes": None,
        "max_unidades_por_pedido": 1,
        "stock_ultimo": 50,
    }
    producto.update(cambios)
    return producto


class TestMetodosDePago:
    def test_separa_limpia_y_quita_repetidos(self):
        assert metodos_de_pago(" Contraentrega ,transferencia, contraentrega") == ["contraentrega", "transferencia"]

    @pytest.mark.parametrize("vacio", [None, "", " , "])
    def test_vacio(self, vacio):
        assert metodos_de_pago(vacio) == []


class TestPisoDePrecio:
    def test_nunca_baja_del_recaudo_minimo_de_rocketfy(self):
        assert piso_de_precio(Decimal("3.00")) == Decimal("10.00")
        assert piso_de_precio(None) == Decimal("10.00")

    def test_si_el_costo_es_mayor_el_piso_es_el_costo(self):
        assert piso_de_precio(Decimal("18.50")) == Decimal("18.50")

    def test_con_envio_confirmado_el_piso_es_costo_mas_envio(self):
        assert piso_de_precio(Decimal("12.00"), Decimal("5.00")) == Decimal("17.00")

    def test_el_envio_no_baja_el_recaudo_minimo(self):
        assert piso_de_precio(Decimal("2.00"), Decimal("3.00")) == Decimal("10.00")

    def test_sin_envio_o_con_none_el_piso_es_el_de_antes(self):
        assert piso_de_precio(Decimal("12.00"), None) == Decimal("12.00")
        assert piso_de_precio(Decimal("12.00")) == Decimal("12.00")


class TestBloqueosDeContenido:
    def test_un_producto_completo_no_tiene_bloqueos(self):
        assert bloqueos_de_contenido(_producto()) == []

    @pytest.mark.parametrize(
        "campo, valor, fragmento",
        [
            ("nombre", "  ", "nombre"),
            ("descripcion", "", "descripción"),
            ("tiempo_entrega", "", "tiempo de entrega"),
            ("metodos_pago_aceptados", "", "método de pago"),
            ("max_unidades_por_pedido", 0, "unidades máximas"),
            ("precio", Decimal("0"), "mayor que cero"),
            ("precio", None, "mayor que cero"),
        ],
    )
    def test_cada_dato_obligatorio_bloquea(self, campo, valor, fragmento):
        bloqueos = bloqueos_de_contenido(_producto(**{campo: valor}))
        assert any(fragmento in b.lower() for b in bloqueos), bloqueos

    def test_metodo_de_pago_desconocido_bloquea(self):
        bloqueos = bloqueos_de_contenido(_producto(metodos_pago_aceptados="contraentrega, bitcoin"))
        assert any("bitcoin" in b for b in bloqueos)

    def test_precio_bajo_el_recaudo_minimo_bloquea_aunque_no_haya_costo(self):
        bloqueos = bloqueos_de_contenido(_producto(precio=Decimal("9.99"), costo_rocketfy=None))
        assert len(bloqueos) == 1 and "$9.99" in bloqueos[0] and "$10.00" in bloqueos[0]

    def test_precio_bajo_el_costo_bloquea(self):
        bloqueos = bloqueos_de_contenido(_producto(precio=Decimal("14.00"), costo_rocketfy=Decimal("15.00")))
        assert len(bloqueos) == 1 and "$14.00" in bloqueos[0] and "$15.00" in bloqueos[0]

    def test_con_envio_confirmado_un_precio_que_no_cubre_costo_mas_envio_bloquea(self):
        producto = _producto(precio=Decimal("16.00"), costo_rocketfy=Decimal("12.00"))
        assert bloqueos_de_contenido(producto) == []  # sin contar envío: $16 > $12
        bloqueos = bloqueos_de_contenido(producto, envio_para_piso=Decimal("5.00"))
        assert len(bloqueos) == 1
        assert "$16.00" in bloqueos[0] and "$17.00" in bloqueos[0] and "envío estimado ($5.00)" in bloqueos[0]

    def test_con_envio_confirmado_un_precio_igual_al_piso_no_bloquea(self):
        producto = _producto(precio=Decimal("17.00"), costo_rocketfy=Decimal("12.00"))
        assert bloqueos_de_contenido(producto, envio_para_piso=Decimal("5.00")) == []

    def test_precio_igual_al_piso_no_bloquea(self):
        assert bloqueos_de_contenido(_producto(precio=Decimal("10.00"), costo_rocketfy=Decimal("4.00"))) == []

    def test_precio_como_texto_o_float_se_trata_como_decimal(self):
        assert bloqueos_de_contenido(_producto(precio="24.99")) == []
        assert bloqueos_de_contenido(_producto(precio=5)) != []


class TestBloqueosDeDisponibilidad:
    def test_sku_que_no_existe(self):
        assert any("no existe" in b for b in bloqueos_de_disponibilidad(False, 5))

    def test_sin_stock(self):
        assert any("stock" in b for b in bloqueos_de_disponibilidad(True, 0))

    def test_no_consultado_no_bloquea(self):
        assert bloqueos_de_disponibilidad(None, None) == []

    def test_con_stock_no_bloquea(self):
        assert bloqueos_de_disponibilidad(True, 3) == []


class TestAvisos:
    def test_producto_sencillo_solo_sin_avisos(self):
        assert avisos_de(_producto(), stock=50) == []

    def test_transferencia(self):
        assert any("transferencia" in a for a in avisos_de(_producto(metodos_pago_aceptados="contraentrega, transferencia"), 50))

    def test_stock_bajo_pero_no_cero(self):
        assert any("pocas unidades" in a for a in avisos_de(_producto(), stock=3))
        assert not any("pocas unidades" in a for a in avisos_de(_producto(), stock=0))
        assert not any("pocas unidades" in a for a in avisos_de(_producto(), stock=6))

    def test_sin_preguntas_frecuentes(self):
        assert any("preguntas frecuentes" in a for a in avisos_de(_producto(preguntas_frecuentes=None), 50))

    def test_descripcion_larga(self):
        assert any("muy larga" in a for a in avisos_de(_producto(descripcion="x" * 1201), 50))

    def test_variantes(self):
        assert any("variantes" in a for a in avisos_de(_producto(variantes="negro, blanco"), 50))

    def test_mas_de_una_unidad(self):
        assert any("más de una unidad" in a for a in avisos_de(_producto(max_unidades_por_pedido=2), 50))


class TestVerificarProducto:
    def test_usa_el_stock_guardado_si_no_se_pasa_uno_en_vivo(self):
        resultado = verificar_producto(_producto(stock_ultimo=0))
        assert any("stock" in b for b in resultado.bloqueos)

    def test_el_stock_en_vivo_tiene_prioridad(self):
        resultado = verificar_producto(_producto(stock_ultimo=0), existe_en_rocketfy=True, stock=8)
        assert resultado.bloqueos == []

    def test_el_envio_confirmado_llega_hasta_los_bloqueos(self):
        producto = _producto(precio=Decimal("16.00"), costo_rocketfy=Decimal("12.00"))
        assert verificar_producto(producto).bloqueos == []
        assert len(verificar_producto(producto, envio_para_piso=Decimal("5.00")).bloqueos) == 1

    def test_junta_bloqueos_y_avisos(self):
        resultado = verificar_producto(
            _producto(descripcion="", metodos_pago_aceptados="transferencia"), existe_en_rocketfy=False, stock=2
        )
        assert len(resultado.bloqueos) == 2  # sin descripción + SKU inexistente
        assert any("transferencia" in a for a in resultado.avisos)
        assert any("pocas unidades" in a for a in resultado.avisos)
