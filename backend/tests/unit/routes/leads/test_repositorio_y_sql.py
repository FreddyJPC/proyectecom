"""
Leads contra la base real de pruebas (migración 025): un lead abierto por contacto, historial de cada cambio, atribución por
lead, «no contactar» en el contacto, y las consultas de la pantalla (lista, resumen, ficha del contacto).
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.anuncios.referral import normalizar_referral
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.leads.exceptions import LeadNoEncontradoError, OtroLeadAbiertoError
from src.routes.leads.repository import LeadsRepository
from src.routes.leads.sql import fijar_temperatura
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

T1, T2 = "593900004001", "593900004002"
AD = "test-leads-anuncio"


def _limpiar():
    borrar_conversaciones_de_prueba(T1, T2)


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _cliente(telefono=T1, **kw):
    return ConversacionRepository.crear(id_externo=telefono, **kw)


def _lead(conv, dias_atribucion=30):
    return LeadRepository.obtener_o_crear(conv["id"], conv["contacto_id"], conv["telefono"], dias_atribucion)


def _llegada(conv, ad=AD, wamid="wamid.leads-1"):
    referral = {"source_id": ad, "source_type": "ad", "ctwa_clid": f"clic-{ad}", "headline": "Anuncio de prueba"}
    return AnuncioRepository.registrar_llegada(conv["id"], None, wamid, normalizar_referral(referral), referral)


def _sql(consulta, *params):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(consulta, params)
        return cur.fetchall() if cur.description else None


def _historial(lead_id):
    return [(h["de"], h["a"], h["origen"]) for h in reversed(LeadsRepository.historial(lead_id))]


class TestUnLeadAbiertoPorContacto:
    def test_un_lead_nuevo_nace_tibio_con_su_primera_entrada_en_el_historial(self):
        lead = _lead(_cliente())
        assert (lead["temperatura"], lead["temperatura_origen"], lead["origen"], lead["id_anuncio"]) == ("tibio", "regla", "directo", None)
        assert _historial(lead["id"]) == [(None, "tibio", "regla")]

    def test_pedir_el_lead_otra_vez_trae_el_mismo_mientras_sigue_abierto(self):
        conv = _cliente()
        assert _lead(conv)["id"] == _lead(conv)["id"]

    def test_la_base_impide_un_segundo_lead_abierto_del_mismo_contacto(self):
        conv = _cliente()
        _lead(conv)
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("insert into leads (conversacion_id, contacto_id) values (%s, %s)", (conv["id"], conv["contacto_id"]))

    def test_cerrado_un_lead_el_cliente_que_vuelve_abre_otro_y_el_anterior_queda_en_su_historial(self):
        conv = _cliente()
        primero = _lead(conv)
        LeadsRepository.fijar_temperatura(primero["id"], "perdido", "dueno", motivo="No contestó", motivo_perdida="sin_respuesta")
        segundo = _lead(conv)
        assert segundo["id"] != primero["id"] and segundo["temperatura"] == "tibio"
        assert [x["id"] for x in LeadsRepository.ficha_de_contacto(conv["contacto_id"])["leads"]] == [segundo["id"], primero["id"]]

    def test_dos_mensajes_a_la_vez_no_abren_dos_leads(self):
        conv = _cliente()
        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(lambda _: _lead(conv)["id"], range(8)))
        assert len(set(ids)) == 1

    def test_el_lead_abierto_es_del_contacto_aunque_escriba_por_otro_canal(self):
        wa = _cliente()
        ig = ConversacionRepository.crear(id_externo="17841400000004001", canal="instagram", telefono=T1)
        try:
            lead = _lead(wa)
            assert LeadRepository.obtener_o_crear(ig["id"], ig["contacto_id"], None)["id"] == lead["id"]
        finally:
            borrar_conversaciones_de_prueba("17841400000004001", canal="instagram")

    def test_obtener_por_conversacion_prefiere_el_abierto_y_si_no_el_mas_reciente(self):
        conv = _cliente()
        primero = _lead(conv)
        assert LeadRepository.obtener_por_conversacion(conv["id"])["id"] == primero["id"]
        LeadsRepository.fijar_temperatura(primero["id"], "perdido", "dueno")
        assert LeadRepository.obtener_por_conversacion(conv["id"])["id"] == primero["id"]  # ninguno abierto: el más reciente
        segundo = _lead(conv)
        assert LeadRepository.obtener_por_conversacion(conv["id"])["id"] == segundo["id"]


class TestFijarTemperatura:
    def test_deja_historial_y_cierra_con_su_motivo(self):
        lead = _lead(_cliente())
        assert LeadsRepository.fijar_temperatura(lead["id"], "caliente", "ia", motivo="Pidió cómo pagar") is True
        assert LeadsRepository.fijar_temperatura(lead["id"], "perdido", "dueno", motivo="Compró en otro lado", motivo_perdida="compro_en_otro_lado", usuario="freddy@x.ec") is True
        actual = LeadsRepository.obtener(lead["id"])
        assert (actual["temperatura"], actual["motivo_perdida"], actual["temperatura_origen"]) == ("perdido", "compro_en_otro_lado", "dueno")
        assert actual["cerrado_en"] is not None
        assert _historial(lead["id"]) == [(None, "tibio", "regla"), ("tibio", "caliente", "ia"), ("caliente", "perdido", "dueno")]
        assert LeadsRepository.historial(lead["id"])[0]["usuario"] == "freddy@x.ec"

    def test_repetir_la_misma_temperatura_no_ensucia_el_historial(self):
        lead = _lead(_cliente())
        assert LeadsRepository.fijar_temperatura(lead["id"], "tibio", "ia") is False
        assert len(LeadsRepository.historial(lead["id"])) == 1

    def test_el_motivo_de_perdida_solo_vale_en_perdido_y_cerrado_en_se_borra_al_reabrir(self):
        lead = _lead(_cliente())
        LeadsRepository.fijar_temperatura(lead["id"], "caliente", "ia", motivo_perdida="precio")
        assert LeadsRepository.obtener(lead["id"])["motivo_perdida"] is None
        LeadsRepository.fijar_temperatura(lead["id"], "perdido", "dueno", motivo_perdida="precio")
        LeadsRepository.fijar_temperatura(lead["id"], "tibio", "dueno")
        reabierto = LeadsRepository.obtener(lead["id"])
        assert reabierto["motivo_perdida"] is None and reabierto["cerrado_en"] is None

    def test_la_temperatura_fijada_por_el_dueno_guarda_hasta_cuando(self):
        lead = _lead(_cliente())
        hasta = datetime.now(timezone.utc) + timedelta(days=7)
        LeadsRepository.fijar_temperatura(lead["id"], "caliente", "dueno", fijada_hasta=hasta)
        assert abs((LeadsRepository.obtener(lead["id"])["temperatura_fijada_hasta"] - hasta).total_seconds()) < 1

    def test_reabrir_un_lead_cuando_ya_hay_otro_abierto_se_rechaza(self):
        conv = _cliente()
        viejo = _lead(conv)
        LeadsRepository.fijar_temperatura(viejo["id"], "perdido", "dueno")
        nuevo = _lead(conv)
        with pytest.raises(OtroLeadAbiertoError):
            LeadsRepository.fijar_temperatura(viejo["id"], "tibio", "dueno")
        assert LeadsRepository.obtener(viejo["id"])["temperatura"] == "perdido" and LeadsRepository.obtener(nuevo["id"])["temperatura"] == "tibio"

    def test_un_lead_que_no_existe_se_avisa(self):
        with pytest.raises(LeadNoEncontradoError):
            LeadsRepository.fijar_temperatura(999999999, "frio", "ia")


class TestReglasSobreHechos:
    def test_despachar_el_pedido_pasa_el_lead_a_ganado_en_la_misma_transaccion(self):
        lead = _lead(_cliente())
        LeadRepository.actualizar_despacho(lead["id"], 123, 456)
        actual = LeadsRepository.obtener(lead["id"])
        assert (actual["etapa"], actual["temperatura"], actual["temperatura_origen"]) == ("despachado", "ganado", "regla")
        assert actual["cerrado_en"] is not None
        assert _historial(lead["id"])[-1] == ("tibio", "ganado", "regla")


class TestAtribucionPorLead:
    def test_un_lead_nuevo_hereda_el_anuncio_si_la_llegada_es_reciente(self):
        conv = _cliente()
        _llegada(conv)
        lead = _lead(conv)
        assert (lead["origen"], lead["id_anuncio"], lead["ctwa_clid"]) == ("anuncio", AD, f"clic-{AD}")

    def test_si_el_anuncio_es_viejo_el_lead_nuevo_es_directo(self):
        # José llegó por un anuncio en enero y en mayo escribe solo: la venta de mayo NO es del anuncio de enero.
        conv = _cliente()
        _llegada(conv)
        _sql("update conversacion_anuncios set creado_en = now() - interval '90 days' where conversacion_id = %s", conv["id"])
        lead = _lead(conv, dias_atribucion=30)
        assert (lead["origen"], lead["id_anuncio"]) == ("directo", None)

    def test_el_periodo_de_atribucion_es_configurable(self):
        conv = _cliente()
        _llegada(conv)
        _sql("update conversacion_anuncios set creado_en = now() - interval '40 days' where conversacion_id = %s", conv["id"])
        assert _lead(conv, dias_atribucion=60)["origen"] == "anuncio"

    def test_una_llegada_por_anuncio_con_un_lead_abierto_cambia_el_origen_de_ese_lead(self):
        conv = _cliente()
        lead = _lead(conv)
        assert lead["origen"] == "directo"
        _llegada(conv)
        actual = LeadsRepository.obtener(lead["id"])
        assert (actual["origen"], actual["id_anuncio"]) == ("anuncio", AD)

    def test_un_lead_cerrado_no_cambia_de_origen_con_llegadas_posteriores(self):
        conv = _cliente()
        lead = _lead(conv)
        LeadsRepository.fijar_temperatura(lead["id"], "perdido", "dueno")
        _llegada(conv)
        assert LeadsRepository.obtener(lead["id"])["origen"] == "directo"


class TestNoContactar:
    def test_se_marca_en_el_contacto_y_cierra_sus_leads_abiertos(self):
        wa = _cliente()
        ig = ConversacionRepository.crear(id_externo="17841400000004001", canal="instagram", telefono=T1)
        try:
            lead = _lead(wa)
            assert LeadsRepository.marcar_no_contactar(wa["contacto_id"], True, "Dijo que no le interesa", "ia", None) is True
            ficha = LeadsRepository.ficha_de_contacto(ig["contacto_id"])  # el MISMO contacto, visto desde otro canal
            assert (ficha["no_contactar"], ficha["no_contactar_por"], ficha["no_contactar_motivo"]) == (True, "ia", "Dijo que no le interesa")
            cerrado = LeadsRepository.obtener(lead["id"])
            assert (cerrado["temperatura"], cerrado["motivo_perdida"], cerrado["no_contactar"]) == ("perdido", "no_le_interesa", True)
            assert _historial(lead["id"])[-1] == ("tibio", "perdido", "ia")
        finally:
            borrar_conversaciones_de_prueba("17841400000004001", canal="instagram")

    def test_se_puede_quitar_y_el_contacto_queda_como_antes(self):
        conv = _cliente()
        LeadsRepository.marcar_no_contactar(conv["contacto_id"], True, "x", "dueno", "freddy@x.ec")
        LeadsRepository.marcar_no_contactar(conv["contacto_id"], False, None, "dueno", "freddy@x.ec")
        ficha = LeadsRepository.ficha_de_contacto(conv["contacto_id"])
        assert (ficha["no_contactar"], ficha["no_contactar_motivo"], ficha["no_contactar_en"]) == (False, None, None)

    def test_un_contacto_que_no_existe_devuelve_falso(self):
        assert LeadsRepository.marcar_no_contactar(999999999, True, None, "dueno", None) is False


class TestPantalla:
    def _tres_leads(self):
        a, b, c = _cliente(T1, nombre_perfil="Ana Perfil"), _cliente(T2, nombre_perfil="Beto Perfil"), None
        la, lb = _lead(a), _lead(b)
        LeadRepository.actualizar_producto(la["id"], "SKU-L1", "Audífonos", 50, cantidad=1)
        LeadRepository.actualizar_producto(lb["id"], "SKU-L2", "Zapatos", 30, cantidad=1)
        LeadsRepository.fijar_temperatura(la["id"], "caliente", "ia", motivo="Pidió cómo pagar")
        LeadsRepository.fijar_temperatura(lb["id"], "perdido", "dueno", motivo_perdida="precio")
        MensajeRepository.crear(a["id"], "cliente", "Hola, quiero los audífonos")
        MensajeRepository.crear(a["id"], "bot", "¡Claro!")
        return a, b, la, lb

    def test_la_lista_trae_cliente_producto_temperatura_y_ultimo_mensaje(self):
        a, _, la, _ = self._tres_leads()
        fila = next(f for f in LeadsRepository.listar(q="Ana")["items"] if f["id"] == la["id"])
        assert (fila["canal"], fila["nombre_perfil"], fila["producto_nombre"], fila["temperatura"], fila["etapa"]) == (
            "whatsapp", "Ana Perfil", "Audífonos", "caliente", "recopilando_datos")
        assert (fila["ultimo_rol"], fila["ultimo_contenido"]) == ("bot", "¡Claro!")
        assert fila["ultimo_cliente_en"] is not None and fila["no_contactar"] is False

    def test_filtra_por_temperatura_producto_canal_y_busqueda(self):
        self._tres_leads()
        assert [f["producto_nombre"] for f in LeadsRepository.listar(temperaturas=["caliente"], q="593900004")["items"]] == ["Audífonos"]
        assert [f["producto_nombre"] for f in LeadsRepository.listar(temperaturas=["perdido"], q="593900004")["items"]] == ["Zapatos"]
        assert [f["producto_nombre"] for f in LeadsRepository.listar(producto_sku="SKU-L2", q="593900004")["items"]] == ["Zapatos"]
        assert LeadsRepository.listar(canal="instagram", q="593900004")["total"] == 0
        assert LeadsRepository.listar(q="Beto Perfil")["total"] == 1

    def test_sin_respuesta_hace_n_dias_usa_el_ultimo_mensaje_del_cliente(self):
        _, _, la, _ = self._tres_leads()
        assert LeadsRepository.listar(sin_respuesta_dias=5, q="Ana")["total"] == 0
        _sql("update mensajes set creado_en = now() - interval '9 days' where conversacion_id = %s", la["conversacion_id"])
        assert LeadsRepository.listar(sin_respuesta_dias=5, q="Ana")["total"] == 1

    def test_los_ordenes_son_los_de_la_lista_blanca(self):
        self._tres_leads()
        por_valor = [f["producto_nombre"] for f in LeadsRepository.listar(q="593900004", orden="valor")["items"]]
        assert por_valor == ["Audífonos", "Zapatos"]
        por_temperatura = [f["temperatura"] for f in LeadsRepository.listar(q="593900004", orden="temperatura")["items"]]
        assert por_temperatura == ["caliente", "perdido"]
        # Un orden desconocido nunca llega al SQL: cae al de siempre.
        assert LeadsRepository.listar(q="593900004", orden="1; drop table leads")["total"] == 2

    def test_paginacion(self):
        self._tres_leads()
        p1 = LeadsRepository.listar(q="593900004", page=1, page_size=1)
        p2 = LeadsRepository.listar(q="593900004", page=2, page_size=1)
        assert (p1["total"], len(p1["items"]), len(p2["items"])) == (2, 1, 1) and p1["items"][0]["id"] != p2["items"][0]["id"]

    def test_el_resumen_cuenta_ahora_y_por_periodo(self):
        self._tres_leads()
        r = LeadsRepository.resumen(None)
        assert r["calientes"] >= 1 and r["perdidos"] >= 1 and r["nuevos"] >= 2
        assert {"motivo": "precio"}.items() <= next(m for m in r["motivos_de_perdida"] if m["motivo"] == "precio").items()
        futuro = LeadsRepository.resumen(datetime.now(timezone.utc) + timedelta(days=1))
        assert futuro["nuevos"] == 0 and futuro["perdidos"] == 0  # el periodo recorta ganados, perdidos y nuevos, no las cuentas de ahora

    def test_la_ficha_del_contacto_junta_leads_compras_y_llegadas(self):
        conv = _cliente(nombre_perfil="Ana Perfil")
        _llegada(conv)
        lead = _lead(conv)
        _sql(
            "insert into ventas (contacto_id, conversacion_id, lead_id, proveedor_id, estado, subtotal, total, costo_productos, telefono) "
            "values (%s, %s, %s, 1, 'despachada', 40, 40, 25, %s), (%s, %s, null, 1, 'cancelada', 99, 99, 10, %s)",
            conv["contacto_id"], conv["id"], lead["id"], T1, conv["contacto_id"], conv["id"], T1,
        )
        ficha = LeadsRepository.ficha_de_contacto(conv["contacto_id"])
        assert (ficha["nombre"], ficha["telefono"]) == ("Ana Perfil", T1)
        assert [c["canal"] for c in ficha["conversaciones"]] == ["whatsapp"]
        assert (int(ficha["compras"]["compras"]), float(ficha["compras"]["total_gastado"]), float(ficha["compras"]["ganancia"])) == (1, 40.0, 15.0)  # la cancelada no cuenta
        assert (ficha["anuncios"]["llegadas"], ficha["primer_anuncio"]["id_anuncio"]) == (1, AD)
        assert LeadsRepository.ficha_de_contacto(999999999) is None


class TestCandidatosAEnfriar:
    def _ids(self):
        return {c["id"] for c in LeadsRepository.candidatos_a_enfriar()}

    def test_trae_los_abiertos_con_su_ultimo_mensaje_del_cliente(self):
        conv = _cliente()
        lead = _lead(conv)
        MensajeRepository.crear(conv["id"], "cliente", "hola")
        _sql("update mensajes set creado_en = now() - interval '3 days' where conversacion_id = %s", conv["id"])
        candidato = next(c for c in LeadsRepository.candidatos_a_enfriar() if c["id"] == lead["id"])
        assert candidato["temperatura"] == "tibio" and (datetime.now(timezone.utc) - candidato["ultimo_cliente_en"]).days == 3

    def test_no_trae_los_cerrados_ni_los_fijados_por_el_dueno_ni_las_conversaciones_en_sus_manos(self):
        c1, c2, c3 = _cliente(T1), _cliente(T2), ConversacionRepository.crear(id_externo="593900004003")
        try:
            cerrado, fijado, escalado = _lead(c1), _lead(c2), _lead(c3)
            LeadsRepository.fijar_temperatura(cerrado["id"], "perdido", "dueno")
            LeadsRepository.fijar_temperatura(fijado["id"], "caliente", "dueno", fijada_hasta=datetime.now(timezone.utc) + timedelta(days=3))
            ConversacionRepository.marcar_escalada(c3["id"])
            assert not ({cerrado["id"], fijado["id"], escalado["id"]} & self._ids())
            _sql("update leads set temperatura_fijada_hasta = now() - interval '1 hour' where id = %s", fijado["id"])
            assert fijado["id"] in self._ids()  # la fijación venció: el silencio vuelve a contar
        finally:
            borrar_conversaciones_de_prueba("593900004003")


class TestListaDeConversacionesConVariosLeads:
    def test_una_conversacion_con_varios_leads_aparece_una_sola_vez_con_el_lead_vigente(self):
        conv = _cliente()
        primero = _lead(conv)
        LeadRepository.actualizar_producto(primero["id"], "SKU-V1", "Audífonos", 50, cantidad=1)
        LeadsRepository.fijar_temperatura(primero["id"], "perdido", "dueno")
        segundo = _lead(conv)
        LeadRepository.actualizar_producto(segundo["id"], "SKU-V2", "Zapatos", 30, cantidad=1)

        lista = ConversacionRepository.listar(q=T1)
        assert lista["total"] == 1 and len(lista["items"]) == 1
        assert lista["items"][0]["producto_nombre"] == "Zapatos"  # el lead abierto, no el que se perdió antes


class TestSeguimientosEnLaPantalla:
    """El seguimiento automático (migración 026) se ve en la lista (el último enviado) y en el detalle (todos, también los fallidos)."""

    def test_la_lista_trae_el_ultimo_seguimiento_enviado_y_el_detalle_todos(self):
        from src.jobs.seguimiento.repository import SeguimientoRepository

        conv = _cliente()
        lead = _lead(conv)
        MensajeRepository.crear(conv["id"], "bot", "Hola, ¿en qué te ayudo?")  # la última palabra es de Victoria
        sin_nada = next(f for f in LeadsRepository.listar(q=T1)["items"] if f["id"] == lead["id"])
        assert sin_nada["seguimiento_tipo"] is None

        fallido = SeguimientoRepository.reservar(lead["id"], "whatsapp", "plantilla", "Hola", "retomar_conversacion")
        SeguimientoRepository.marcar_fallido(fallido, "Plantilla no aprobada")
        enviado = SeguimientoRepository.reservar(lead["id"], "whatsapp", "empujon", "¿Sigue interesado(a)?")
        SeguimientoRepository.marcar_enviado(enviado, conv["id"], "¿Sigue interesado(a)?", "wamid.t1")

        fila = next(f for f in LeadsRepository.listar(q=T1)["items"] if f["id"] == lead["id"])
        assert fila["seguimiento_tipo"] == "empujon" and fila["seguimiento_en"] is not None  # el fallido no cuenta como «enviado»
        todos = LeadsRepository.seguimientos(lead["id"])
        assert [(s["tipo"], s["estado"]) for s in todos] == [("empujon", "enviado"), ("plantilla", "fallido")]  # el más reciente primero
        assert todos[1]["error"] == "Plantilla no aprobada" and todos[0]["enviado_en"] is not None

    def test_la_lista_sigue_con_una_fila_por_lead_aunque_tenga_varios_seguimientos(self):
        from src.jobs.seguimiento.repository import SeguimientoRepository

        conv = _cliente()
        lead = _lead(conv)
        MensajeRepository.crear(conv["id"], "bot", "Hola, ¿en qué te ayudo?")
        for tipo in ("empujon", "plantilla"):
            sid = SeguimientoRepository.reservar(lead["id"], "whatsapp", tipo, "x", "p" if tipo == "plantilla" else None)
            SeguimientoRepository.marcar_enviado(sid, conv["id"], "x", f"wamid.{tipo}")
        assert len([f for f in LeadsRepository.listar(q=T1)["items"] if f["id"] == lead["id"]]) == 1
