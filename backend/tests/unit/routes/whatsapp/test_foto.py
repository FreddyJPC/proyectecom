"""
Herramienta `enviar_foto_producto` (Fase G2): Victoria manda por WhatsApp la
foto del producto. Con repositorios y WhatsApp falsos: lo que se prueba es que
solo se envíe la foto de un producto ACTIVO, desde la URL guardada (nunca una
que invente el modelo), una vez por conversación, y que cualquier fallo se le
explique a Victoria sin escalar ni romper la conversación.
"""
from unittest.mock import MagicMock

import pytest

from src.integrations.whatsapp import WhatsAppBusinessError, WhatsAppRequestError
from src.routes.whatsapp.tools import HERRAMIENTAS_VICTORIA, HERRAMIENTA_FOTO, HerramientasVictoria, herramientas_de_victoria
from tests.unit.routes.whatsapp.test_tools import (
    FakeConversacionRepository,
    FakeLeadRepository,
    FakeProductoBotRepository,
    FakeStockChecker,
)

URL = "https://cdn.rocketfy.example/reloj.png"
TELEFONO = "593987654321"


def producto(**cambios):
    datos = {
        "sku": "DEMO-1", "nombre": "Reloj deportivo", "descripcion": "Un reloj.", "precio": "24.99",
        "tiempo_entrega": "2 a 4 dias", "metodos_pago_aceptados": "contraentrega", "max_unidades_por_pedido": 1,
        "activo": True, "imagen_url": URL,
    }
    datos.update(cambios)
    return datos


class MensajesFalsos:
    def __init__(self):
        self.creados = []

    def contar_fotos(self, conversacion_id, sku):
        return sum(1 for m in self.creados if m["conversacion_id"] == conversacion_id and m["contenido"].endswith(f"({sku})"))

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None):
        self.creados.append({"conversacion_id": conversacion_id, "rol": rol, "contenido": contenido, "tipo": tipo, "wamid": wamid})
        return self.creados[-1]


class ImagenesFalsas:
    """La galería subida por el dueño: {sku: [urls]} (por defecto, ninguna: se usa la de Rocketfy)."""

    def __init__(self, por_sku=None):
        self.por_sku = por_sku or {}

    def listar(self, sku):
        return [{"id": i, "url": url, "orden": i} for i, url in enumerate(self.por_sku.get(sku, []))]


class WhatsAppFalso:
    def __init__(self, error=None):
        self.error = error
        self.enviadas = []

    def enviar_imagen(self, telefono, url, descripcion=None):
        if self.error is not None:
            raise self.error
        self.enviadas.append({"telefono": telefono, "url": url, "descripcion": descripcion})
        return {"messages": [{"id": "wamid.X"}]}


def armar(productos=None, mensajes=None, whatsapp=None, enviar_fotos=True, galeria=None):
    productos = productos if productos is not None else {"DEMO-1": producto()}
    mensajes = mensajes or MensajesFalsos()
    whatsapp = whatsapp or WhatsAppFalso()
    telegram = MagicMock()
    herramientas = HerramientasVictoria(
        lead_repo=FakeLeadRepository({1: {"telefono": TELEFONO}}),
        conversacion_repo=FakeConversacionRepository(),
        producto_repo=FakeProductoBotRepository(productos),
        pedido_service=MagicMock(),
        telegram_notifier=telegram,
        stock_checker=FakeStockChecker(),
        minimo_repo=MagicMock(),
        mensaje_repo=mensajes,
        whatsapp_client=whatsapp,
        enviar_fotos=enviar_fotos,
        imagen_repo=ImagenesFalsas(galeria),
    )
    return herramientas, mensajes, whatsapp, telegram


def enviar(herramientas, sku="DEMO-1", conversacion_id=7):
    return herramientas.ejecutar("enviar_foto_producto", lead_id=1, conversacion_id=conversacion_id, entrada={"producto_sku": sku}, id_llamada="t1").contenido


