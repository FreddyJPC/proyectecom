"""Servicio de leads con la base real: quién puede cambiar la temperatura, Victoria, «no contactar» y el enfriamiento."""
from datetime import datetime, timedelta, timezone

import pytest

from src.config.database import get_connection
from src.config.parametros import parametros
from src.routes.leads.exceptions import ContactoNoEncontradoError, DatosInvalidosError, LeadNoEncontradoError, VentaYaCerradaError
from src.routes.leads.repository import LeadsRepository
from src.routes.leads.servicio import LeadsServicio, desde_de_periodo
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

T1, T2, T3 = "593900005001", "593900005002", "593900005003"
DUENO = "freddy@azoshop.ec"


@pytest.fixture(autouse=True)
def limpio():
    borrar_conversaciones_de_prueba(T1, T2, T3)
    yield
    borrar_conversaciones_de_prueba(T1, T2, T3)


@pytest.fixture
def servicio():
    return LeadsServicio()


def _lead(telefono=T1):
    conv = ConversacionRepository.crear(id_externo=telefono)
    return LeadRepository.obtener_o_crear(conv["id"], conv["contacto_id"], telefono), conv


def _escribio_hace(conv, dias):
    MensajeRepository.crear(conv["id"], "cliente", "hola")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("update mensajes set creado_en = now() - make_interval(days => %s) where conversacion_id = %s", (dias, conv["id"]))


class TestElDuenoCambiaLaTemperatura:
    def test_cambia_y_la_deja_fijada_por_los_dias_del_parametro(self, servicio):
        lead, _ = _lead()
        detalle = servicio.cambiar_temperatura(lead["id"], "caliente", None, "Quiere comprar ya", DUENO)
        assert (detalle["lead"]["temperatura"], detalle["lead"]["temperatura_origen"]) == ("caliente", "dueno")
        dias = (detalle["lead"]["temperatura_fijada_hasta"] - datetime.now(timezone.utc)).total_seconds() / 86400
        assert 6.9 < dias < 7.1  # leads.dias_fijar = 7
        assert detalle["historial"][0]["usuario"] == DUENO and detalle["historial"][0]["motivo"] == "Quiere comprar ya"

    def test_perdido_pide_motivo_del_catalogo_y_por_defecto_es_otro(self, servicio):
        lead, _ = _lead()
        assert servicio.cambiar_temperatura(lead["id"], "perdido", None, None, DUENO)["lead"]["motivo_perdida"] == "otro"
        lead2, _ = _lead(T2)
        with pytest.raises(DatosInvalidosError):
            servicio.cambiar_temperatura(lead2["id"], "perdido", "porque sí", None, DUENO)

    def test_un_lead_perdido_no_queda_fijado(self, servicio):
        lead, _ = _lead()
        assert servicio.cambiar_temperatura(lead["id"], "perdido", "precio", None, DUENO)["lead"]["temperatura_fijada_hasta"] is None

    def test_una_temperatura_desconocida_se_rechaza(self, servicio):
        lead, _ = _lead()
        with pytest.raises(DatosInvalidosError):
            servicio.cambiar_temperatura(lead["id"], "hirviendo", None, None, DUENO)

    def test_una_venta_cerrada_manda_sobre_la_temperatura(self, servicio):
        lead, _ = _lead()
        LeadRepository.actualizar_despacho(lead["id"], 1, 2)
        with pytest.raises(VentaYaCerradaError):
            servicio.cambiar_temperatura(lead["id"], "frio", None, None, DUENO)
        assert servicio.cambiar_temperatura(lead["id"], "ganado", None, None, DUENO)["lead"]["temperatura"] == "ganado"  # lo mismo que ya es: permitido

    def test_un_lead_que_no_existe(self, servicio):
        with pytest.raises(LeadNoEncontradoError):
            servicio.cambiar_temperatura(999999999, "frio", None, None, DUENO)


