"""
Motor de «Probar con Victoria» (Fase E). Se prueba con una IA guionada (sin
red) y, lo más importante, con el test de «cero efectos reales»: una compra
simulada completa NO hace ninguna petición HTTP (Rocketfy, Telegram, WhatsApp)
ni abre una conexión a la base de datos.
"""
import json
from decimal import Decimal

import pytest
import responses

from src.integrations.llm.contratos import LlamadaHerramienta, LLMProvider, RespuestaLLM
from src.routes.productos_bot import simulacion
from src.routes.productos_bot.simulacion import (
    TELEFONO_DE_PRUEBA,
    estado_desde_lead,
    lead_desde_estado,
    lead_inicial,
    simular_turno,
)

SKU = "SIM-1"


def ficha(**cambios):
    datos = {
        "id": 7, "sku": SKU, "nombre": "Audifonos Bluetooth", "descripcion": "Audifonos con 20 horas de bateria.",
        "precio": Decimal("24.99"), "variantes": "Negro, blanco", "tiempo_entrega": "2 a 4 dias habiles",
        "metodos_pago_aceptados": "contraentrega, transferencia", "preguntas_frecuentes": "Incluye estuche? Si.",
        "temas_no_responder": "Garantia", "max_unidades_por_pedido": 2, "estado": "borrador", "activo": False,
        "stock_ultimo": 50, "imagen_url": "https://cdn.rocketfy.example/audifonos.png",
    }
    datos.update(cambios)
    return datos


class LLMGuionado(LLMProvider):
    """Devuelve las respuestas en orden y anota lo que recibió."""

    def __init__(self, *respuestas):
        self._respuestas = list(respuestas)
        self.llamadas = []

    def generar_respuesta(self, system, mensajes, herramientas, max_tokens=1024, forzar_herramienta=None):
        self.llamadas.append({"system": system, "mensajes": list(mensajes), "herramientas": herramientas})
        return self._respuestas.pop(0)


def herramientas(*llamadas):
    """Un turno del modelo que pide herramientas: llamadas = (nombre, entrada)."""
    return RespuestaLLM(
        texto="",
        llamadas_herramientas=[LlamadaHerramienta(id=f"id{i}", nombre=n, entrada=e) for i, (n, e) in enumerate(llamadas)],
        razon_de_parada="necesita_herramientas",
    )


def texto(contenido):
    return RespuestaLLM(texto=contenido, llamadas_herramientas=[], razon_de_parada="fin")


DATOS = ("guardar_datos_cliente", {
    "nombre_cliente": "Ana Prueba", "direccion": "Av. Siempre Viva 123", "canton": "Quito", "provincia": "Pichincha",
})
PRODUCTO = ("registrar_producto", {"producto_sku": SKU, "producto_nombre": "Audifonos Bluetooth"})
CONTRAENTREGA = ("registrar_metodo_pago", {"metodo_pago": "contraentrega"})
CERRAR = ("cerrar_venta", {})


def compra_completa():
    return LLMGuionado(herramientas(DATOS, PRODUCTO, CONTRAENTREGA, CERRAR), texto("Listo, tu pedido va en camino."))


FOTO_SUBIDA = {"id": 1, "url": "https://xyz.supabase.co/storage/v1/object/public/productos/p1/audifonos.jpg", "orden": 0}


def turno(llm, mensaje="Quiero comprarlos", historial=(), estado=None, desde_anuncio=False, producto=None, imagenes=None):
    return simular_turno(
        producto=producto or ficha(), mensaje=mensaje, historial=list(historial), estado=estado,
        desde_anuncio=desde_anuncio, llm=llm, imagenes=imagenes,
    )