class TestEnviarFoto:
    def test_envia_la_foto_guardada_al_telefono_del_cliente_y_deja_el_mensaje(self):
        h, mensajes, whatsapp, _ = armar()
        respuesta = enviar(h)

        assert whatsapp.enviadas == [{"telefono": TELEFONO, "url": URL, "descripcion": "Reloj deportivo"}]
        assert mensajes.creados == [
            {"conversacion_id": 7, "rol": "bot", "contenido": "📷 Foto de Reloj deportivo (DEMO-1)", "tipo": "imagen", "wamid": None}
        ]
        assert "Ya le enviaste la foto" in respuesta and "Quedan" not in respuesta

    def test_una_ruta_relativa_de_rocketfy_se_completa_con_el_sitio_de_la_api(self, monkeypatch):
        monkeypatch.setenv("ROCKETFY_BASE_URL", "https://rocket-e.com/api")
        h, _, whatsapp, _ = armar({"DEMO-1": producto(imagen_url="/storage/products/4193/foto.jpg")})
        enviar(h)
        assert whatsapp.enviadas[0]["url"] == "https://rocket-e.com/storage/products/4193/foto.jpg"

    def test_si_el_sitio_de_la_api_no_es_https_la_ruta_relativa_no_se_envia(self, monkeypatch):
        # Meta solo descarga enlaces https: mejor no enviar que enviar algo que no llegará.
        monkeypatch.setenv("ROCKETFY_BASE_URL", "http://rocket-e.com/api")
        h, _, whatsapp, _ = armar({"DEMO-1": producto(imagen_url="/storage/products/4193/foto.jpg")})
        assert "todavía no tiene fotos" in enviar(h) and whatsapp.enviadas == []

    def test_la_url_sale_de_la_base_no_de_lo_que_diga_el_modelo(self):
        h, _, whatsapp, _ = armar()
        h.ejecutar("enviar_foto_producto", 1, 7, {"producto_sku": "DEMO-1", "url": "https://malo.example/x.png"}, "t1")
        assert whatsapp.enviadas[0]["url"] == URL

    def test_un_sku_mal_copiado_se_corrige_por_nombre(self):
        h, _, whatsapp, _ = armar()
        enviar(h, sku="reloj deportivo")
        assert len(whatsapp.enviadas) == 1

    def test_no_repite_la_foto_en_la_misma_conversacion(self):
        h, _, whatsapp, _ = armar()
        enviar(h)
        segunda = enviar(h)
        assert len(whatsapp.enviadas) == 1 and "no la repitas" in segunda

    def test_en_otra_conversacion_si_se_envia(self):
        h, _, whatsapp, _ = armar()
        enviar(h, conversacion_id=7)
        enviar(h, conversacion_id=8)
        assert len(whatsapp.enviadas) == 2

    def test_un_producto_pausado_no_se_envia(self):
        h, _, whatsapp, _ = armar({"DEMO-1": producto(activo=False)})
        assert "No encontré ese producto" in enviar(h)
        assert whatsapp.enviadas == []

    def test_un_sku_inexistente_devuelve_el_catalogo_y_no_envia(self):
        h, _, whatsapp, _ = armar()
        respuesta = enviar(h, sku="NO-EXISTE")
        assert "No encontré ese producto" in respuesta and "DEMO-1" in respuesta
        assert whatsapp.enviadas == []

    @pytest.mark.parametrize("imagen", [None, "", "   ", "http://inseguro.example/x.png", "ftp://x/y.png", "/ruta/local.png"])
    def test_sin_foto_valida_no_envia_y_no_promete(self, imagen):
        h, mensajes, whatsapp, _ = armar({"DEMO-1": producto(imagen_url=imagen)})
        respuesta = enviar(h)
        assert "todavía no tiene fotos" in respuesta and "por el momento no hay imágenes" in respuesta
        assert "no le prometas" in respuesta
        assert whatsapp.enviadas == [] and mensajes.creados == []

    @pytest.mark.parametrize("error", [WhatsAppBusinessError("Media upload error", 131053), WhatsAppRequestError("sin red"), RuntimeError("bug")])
    def test_si_whatsapp_falla_se_le_explica_a_victoria_y_no_se_registra_ni_escala(self, error):
        h, mensajes, _, telegram = armar(whatsapp=WhatsAppFalso(error=error))
        respuesta = enviar(h)
        assert "No se pudieron enviar las fotos" in respuesta
        assert mensajes.creados == []  # no quedó registrada: se puede volver a intentar
        telegram.notificar_escalado.assert_not_called()

    def test_el_cliente_de_whatsapp_real_no_se_arma_hasta_que_hace_falta(self, monkeypatch):
        def prohibido():
            raise AssertionError("se armó el cliente de WhatsApp sin necesitarlo")

        monkeypatch.setattr("src.routes.whatsapp.tools.get_whatsapp_client", prohibido)
        h = HerramientasVictoria(
            lead_repo=FakeLeadRepository(), conversacion_repo=FakeConversacionRepository(), producto_repo=FakeProductoBotRepository(),
            pedido_service=MagicMock(), telegram_notifier=MagicMock(), stock_checker=FakeStockChecker(), minimo_repo=MagicMock(),
            mensaje_repo=MensajesFalsos(), enviar_fotos=True,
        )
        assert h.ejecutar("ver_ficha_producto", 1, 7, {"producto_sku": "x"}, "t1")  # otra herramienta: no toca WhatsApp