class TestVictoriaClasifica:
    def test_aplica_y_deja_su_motivo(self, servicio):
        lead, _ = _lead()
        assert servicio.clasificar_por_ia(lead["id"], "caliente", "Dio sus datos y preguntó cómo pagar")["aplicado"] is True
        actual = LeadsRepository.obtener(lead["id"])
        assert (actual["temperatura"], actual["temperatura_origen"], actual["temperatura_motivo"]) == (
            "caliente", "ia", "Dio sus datos y preguntó cómo pagar")

    def test_no_pisa_lo_que_fijo_el_dueno(self, servicio):
        lead, _ = _lead()
        servicio.cambiar_temperatura(lead["id"], "frio", None, "Lo conozco, no compra", DUENO)
        respuesta = servicio.clasificar_por_ia(lead["id"], "caliente", "Parece interesado")
        assert respuesta["aplicado"] is False and "dueño" in respuesta["razon"]
        assert LeadsRepository.obtener(lead["id"])["temperatura"] == "frio"

    def test_vuelve_a_poder_cuando_vence_la_fijacion(self, servicio):
        lead, _ = _lead()
        servicio.cambiar_temperatura(lead["id"], "frio", None, None, DUENO)
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("update leads set temperatura_fijada_hasta = now() - interval '1 minute' where id = %s", (lead["id"],))
        assert servicio.clasificar_por_ia(lead["id"], "caliente", "Volvió con ganas")["aplicado"] is True

    def test_no_puede_dar_ganado_la_venta_lo_decide(self, servicio):
        lead, _ = _lead()
        respuesta = servicio.clasificar_por_ia(lead["id"], "ganado", "Seguro compra")
        assert respuesta["aplicado"] is False and "venta" in respuesta["razon"]
        assert LeadsRepository.obtener(lead["id"])["temperatura"] == "tibio"

    def test_no_reabre_un_lead_terminado(self, servicio):
        lead, _ = _lead()
        servicio.clasificar_por_ia(lead["id"], "perdido", "Dijo que no", "no_le_interesa")
        respuesta = servicio.clasificar_por_ia(lead["id"], "caliente", "Ahora sí")
        assert respuesta["aplicado"] is False and "terminó" in respuesta["razon"]

    def test_perdido_lleva_un_motivo_del_catalogo_o_otro(self, servicio):
        lead, _ = _lead()
        servicio.clasificar_por_ia(lead["id"], "perdido", "Muy caro", "inventado")
        assert LeadsRepository.obtener(lead["id"])["motivo_perdida"] == "otro"

    def test_temperatura_desconocida_o_lead_inexistente_no_lanzan(self, servicio):
        lead, _ = _lead()
        assert servicio.clasificar_por_ia(lead["id"], "templado", "x")["aplicado"] is False
        assert servicio.clasificar_por_ia(999999999, "caliente", "x")["aplicado"] is False


class TestNoContactar:
    def test_el_dueno_lo_marca_y_lo_quita(self, servicio):
        lead, conv = _lead()
        servicio.marcar_no_contactar(conv["contacto_id"], True, "Me lo pidió por teléfono", DUENO)
        assert LeadsRepository.obtener(lead["id"])["no_contactar"] is True
        servicio.marcar_no_contactar(conv["contacto_id"], False, None, DUENO)
        assert LeadsRepository.obtener(lead["id"])["no_contactar"] is False

    def test_victoria_lo_marca_con_su_origen(self, servicio):
        lead, conv = _lead()
        assert servicio.no_contactar_por_ia(conv["contacto_id"], None) is True
        ficha = LeadsRepository.ficha_de_contacto(conv["contacto_id"])
        assert (ficha["no_contactar_por"], ficha["no_contactar_motivo"]) == ("ia", "El cliente pidió que no lo contacten")

    def test_contacto_inexistente(self, servicio):
        with pytest.raises(ContactoNoEncontradoError):
            servicio.marcar_no_contactar(999999999, True, None, DUENO)


