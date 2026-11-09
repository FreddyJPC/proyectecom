"""
De punta a punta contra la base real: un mensaje de WhatsApp CON la forma documentada por Meta para un anuncio de
Click-to-WhatsApp entra por el webhook y todo queda guardado. Telegram y el bot, simulados.

Importante: en producción nunca ha llegado un anuncio real todavía (0 conversaciones por anuncio al 2026-11-09), así
que esta prueba usa el formato que Meta documenta. Cuando llegue el primero real, hay que compararlo con este.
"""
from unittest.mock import MagicMock

import pytest

from src.config.database import get_connection
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.anuncios.servicio import AnuncioServicio
from src.routes.whatsapp.controllers import _extraer_mensajes
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository
from src.routes.whatsapp.services import WebhookService
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900008001"
ANUNCIO_1, ANUNCIO_2 = "test-anuncio-p1", "test-anuncio-p2"


def _limpiar():
    borrar_conversaciones_de_prueba(TELEFONO)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from anuncios_productos where id_anuncio like 'test-anuncio-%'")


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _payload(wamid, anuncio=None, texto="Hola, quiero información"):
    mensaje = {"id": wamid, "from": TELEFONO, "timestamp": "1786000000", "type": "text", "text": {"body": texto}}
    if anuncio:
        mensaje["referral"] = {
            "source_url": f"https://fb.me/{anuncio}",
            "source_id": anuncio,
            "source_type": "ad",
            "body": "Texto principal del anuncio",
            "headline": f"Titular {anuncio}",
            "media_type": "image",
            "image_url": "https://scontent.fb/imagen.jpg",
            "ctwa_clid": f"clic-{anuncio}",
            "welcome_message": {"text": "¡Hola! ¿En qué te ayudamos?"},
        }
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": {"messaging_product": "whatsapp", "messages": [mensaje]}}]}],
    }


def _procesar(payload, telegram=None, bot=None):
    servicio = WebhookService(
        whatsapp_client=MagicMock(), telegram_notifier=telegram or MagicMock(), bot_worker=bot or MagicMock(),
        anuncio_servicio=AnuncioServicio(),
    )
    for dto in _extraer_mensajes(payload):
        servicio.procesar_mensaje_entrante(dto)


def test_un_cliente_nuevo_que_llega_por_un_anuncio_queda_con_todos_los_datos():
    telegram, bot = MagicMock(), MagicMock()

    _procesar(_payload("wamid.P1", ANUNCIO_1), telegram, bot)

    conversacion = ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)
    assert (conversacion["origen"], conversacion["id_anuncio"], conversacion["ctwa_clid"]) == ("anuncio", ANUNCIO_1, f"clic-{ANUNCIO_1}")
    llegada = AnuncioRepository.llegadas_de(conversacion["id"])[0]
    assert llegada["titulo"] == f"Titular {ANUNCIO_1}"
    assert llegada["texto"] == "Texto principal del anuncio"
    assert llegada["url_anuncio"] == f"https://fb.me/{ANUNCIO_1}"
    assert llegada["imagen_url"] == "https://scontent.fb/imagen.jpg"
    assert llegada["mensaje_bienvenida"] == "¡Hola! ¿En qué te ayudamos?"
    # el mensaje del cliente está guardado y enlazado a la llegada
    mensaje = MensajeRepository.obtener_por_conversacion(conversacion["id"])[0]
    assert llegada["mensaje_id"] == mensaje["id"]
    bot.encolar.assert_called_once()  # y Victoria respondió igual
    telegram.notificar_aviso.assert_called_once()  # anuncio nuevo sin vincular -> avisa al dueño


def test_el_mismo_webhook_reenviado_por_meta_no_duplica_nada():
    _procesar(_payload("wamid.P1", ANUNCIO_1))
    _procesar(_payload("wamid.P1", ANUNCIO_1))

    conversacion = ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)
    assert len(AnuncioRepository.llegadas_de(conversacion["id"])) == 1
    assert len(MensajeRepository.obtener_por_conversacion(conversacion["id"])) == 1


def test_un_cliente_que_ya_existia_y_vuelve_por_otro_anuncio_actualiza_el_origen():
    _procesar(_payload("wamid.P1"))  # primero escribió directo
    assert ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)["origen"] == "directo"

    _procesar(_payload("wamid.P2", ANUNCIO_1))
    _procesar(_payload("wamid.P3", ANUNCIO_2))

    conversacion = ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)
    assert (conversacion["origen"], conversacion["id_anuncio"]) == ("anuncio", ANUNCIO_2)
    assert [l["id_anuncio"] for l in AnuncioRepository.llegadas_de(conversacion["id"])] == [ANUNCIO_2, ANUNCIO_1]


def test_con_el_anuncio_vinculado_victoria_sabe_de_que_producto_hablar_sin_preguntar():
    from src.routes.whatsapp.repository import ProductoBotRepository
    from src.routes.productos_bot.repository import ProductoBotGestionRepository as ProductosRepo
    from decimal import Decimal

    sku = ProductosRepo.crear_propio(
        {
            "nombre": "TEST-ANUNCIOS Zapatos", "descripcion": "Zapatos", "precio": Decimal("30.00"), "tiempo_entrega": "2 días",
            "metodos_pago_aceptados": "contraentrega", "max_unidades_por_pedido": 5, "costo_propio": Decimal("18.00"),
            "controla_stock": True, "stock_ultimo": 5, "envio_incluido": True, "costo_flete_estimado": None, "categoria_id": None,
        },
        [],
    )["sku"]
    try:
        AnuncioServicio().vincular(ANUNCIO_1, sku, "Video 1")
        telegram = MagicMock()

        _procesar(_payload("wamid.P1", ANUNCIO_1), telegram)

        telegram.notificar_aviso.assert_not_called()  # ya estaba vinculado: no es un anuncio «nuevo sin vincular»
        conversacion = ConversacionRepository.obtener_por_canal("whatsapp", TELEFONO)
        assert ProductoBotRepository.obtener_por_id_anuncio(conversacion["id_anuncio"])["sku"] == sku
    finally:
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("delete from anuncios_productos where id_anuncio like 'test-anuncio-%'")
            cur.execute("delete from productos_bot where nombre like 'TEST-ANUNCIOS %'")