URL_A = "https://xyz.supabase.co/storage/v1/object/public/productos/DEMO-1/a.jpg"
URL_B = "https://xyz.supabase.co/storage/v1/object/public/productos/DEMO-1/b.jpg"
URL_C = "https://xyz.supabase.co/storage/v1/object/public/productos/DEMO-1/c.jpg"
URL_D = "https://xyz.supabase.co/storage/v1/object/public/productos/DEMO-1/d.jpg"


class TestGaleria:
    """ADR-012: las fotos que el dueño sube a la ficha (bucket de Supabase) mandan sobre la de Rocketfy."""

    def test_manda_las_fotos_subidas_y_no_la_de_rocketfy(self):
        h, _, whatsapp, _ = armar(galeria={"DEMO-1": [URL_A, URL_B]})
        enviar(h)
        assert [e["url"] for e in whatsapp.enviadas] == [URL_A, URL_B]

    def test_solo_la_primera_lleva_el_nombre_del_producto_como_texto(self):
        h, _, whatsapp, _ = armar(galeria={"DEMO-1": [URL_A, URL_B]})
        enviar(h)
        assert [e["descripcion"] for e in whatsapp.enviadas] == ["Reloj deportivo", None]

    def test_cada_foto_queda_como_un_mensaje_del_bot(self):
        h, mensajes, _, _ = armar(galeria={"DEMO-1": [URL_A, URL_B]})
        enviar(h)
        assert [m["contenido"] for m in mensajes.creados] == ["📷 Foto de Reloj deportivo (DEMO-1)"] * 2
        assert all(m["tipo"] == "imagen" and m["rol"] == "bot" for m in mensajes.creados)

    def test_manda_por_tandas_y_la_siguiente_sigue_donde_quedo(self):
        h, _, whatsapp, _ = armar(galeria={"DEMO-1": [URL_A, URL_B, URL_C, URL_D]})

        primera = enviar(h)
        assert [e["url"] for e in whatsapp.enviadas] == [URL_A, URL_B, URL_C]  # el valor por defecto son 3
        assert "Quedan 1 más" in primera

        segunda = enviar(h)
        assert [e["url"] for e in whatsapp.enviadas][3:] == [URL_D] and "Quedan" not in segunda

        tercera = enviar(h)
        assert len(whatsapp.enviadas) == 4 and "no las repitas" in tercera

    def test_el_tamano_de_la_tanda_es_un_parametro_que_se_cambia_desde_la_app(self, monkeypatch):
        from src.config.parametros import parametros

        monkeypatch.setattr(parametros, "valor", lambda clave: 1 if clave == "bot.max_fotos_por_envio" else True)
        h, _, whatsapp, _ = armar(galeria={"DEMO-1": [URL_A, URL_B]})
        enviar(h)
        assert [e["url"] for e in whatsapp.enviadas] == [URL_A]

    def test_si_falla_a_la_mitad_cuenta_solo_las_enviadas_y_lo_dice(self):
        class FallaLaSegunda(WhatsAppFalso):
            ya_fallo = False

            def enviar_imagen(self, telefono, url, descripcion=None):
                if self.enviadas and not self.ya_fallo:
                    self.ya_fallo = True
                    raise WhatsAppRequestError("sin red")
                return super().enviar_imagen(telefono, url, descripcion)

        h, mensajes, whatsapp, _ = armar(whatsapp=FallaLaSegunda(), galeria={"DEMO-1": [URL_A, URL_B]})
        respuesta = enviar(h)
        assert len(whatsapp.enviadas) == 1 and len(mensajes.creados) == 1
        assert "solo se pudieron enviar algunas" in respuesta
        assert [e["url"] for e in whatsapp.enviadas] == [URL_A]
        assert enviar(h) and whatsapp.enviadas[-1]["url"] == URL_B  # el reintento sigue en la que faltaba

    def test_una_foto_subida_que_no_es_https_se_ignora_y_usa_la_de_rocketfy(self):
        h, _, whatsapp, _ = armar(galeria={"DEMO-1": ["http://inseguro.example/a.jpg"]})
        enviar(h)
        assert [e["url"] for e in whatsapp.enviadas] == [URL]

    def test_sin_fotos_en_ninguna_parte_dice_que_por_ahora_no_hay_imagenes(self):
        h, mensajes, whatsapp, _ = armar({"DEMO-1": producto(imagen_url=None)})
        respuesta = enviar(h)
        assert "por el momento no hay imágenes" in respuesta
        assert whatsapp.enviadas == [] and mensajes.creados == []

    def test_con_fotos_subidas_no_hace_falta_la_de_rocketfy(self):
        h, _, whatsapp, _ = armar({"DEMO-1": producto(imagen_url=None)}, galeria={"DEMO-1": [URL_A]})
        enviar(h)
        assert [e["url"] for e in whatsapp.enviadas] == [URL_A]