class TestCompraCompleta:
    def test_arma_el_pedido_real_y_lo_deja_como_vista_previa(self):
        r = turno(compra_completa())

        assert r.respuesta == "Listo, tu pedido va en camino."
        assert [h["nombre"] for h in r.herramientas] == [
            "guardar_datos_cliente", "registrar_producto", "registrar_metodo_pago", "cerrar_venta",
        ]
        assert r.pedido["confirmado"] is True
        p = r.pedido["payload"]
        # El payload que armó PedidoService de verdad: teléfono en formato local, dinero como texto, etc.
        assert p["name"] == "Ana Prueba" and p["phone"] == TELEFONO_DE_PRUEBA[3:]
        assert p["city"] == "Quito" and p["province"] == "Pichincha"
        assert p["total"] == "24.99" and p["not_COD"] == 0
        assert json.loads(p["order_details"]) == [{"sku": SKU, "name": "Audifonos Bluetooth", "quantity": 1}]
        assert r.escalada is False and r.avisos == []

    def test_deja_el_estado_de_la_venta_para_el_siguiente_turno(self):
        r = turno(compra_completa())
        assert r.estado["estado"] == "despachado"
        assert r.estado["total"] == "24.99" and r.estado["cantidad"] == 1
        assert r.estado["nombre_cliente"] == "Ana Prueba" and r.estado["metodo_pago"] == "contraentrega"
        assert r.estado["id_pedido_rocketfy"] >= simulacion.ID_PEDIDO_SIMULADO_INICIAL

    def test_el_total_lo_calcula_el_sistema_aunque_la_ia_mande_otro(self):
        llm = LLMGuionado(
            herramientas(DATOS, ("registrar_producto", {**PRODUCTO[1], "cantidad": 2, "total": "1.00"}), CONTRAENTREGA, CERRAR),
            texto("ok"),
        )
        r = turno(llm)
        assert r.estado["total"] == "49.98"
        assert json.loads(r.pedido["payload"]["order_details"])[0]["quantity"] == 2

    def test_la_variante_viaja_en_el_nombre_de_la_linea(self):
        llm = LLMGuionado(
            herramientas(DATOS, ("registrar_producto", {**PRODUCTO[1], "variante": "Negro"}), CONTRAENTREGA, CERRAR),
            texto("ok"),
        )
        r = turno(llm)
        assert json.loads(r.pedido["payload"]["order_details"])[0]["name"] == "Audifonos Bluetooth - Negro"


class TestReglasRealesDeLasHerramientas:
    """Las reglas son las de producción (se ejecuta el mismo código)."""

    def test_mas_unidades_que_el_maximo_no_se_registran(self):
        llm = LLMGuionado(herramientas(("registrar_producto", {**PRODUCTO[1], "cantidad": 3})), texto("Maximo 2."))
        r = turno(llm)
        assert "hasta 2 unidades" in r.herramientas[0]["resultado"]
        assert r.estado["producto_sku"] is None and r.estado["total"] is None

    def test_un_sku_inventado_se_corrige_por_nombre(self):
        llm = LLMGuionado(herramientas(("registrar_producto", {"producto_sku": "inventado", "producto_nombre": "audifonos bluetooth"})), texto("ok"))
        assert turno(llm).estado["producto_sku"] == SKU

    def test_transferencia_pide_comprobante_y_no_crea_pedido(self):
        llm = LLMGuionado(
            herramientas(DATOS, PRODUCTO, ("registrar_metodo_pago", {"metodo_pago": "transferencia"}), CERRAR),
            texto("Envianos el comprobante."),
        )
        r = turno(llm)
        assert "comprobante" in r.herramientas[3]["resultado"]
        assert r.pedido is None and r.estado["estado"] == "esperando_pago"

    def test_si_faltan_datos_no_se_cierra(self):
        llm = LLMGuionado(herramientas(PRODUCTO, CERRAR), texto("Me falta tu direccion."))
        r = turno(llm)
        assert r.herramientas[1]["resultado"].startswith("Faltan datos")
        assert r.pedido is None

    def test_contraentrega_bajo_el_recaudo_minimo_escala_con_el_aviso_a_la_vista(self):
        llm = LLMGuionado(herramientas(DATOS, PRODUCTO, CONTRAENTREGA, CERRAR), texto("Un asesor te contacta."))
        r = turno(llm, producto=ficha(precio=Decimal("5.00")))
        assert r.pedido is None and r.escalada is True
        assert len(r.avisos) == 1 and r.avisos[0]["canal"] == "telegram"
        assert "recaudo" in r.avisos[0]["texto"].lower()

    def test_un_canton_que_no_existe_escala(self):
        datos = ("guardar_datos_cliente", {**DATOS[1], "canton": "Narnia"})
        llm = LLMGuionado(herramientas(datos, PRODUCTO, CONTRAENTREGA, CERRAR), texto("Un asesor te contacta."))
        r = turno(llm)
        assert r.pedido is None and r.escalada is True

    def test_escalar_a_humano_avisa_pero_no_manda_nada(self):
        llm = LLMGuionado(herramientas(("escalar_a_humano", {"motivo": "Pregunta fuera de la ficha"})), texto("Te paso con un asesor."))
        r = turno(llm)
        assert r.escalada is True
        assert r.avisos == [{"canal": "telegram", "texto": "Victoria escaló la conversación. Motivo: Pregunta fuera de la ficha"}]

    def test_sin_stock_frena_la_venta_y_escala(self):
        llm = LLMGuionado(herramientas(DATOS, PRODUCTO), texto("Esta agotado."))
        r = turno(llm, producto=ficha(stock_ultimo=0))
        assert r.escalada is True and r.estado["producto_sku"] is None

    def test_herramienta_desconocida_no_rompe(self):
        llm = LLMGuionado(herramientas(("hackear", {})), texto("ok"))
        assert turno(llm).herramientas[0]["resultado"] == "Herramienta desconocida: hackear."