class TestEnfriamiento:
    def test_enfria_segun_los_dias_de_silencio_y_deja_el_motivo(self, servicio):
        lead, conv = _lead()
        LeadsRepository.fijar_temperatura(lead["id"], "caliente", "ia")
        _escribio_hace(conv, 6)  # umbrales por defecto 2 / 5 / 14: 6 días => frío
        resultado = servicio.enfriar_por_silencio()
        actual = LeadsRepository.obtener(lead["id"])
        assert resultado["enfriados"] >= 1 and (actual["temperatura"], actual["temperatura_origen"]) == ("frio", "regla")
        assert "hace 6 días" in actual["temperatura_motivo"]

    def test_perdido_por_silencio_guarda_sin_respuesta_como_motivo(self, servicio):
        lead, conv = _lead()
        _escribio_hace(conv, 20)
        servicio.enfriar_por_silencio()
        actual = LeadsRepository.obtener(lead["id"])
        assert (actual["temperatura"], actual["motivo_perdida"]) == ("perdido", "sin_respuesta")

    def test_el_cliente_que_escribio_hace_poco_no_se_enfria(self, servicio):
        lead, conv = _lead()
        _escribio_hace(conv, 0)
        servicio.enfriar_por_silencio()
        assert LeadsRepository.obtener(lead["id"])["temperatura"] == "tibio"

    def test_no_toca_lo_fijado_por_el_dueno_ni_conversaciones_en_manos_del_dueno(self, servicio):
        fijado, c1 = _lead(T1)
        escalado, c2 = _lead(T2)
        servicio.cambiar_temperatura(fijado["id"], "caliente", None, None, DUENO)
        ConversacionRepository.marcar_escalada(c2["id"])
        _escribio_hace(c1, 30)
        _escribio_hace(c2, 30)
        servicio.enfriar_por_silencio()
        assert LeadsRepository.obtener(fijado["id"])["temperatura"] == "caliente"
        assert LeadsRepository.obtener(escalado["id"])["temperatura"] == "tibio"

    def test_el_interruptor_apagado_no_hace_nada(self, servicio):
        lead, conv = _lead()
        _escribio_hace(conv, 30)
        parametros.guardar("leads.enfriar_activo", False, "test@ejemplo.com")
        try:
            assert servicio.enfriar_por_silencio() == {"revisados": 0, "enfriados": 0}
        finally:
            parametros.restaurar("leads.enfriar_activo", "test@ejemplo.com")
        assert LeadsRepository.obtener(lead["id"])["temperatura"] == "tibio"

    def test_los_dias_se_ajustan_desde_los_parametros(self, servicio):
        lead, conv = _lead()
        _escribio_hace(conv, 3)
        parametros.guardar("leads.dias_a_tibio", 1, "test@ejemplo.com")
        parametros.guardar("leads.dias_a_frio", 2, "test@ejemplo.com")
        try:
            servicio.enfriar_por_silencio()
        finally:
            parametros.restaurar("leads.dias_a_tibio", "test@ejemplo.com")
            parametros.restaurar("leads.dias_a_frio", "test@ejemplo.com")
        assert LeadsRepository.obtener(lead["id"])["temperatura"] == "frio"

    def test_correr_dos_veces_no_repite_cambios(self, servicio):
        lead, conv = _lead()
        _escribio_hace(conv, 6)
        servicio.enfriar_por_silencio()
        assert servicio.enfriar_por_silencio()["enfriados"] == 0
        assert len(LeadsRepository.historial(lead["id"])) == 2


class TestLecturas:
    def test_el_resumen_calcula_la_tasa_de_cierre_de_los_leads_terminados(self, servicio, monkeypatch):
        monkeypatch.setattr(
            LeadsRepository, "resumen",
            staticmethod(lambda desde: {"calientes": 1, "tibios": 2, "frios": 3, "valor_en_juego": 150, "ganados": 3, "ingresos_ganados": 90,
                                         "perdidos": 1, "nuevos": 9, "no_contactar": 2,
                                         "motivos_de_perdida": [{"motivo": "precio", "leads": 1}]}),
        )
        r = servicio.resumen(30)
        assert str(r["tasa_de_cierre"]) == "75.0" and r["motivos_de_perdida"][0]["etiqueta"] == "El precio"
        assert (r["calientes"], r["valor_en_juego"], r["no_contactar"]) == (1, 150, 2)

    def test_sin_leads_terminados_no_hay_tasa(self, servicio, monkeypatch):
        monkeypatch.setattr(
            LeadsRepository, "resumen",
            staticmethod(lambda desde: {"calientes": 0, "tibios": 0, "frios": 0, "valor_en_juego": 0, "ganados": 0, "ingresos_ganados": 0,
                                         "perdidos": 0, "nuevos": 0, "no_contactar": 0, "motivos_de_perdida": []}),
        )
        assert servicio.resumen(None)["tasa_de_cierre"] is None

    def test_el_detalle_trae_el_tipo_de_contacto(self, servicio):
        lead, conv = _lead()
        assert servicio.detalle(lead["id"])["contacto"]["tipo"] == "prospecto"
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(
                "insert into ventas (contacto_id, conversacion_id, proveedor_id, estado, subtotal, total, telefono) "
                "values (%s, %s, 1, 'despachada', 10, 10, %s), (%s, %s, 1, 'despachada', 20, 20, %s)",
                (conv["contacto_id"], conv["id"], T1, conv["contacto_id"], conv["id"], T1),
            )
        assert servicio.detalle(lead["id"])["contacto"]["tipo"] == "recurrente"

    def test_filtros_invalidos_se_rechazan_antes_de_llegar_a_la_base(self, servicio):
        with pytest.raises(DatosInvalidosError):
            servicio.listar(temperaturas=["tibia"])
        with pytest.raises(DatosInvalidosError):
            servicio.listar(orden="1; drop table leads")

    def test_el_tamano_de_pagina_se_acota(self, servicio):
        assert servicio.listar(page_size=100000)["page_size"] == 100 and servicio.listar(page=-3)["page"] == 1

    def test_periodo(self):
        ahora = datetime(2026, 11, 9, tzinfo=timezone.utc)
        assert desde_de_periodo(30, ahora) == ahora - timedelta(days=30) and desde_de_periodo(None) is None
