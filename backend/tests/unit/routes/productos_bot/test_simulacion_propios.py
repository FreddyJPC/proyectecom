"""
«Probar con Victoria» con un producto PROPIO (ADR-012): el cierre manual se ensaya de punta a punta sin tocar
nada real (ni la base, ni Rocketfy, ni Telegram, ni WhatsApp) y deja a la vista la venta que se habría guardado.
"""
from decimal import Decimal

import responses

from src.routes.productos_bot.simulacion import simular_turno
from tests.unit.routes.productos_bot.test_pruebas import probar, servicio
from tests.unit.routes.productos_bot.test_simulacion import LLMGuionado, herramientas, texto

SKU = "PROP-0001"
ENTREGAS = [
    {
        "id": 1, "nombre": "Envío en Cuenca", "tipo": "envio", "costo_cliente": Decimal("2.00"), "costo_negocio": Decimal("1.00"),
        "cantones": ["Cuenca"], "provincias": [], "resto_del_pais": False, "direccion_retiro": None, "tiempo_entrega": None,
        "activo": True,
    },
    {
        "id": 2, "nombre": "Retiro en tienda", "tipo": "retiro", "costo_cliente": Decimal("0.00"), "costo_negocio": None,
        "cantones": [], "provincias": [], "resto_del_pais": False, "direccion_retiro": "Calle Larga 1-23",
        "tiempo_entrega": None, "activo": True,
    },
]


def ficha_propia(**cambios):
    datos = {
        "id": 9, "sku": SKU, "nombre": "Zapatos de cuero", "descripcion": "Hechos a mano.", "precio": Decimal("30.00"),
        "variantes": "talla 38 a 42", "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega, transferencia",
        "preguntas_frecuentes": None, "temas_no_responder": None, "max_unidades_por_pedido": 3, "estado": "borrador",
        "activo": False, "proveedor_id": 2, "proveedor_clave": "propio", "proveedor_cierre": "manual",
        "categoria_id": 3, "categoria_nombre": "Calzado", "costo_rocketfy": None, "costo_propio": Decimal("18.00"),
        "controla_stock": True, "stock_ultimo": 5, "envio_incluido": False, "costo_flete_estimado": None, "imagen_url": None,
    }
    datos.update(cambios)
    return datos


DATOS = ("guardar_datos_cliente", {"nombre_cliente": "Ana", "direccion": "Calle 1", "canton": "Cuenca", "provincia": "Azuay"})
PRODUCTO = ("registrar_producto", {"producto_sku": SKU, "producto_nombre": "Zapatos de cuero", "cantidad": 2, "variante": "talla 40"})
ENTREGA = ("registrar_entrega", {"opcion": "1"})
PAGO = ("registrar_metodo_pago", {"metodo_pago": "contraentrega"})
COMPRA = ("solicitar_gestion", {"tipo": "quiere_comprar", "detalle": "quiere 2 pares"})
CERRAR = ("cerrar_venta", {})


def compra_propia():
    return LLMGuionado(herramientas(COMPRA, DATOS, PRODUCTO, ENTREGA, PAGO, CERRAR), texto("Listo, el dueño te escribe pronto."))


def turno(llm, producto=None, entregas=ENTREGAS, mensaje="Quiero 2 pares", desde_anuncio=False):
    return simular_turno(
        producto=producto or ficha_propia(), mensaje=mensaje, historial=[], estado=None, desde_anuncio=desde_anuncio,
        llm=llm, entregas=entregas,
    )