class TestEscenarioDelProducto:
    def test_el_producto_en_borrador_es_el_unico_disponible(self):
        llm = LLMGuionado(texto("Hola"))
        p = ficha()
        turno(llm, producto=p)
        system = llm.llamadas[0]["system"]
        assert "Audifonos Bluetooth" in system and f"SKU {SKU}" in system
        assert p["activo"] is False  # la copia es la que se marca activa, nunca la original

    def test_desde_un_anuncio_victoria_ya_conoce_el_producto(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm, desde_anuncio=True)
        system = llm.llamadas[0]["system"]
        assert "Descripción: Audifonos con 20 horas de bateria." in system
        assert "Estos son los productos disponibles" not in system

    def test_sin_anuncio_ve_la_lista_con_ese_unico_producto(self):
        llm = LLMGuionado(texto("Hola"))
        turno(llm, desde_anuncio=False)
        assert "Estos son los productos disponibles" in llm.llamadas[0]["system"]

    def test_el_mensaje_nuevo_llega_una_sola_vez_despues_del_historial(self):
        llm = LLMGuionado(texto("ok"))
        historial = [{"rol": "cliente", "contenido": "Hola"}, {"rol": "bot", "contenido": "Hola, soy Victoria"}]
        turno(llm, mensaje="Cuanto cuesta?", historial=historial)
        recibidos = [(m.rol, m.texto) for m in llm.llamadas[0]["mensajes"]]
        assert recibidos == [("user", "Hola"), ("assistant", "Hola, soy Victoria"), ("user", "Cuanto cuesta?")]

    def test_lo_que_ya_se_sabe_de_la_venta_llega_al_prompt(self):
        primero = turno(LLMGuionado(herramientas(DATOS), texto("Anotado")))
        llm = LLMGuionado(texto("ok"))
        turno(llm, estado=primero.estado)
        assert "Nombre: Ana Prueba" in llm.llamadas[0]["system"]

    def test_la_respuesta_del_bot_se_agrega_al_final_sin_tocar_el_historial_recibido(self):
        historial = [{"rol": "cliente", "contenido": "Hola"}]
        turno(LLMGuionado(texto("Hola!")), mensaje="Precio?", historial=historial)
        assert historial == [{"rol": "cliente", "contenido": "Hola"}]


class TestEstadoDeLaPrueba:
    def test_ida_y_vuelta(self):
        r = turno(compra_completa())
        lead = lead_desde_estado(r.estado)
        assert estado_desde_lead(lead) == r.estado
        assert isinstance(lead["total"], Decimal)

    def test_lo_desconocido_o_mal_tipado_se_descarta(self):
        lead = lead_desde_estado({
            "nombre_cliente": "  Ana  ", "cantidad": 0, "total": "no-es-dinero", "metodo_pago": "bitcoin",
            "estado": "inventado", "id_pedido_local": True, "telefono": "593111", "id": 99, "campo_raro": "x",
            "direccion": 123,
        })
        esperado = lead_inicial()
        esperado["nombre_cliente"] = "Ana"
        assert lead == esperado
        assert lead["telefono"] == TELEFONO_DE_PRUEBA  # el teléfono nunca viene de afuera

    def test_estado_vacio_o_nulo_es_una_venta_nueva(self):
        assert lead_desde_estado(None) == lead_inicial() == lead_desde_estado({})

    def test_un_campo_largo_se_recorta(self):
        assert len(lead_desde_estado({"direccion": "x" * 5000})["direccion"]) == simulacion.LARGO_MAXIMO_DE_UN_CAMPO


