"""Las dos ventanas de WhatsApp (servicio de 24 h y gratuita de anuncio) con la regla actual de Meta. Funciones puras."""
from datetime import datetime, timedelta, timezone

from src.routes.anuncios.ventana import ABIERTA, CERRADA, PENDIENTE, SIN_ANUNCIO, ventana_de_servicio, ventana_gratuita

AHORA = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def _m(rol, hace):
    return {"rol": rol, "creado_en": AHORA - hace}


class TestVentanaDeServicio:
    def test_sin_mensajes_del_cliente_esta_cerrada(self):
        assert ventana_de_servicio([], AHORA) == (False, None)
        assert ventana_de_servicio([_m("bot", timedelta(hours=1))], AHORA) == (False, None)

    def test_abierta_hasta_24_horas_despues_del_ultimo_mensaje_del_cliente(self):
        abierta, cierre = ventana_de_servicio([_m("cliente", timedelta(hours=2))], AHORA)
        assert abierta is True
        assert cierre == AHORA - timedelta(hours=2) + timedelta(hours=24)

    def test_cuenta_desde_el_ULTIMO_mensaje_del_cliente(self):
        mensajes = [_m("cliente", timedelta(hours=30)), _m("cliente", timedelta(hours=1))]
        assert ventana_de_servicio(mensajes, AHORA)[0] is True

    def test_responder_no_extiende_la_ventana(self):
        mensajes = [_m("cliente", timedelta(hours=30)), _m("humano", timedelta(hours=1))]
        assert ventana_de_servicio(mensajes, AHORA) == (False, None)

    def test_pasadas_24_horas_esta_cerrada(self):
        assert ventana_de_servicio([_m("cliente", timedelta(hours=24, minutes=1))], AHORA) == (False, None)


class TestVentanaGratuita:
    def test_sin_llegadas_por_anuncio(self):
        assert ventana_gratuita([], [_m("cliente", timedelta(hours=1))], AHORA)["estado"] == SIN_ANUNCIO

    def test_pendiente_mientras_no_respondamos_dentro_de_las_24_horas(self):
        llegada = AHORA - timedelta(hours=3)
        r = ventana_gratuita([llegada], [_m("cliente", timedelta(hours=3))], AHORA)
        assert r["estado"] == PENDIENTE
        assert r["responder_antes_de"] == llegada + timedelta(hours=24)
        assert r["expira_en"] is None

    def test_si_pasan_24_horas_sin_responder_se_pierde(self):
        llegada = AHORA - timedelta(hours=30)
        r = ventana_gratuita([llegada], [_m("cliente", timedelta(hours=30))], AHORA)
        assert r["estado"] == CERRADA

    def test_se_abre_cuando_respondemos_y_dura_hasta_7_dias_desde_esa_respuesta(self):
        llegada = AHORA - timedelta(hours=2)
        respuesta = AHORA - timedelta(hours=2) + timedelta(seconds=20)
        mensajes = [_m("cliente", timedelta(hours=2)), {"rol": "bot", "creado_en": respuesta}]

        r = ventana_gratuita([llegada], mensajes, AHORA)

        assert r["estado"] == ABIERTA
        assert r["expira_en"] == respuesta + timedelta(days=7)

    def test_una_respuesta_del_dueno_tambien_la_abre(self):
        llegada = AHORA - timedelta(hours=5)
        mensajes = [_m("cliente", timedelta(hours=5)), _m("humano", timedelta(hours=4))]
        assert ventana_gratuita([llegada], mensajes, AHORA)["estado"] == ABIERTA

    def test_vence_a_los_7_dias(self):
        llegada = AHORA - timedelta(days=8)
        mensajes = [{"rol": "cliente", "creado_en": llegada}, {"rol": "bot", "creado_en": llegada + timedelta(seconds=10)}]
        assert ventana_gratuita([llegada], mensajes, AHORA)["estado"] == CERRADA

    def test_una_respuesta_fuera_de_la_ventana_de_servicio_no_la_abre(self):
        """Se respondió 26 h después del último mensaje del cliente: Meta no la cuenta."""
        llegada = AHORA - timedelta(hours=30)
        mensajes = [_m("cliente", timedelta(hours=30)), _m("bot", timedelta(hours=4))]
        assert ventana_gratuita([llegada], mensajes, AHORA)["estado"] == CERRADA

    def test_si_el_cliente_vuelve_a_escribir_la_respuesta_tardia_si_cuenta(self):
        """Llegó hace 30 h, escribió otra vez hace 10 h y le respondimos hace 9 h: dentro de la ventana de servicio."""
        llegada = AHORA - timedelta(hours=30)
        mensajes = [_m("cliente", timedelta(hours=30)), _m("cliente", timedelta(hours=10)), _m("bot", timedelta(hours=9))]
        assert ventana_gratuita([llegada], mensajes, AHORA)["estado"] == ABIERTA

    def test_toma_la_ULTIMA_llegada_por_anuncio(self):
        """Respondimos a la primera llegada (hace 20 días) pero la última (hace 1 h) aún no tiene respuesta."""
        primera = AHORA - timedelta(days=20)
        ultima = AHORA - timedelta(hours=1)
        mensajes = [
            {"rol": "cliente", "creado_en": primera},
            {"rol": "bot", "creado_en": primera + timedelta(seconds=5)},
            {"rol": "cliente", "creado_en": ultima},
        ]
        r = ventana_gratuita([primera, ultima], mensajes, AHORA)
        assert r["estado"] == PENDIENTE
        assert r["responder_antes_de"] == ultima + timedelta(hours=24)

    def test_no_depende_del_orden_en_que_lleguen_los_mensajes(self):
        llegada = AHORA - timedelta(hours=2)
        mensajes = [_m("bot", timedelta(hours=2) - timedelta(seconds=30)), _m("cliente", timedelta(hours=2))]
        assert ventana_gratuita([llegada], mensajes, AHORA)["estado"] == ABIERTA