class TestInterruptor:
    def test_apagado_la_herramienta_no_se_ofrece_ni_se_ejecuta(self):
        assert HERRAMIENTA_FOTO not in herramientas_de_victoria(False)
        h, _, whatsapp, _ = armar(enviar_fotos=False)
        assert enviar(h) == "Herramienta desconocida: enviar_foto_producto."
        assert whatsapp.enviadas == []

    def test_encendido_se_agrega_al_final_sin_tocar_las_demas(self):
        herramientas = herramientas_de_victoria(True)
        assert herramientas[:-1] == HERRAMIENTAS_VICTORIA and herramientas[-1] is HERRAMIENTA_FOTO
        assert len(herramientas_de_victoria(False)) == len(HERRAMIENTAS_VICTORIA)

    def test_la_lista_base_no_cambia_por_haber_agregado_la_foto(self):
        assert "enviar_foto_producto" not in [h.nombre for h in HERRAMIENTAS_VICTORIA]
        assert HERRAMIENTA_FOTO.parametros["required"] == ["producto_sku"]

    @pytest.mark.parametrize(
        "valor, esperado",
        [(None, False), ("", False), ("false", False), ("False", False), ("0", False), ("no", False), ("true", True), ("TRUE", True), ("1", True), ("si", True)],
    )
    def test_la_variable_de_entorno_sigue_valiendo_como_respaldo(self, monkeypatch, valor, esperado):
        from src.config.parametros import parametros

        if valor is None:
            monkeypatch.delenv("BOT_ENVIAR_FOTOS", raising=False)
        else:
            monkeypatch.setenv("BOT_ENVIAR_FOTOS", valor)
        assert parametros.valor("bot.enviar_fotos") is esperado

    def test_sin_fijarla_la_herramienta_obedece_al_parametro_en_cada_llamada(self, monkeypatch):
        """Encender las fotos desde la app se nota en la siguiente llamada, sin reiniciar."""
        h, _, whatsapp, _ = armar(enviar_fotos=None)
        monkeypatch.delenv("BOT_ENVIAR_FOTOS", raising=False)
        assert "Herramienta desconocida" in enviar(h) and whatsapp.enviadas == []

        monkeypatch.setenv("BOT_ENVIAR_FOTOS", "true")  # equivale a encenderla en Parámetros
        assert "Ya le enviaste la foto" in enviar(h) and len(whatsapp.enviadas) == 1