class TestCompraPropia:
    def test_el_cierre_manual_deja_la_venta_y_los_avisos_a_la_vista(self):
        r = turno(compra_propia())

        assert r.pedido is None  # nada se habría enviado a Rocketfy
        assert r.estado["estado"] == "por_gestionar" and r.estado["total"] == "62.00"
        assert r.estado["entrega_nombre"] == "Envío en Cuenca" and r.estado["costo_envio"] == "2.00"
        assert r.escalada is True  # la conversación pasó al dueño

        v = r.venta_manual
        assert (v["producto"], v["variante"], v["cantidad"]) == ("Zapatos de cuero", "talla 40", 2)
        assert (v["subtotal"], v["costo_envio_cliente"], v["total"]) == ("60.00", "2.00", "62.00")
        assert (v["costo_productos"], v["costo_envio_negocio"], v["ganancia"]) == ("36.00", "1.00", "25.00")
        assert v["entrega"] == "Envío en Cuenca" and v["metodo_pago"] == "contraentrega" and v["canal"] == "directo"

        textos = [a["texto"] for a in r.avisos]
        assert any("Cierre previo: Quiere comprar" in t for t in textos)
        assert any("Pedido cerrado, gestionar envío" in t for t in textos)
        assert [s["tipo"] for s in r.solicitudes] == ["quiere_comprar"]

    def test_ver_el_producto_pasa_la_conversacion_sin_pedir_datos(self):
        llm = LLMGuionado(
            herramientas(("solicitar_gestion", {"tipo": "quiere_ver_producto", "detalle": "quiere verlos"})),
            texto("El dueño te contacta."),
        )
        r = turno(llm, mensaje="¿Puedo verlos en persona?")
        assert r.escalada is True and r.venta_manual is None
        assert [s["etiqueta"] for s in r.solicitudes] == ["Quiere ver el producto"]

    def test_victoria_ve_el_envio_y_el_cierre_manual_en_su_ficha(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm, desde_anuncio=True)
        sistema = llm.llamadas[0]["system"]
        assert "Cierre de la venta: MANUAL" in sistema and "Envío en Cuenca" in sistema

    def test_en_la_lista_de_productos_se_marca_el_de_cierre_manual(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm, desde_anuncio=False)
        assert "[cierre manual: lo gestiona el dueño]" in llm.llamadas[0]["system"]

    def test_las_herramientas_nuevas_se_le_ofrecen_al_modelo(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm)
        assert {"registrar_entrega", "solicitar_gestion"} <= {h.nombre for h in llm.llamadas[0]["herramientas"]}

    @responses.activate  # sin ninguna URL registrada: cualquier petición HTTP lanza ConnectionError
    def test_cero_efectos_reales_ni_peticiones_ni_base(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError("La simulación intentó usar la base de datos")

        monkeypatch.setattr("src.config.database._get_pool", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.tools.get_rocketfy_client", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.tools.get_telegram_notifier", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.stock.get_rocketfy_client", prohibido)
        monkeypatch.setattr("src.routes.gestion.services.get_telegram_notifier", prohibido)

        r = turno(compra_propia())

        assert r.venta_manual is not None and len(responses.calls) == 0

    def test_sin_cobertura_la_prueba_lo_muestra(self):
        llm = LLMGuionado(herramientas(PRODUCTO, ("guardar_datos_cliente", {"canton": "Quito", "provincia": "Pichincha"}), ("registrar_entrega", {})), texto("Lo siento."))
        r = turno(llm, entregas=[ENTREGAS[0]])
        assert r.escalada is True and [s["tipo"] for s in r.solicitudes] == ["sin_cobertura"]


class TestPruebasService:
    def test_una_compra_propia_completa_cuenta_como_simulacion_completa(self):
        s, repo, _ = servicio(llm=compra_propia(), fila=ficha_propia(), entregas=ENTREGAS)

        turno_dto = probar(s, "Quiero 2 pares", sku=SKU)

        assert turno_dto.venta_manual["total"] == "62.00" and turno_dto.pedido is None
        assert turno_dto.estado["entregaNombre"] == "Envío en Cuenca" and turno_dto.estado["costoEnvio"] == "2.00"
        assert [s["tipo"] for s in turno_dto.solicitudes] == ["quiere_comprar"]
        assert any(h[1] == "simulacion_completa" for h in repo.historial)

    def test_cuando_el_pedido_ya_paso_al_dueno_la_prueba_no_sigue(self):
        import pytest

        from src.routes.productos_bot.exceptions import PruebaInvalidaError

        s, *_ = servicio(llm=LLMGuionado(), fila=ficha_propia(), entregas=ENTREGAS)
        with pytest.raises(PruebaInvalidaError):
            probar(s, "Hola otra vez", estado={"estado": "por_gestionar"}, sku=SKU)


class TestGaleriaEnLaPrueba:
    def test_la_prueba_muestra_las_fotos_de_la_galeria_y_no_envia_nada(self):
        galeria = [
            {"id": 1, "url": "https://proyecto.supabase.co/storage/v1/object/public/productos/PROP-0001/a.jpg", "orden": 0},
            {"id": 2, "url": "https://proyecto.supabase.co/storage/v1/object/public/productos/PROP-0001/b.jpg", "orden": 1},
        ]
        llm = LLMGuionado(herramientas(("enviar_foto_producto", {"producto_sku": SKU})), texto("Te las mando."))

        r = simular_turno(
            producto=ficha_propia(imagen_url=None), mensaje="¿Tienes fotos?", historial=[], estado=None, desde_anuncio=False,
            llm=llm, entregas=ENTREGAS, imagenes=galeria,
        )

        assert [f["url"] for f in r.fotos] == [g["url"] for g in galeria]
        assert "Ya le enviaste 2 fotos" in r.herramientas[0]["resultado"]

    def test_sin_ninguna_foto_victoria_dice_que_por_ahora_no_hay(self):
        llm = LLMGuionado(herramientas(("enviar_foto_producto", {"producto_sku": SKU})), texto("Por ahora no tengo fotos."))
        r = simular_turno(
            producto=ficha_propia(imagen_url=None), mensaje="¿Tienes fotos?", historial=[], estado=None, desde_anuncio=False,
            llm=llm, entregas=ENTREGAS, imagenes=[],
        )
        assert r.fotos == [] and "por el momento no hay imágenes" in r.herramientas[0]["resultado"]