class TestCeroEfectosReales:
    """Plan de gestión de productos, Fase E: «una compra simulada completa no
    genera NINGUNA llamada a Rocketfy, Telegram o WhatsApp ni filas nuevas»."""

    @responses.activate  # sin ninguna URL registrada: cualquier petición HTTP lanza ConnectionError
    def test_una_compra_completa_no_hace_peticiones_ni_abre_la_base(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError("La simulación intentó usar la base de datos")

        monkeypatch.setattr("src.config.database._get_pool", prohibido)
        # Los constructores de los clientes REALES tampoco deben ni invocarse.
        monkeypatch.setattr("src.routes.whatsapp.tools.get_rocketfy_client", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.tools.get_telegram_notifier", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.stock.get_rocketfy_client", prohibido)

        r = turno(compra_completa())

        assert r.pedido is not None and r.pedido["confirmado"] is True
        assert len(responses.calls) == 0

    @responses.activate
    def test_escalar_tampoco_avisa_por_telegram(self, monkeypatch):
        monkeypatch.setattr("src.config.database._get_pool", lambda: (_ for _ in ()).throw(AssertionError("base")))
        llm = LLMGuionado(herramientas(("escalar_a_humano", {"motivo": "prueba"})), texto("Te paso con un asesor."))
        r = turno(llm)
        assert r.escalada is True and len(responses.calls) == 0

    @responses.activate
    def test_ni_siquiera_un_rechazo_de_rocketfy_sale_a_la_red(self, monkeypatch):
        monkeypatch.setattr("src.config.database._get_pool", lambda: (_ for _ in ()).throw(AssertionError("base")))
        r = turno(compra_completa(), producto=ficha(precio=Decimal("5.00")))
        assert r.pedido is None and len(responses.calls) == 0


FOTO = ("enviar_foto_producto", {"producto_sku": SKU})


class TestFotoDelProducto:
    def test_la_foto_queda_a_la_vista_y_no_se_envia_nada(self):
        r = turno(LLMGuionado(herramientas(FOTO), texto("Te la mando.")), mensaje="Tienes fotos?", imagenes=[FOTO_SUBIDA])
        assert [h["nombre"] for h in r.herramientas] == ["enviar_foto_producto"]
        assert "Ya le enviaste la foto" in r.herramientas[0]["resultado"]
        assert r.fotos == [{
            "mensaje": f"📷 Foto de Audifonos Bluetooth ({SKU})",
            "url": FOTO_SUBIDA["url"],
            "descripcion": "Audifonos Bluetooth",
        }]

    def test_sin_fotos_subidas_no_hay_foto_aunque_la_ficha_tenga_la_de_rocketfy(self):
        r = turno(LLMGuionado(herramientas(FOTO), texto("No tengo foto.")), producto=ficha(imagen_url="https://cdn.rocketfy.example/audifonos.png"))
        assert r.fotos == [] and "todavía no tiene fotos" in r.herramientas[0]["resultado"]

    def test_no_repite_la_foto_si_ya_esta_en_el_historial_de_la_prueba(self):
        historial = [
            {"rol": "cliente", "contenido": "Tienes fotos?"},
            {"rol": "bot", "contenido": f"📷 Foto de Audifonos Bluetooth ({SKU})"},
            {"rol": "bot", "contenido": "Te la mande."},
        ]
        r = turno(LLMGuionado(herramientas(FOTO), texto("Ya te la mande.")), mensaje="Otra vez?", historial=historial, imagenes=[FOTO_SUBIDA])
        assert r.fotos == [] and "no la repitas" in r.herramientas[0]["resultado"]

    def test_la_foto_se_ve_en_el_historial_que_recibe_el_modelo(self):
        llm = LLMGuionado(texto("ok"))
        historial = [{"rol": "bot", "contenido": f"📷 Foto de Audifonos Bluetooth ({SKU})"}]
        turno(llm, historial=historial)
        assert any("Foto de Audifonos Bluetooth" in (m.texto or "") for m in llm.llamadas[0]["mensajes"])

    def test_la_simulacion_ofrece_la_foto_aunque_en_produccion_este_apagada(self, monkeypatch):
        monkeypatch.delenv("BOT_ENVIAR_FOTOS", raising=False)
        llm = LLMGuionado(texto("Hola"))
        turno(llm)
        assert "enviar_foto_producto" in [h.nombre for h in llm.llamadas[0]["herramientas"]]

    @responses.activate
    def test_cero_efectos_ni_siquiera_se_arma_el_cliente_real_de_whatsapp(self, monkeypatch):
        def prohibido(*args, **kwargs):
            raise AssertionError("La simulación intentó usar WhatsApp o la base de datos")

        # Leer los parámetros del sistema (memoria, vueltas…) es lo único que la simulación pide a la base:
        # no escribe nada. Aquí se da por leído para que el resto de la prohibición sea estricta.
        monkeypatch.setattr("src.config.parametros.repository.ParametrosRepository.listar", staticmethod(lambda: {}))
        monkeypatch.setattr("src.config.database._get_pool", prohibido)
        monkeypatch.setattr("src.routes.whatsapp.tools.get_registro_canales", prohibido)
        r = turno(LLMGuionado(herramientas(FOTO), texto("Te la mando.")), imagenes=[FOTO_SUBIDA])
        assert len(r.fotos) == 1 and len(responses.calls) == 0