# ----------------------------------------------------------------------
# Repositorios reales (base local)
# ----------------------------------------------------------------------
from src.config.database import get_connection  # noqa: E402
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository, ProductoBotRepository  # noqa: E402

TELEFONO_DE_PRUEBA = "593900009999"
TELEFONO_OTRO = "593900009998"
SKU_REAL = "TEST-G2-FOTO"


def _limpiar_base():
    with get_connection() as conn:
        with conn.cursor() as cur:
            telefonos = [TELEFONO_DE_PRUEBA, TELEFONO_OTRO]
            cur.execute("delete from mensajes where conversacion_id in (select id from conversaciones where telefono = any(%s))", (telefonos,))
            cur.execute("delete from conversaciones where telefono = any(%s)", (telefonos,))
            cur.execute("delete from productos_bot where sku = %s", (SKU_REAL,))


@pytest.fixture
def conversacion():
    _limpiar_base()
    c = ConversacionRepository.crear(telefono=TELEFONO_DE_PRUEBA, origen="directo")
    yield c["id"]
    _limpiar_base()


class TestContarFotosContraLaBase:
    def test_sin_fotos_es_cero(self, conversacion):
        assert MensajeRepository.contar_fotos(conversacion, "DEMO-1") == 0

    def test_cada_foto_del_bot_se_cuenta_por_su_sku(self, conversacion):
        MensajeRepository.crear(conversacion, "bot", "📷 Foto de Reloj (DEMO-1)", tipo="imagen")
        MensajeRepository.crear(conversacion, "bot", "📷 Foto de Reloj (DEMO-1)", tipo="imagen")
        assert MensajeRepository.contar_fotos(conversacion, "DEMO-1") == 2
        assert MensajeRepository.contar_fotos(conversacion, "DEMO-2") == 0

    def test_no_se_confunde_con_un_texto_normal_que_nombra_el_sku(self, conversacion):
        MensajeRepository.crear(conversacion, "bot", "Mira el producto (DEMO-1)", tipo="texto")
        MensajeRepository.crear(conversacion, "cliente", "📷 Foto de Reloj (DEMO-1)", tipo="imagen")  # imagen del CLIENTE
        assert MensajeRepository.contar_fotos(conversacion, "DEMO-1") == 0

    def test_es_por_conversacion(self, conversacion):
        otra = ConversacionRepository.crear(telefono=TELEFONO_OTRO, origen="directo")["id"]
        MensajeRepository.crear(conversacion, "bot", "📷 Foto de Reloj (DEMO-1)", tipo="imagen")
        assert MensajeRepository.contar_fotos(otra, "DEMO-1") == 0

    @pytest.mark.parametrize("sku", ["A%B", "A_B", "100%", "X'Y"])
    def test_un_sku_con_comodines_o_comillas_se_busca_literal(self, conversacion, sku):
        MensajeRepository.crear(conversacion, "bot", "📷 Foto de Otro (ABB)", tipo="imagen")
        assert MensajeRepository.contar_fotos(conversacion, sku) == 0
        MensajeRepository.crear(conversacion, "bot", f"📷 Foto de Raro ({sku})", tipo="imagen")
        assert MensajeRepository.contar_fotos(conversacion, sku) == 1


class TestElProductoDelBotTraeLaImagen:
    def test_obtener_por_sku_incluye_imagen_url(self):
        _limpiar_base()
        try:
            ProductoBotRepository.crear(sku=SKU_REAL, nombre="Reloj G2", descripcion="x", precio="19.99", tiempo_entrega="2 dias")
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("update productos_bot set imagen_url = %s where sku = %s", (URL, SKU_REAL))
            assert ProductoBotRepository.obtener_por_sku(SKU_REAL)["imagen_url"] == URL
        finally:
            _limpiar_base()
