"""
Contactos y conversaciones por canal contra la base real de pruebas (ADR-014, migración 024): un contacto único por
teléfono, una conversación por canal, «crear o traer» sin duplicados y pedido previo por contacto.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest

from src.config.database import get_connection
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900003001"
INSTAGRAM = "17841400000003001"


def _limpiar():
    borrar_conversaciones_de_prueba(TELEFONO, INSTAGRAM)  # por WhatsApp (una prueba usa el mismo identificador en ambos canales)
    borrar_conversaciones_de_prueba(INSTAGRAM, canal="instagram")
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("delete from contactos where telefono = %s", (TELEFONO,))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


class TestCrearConversacion:
    def test_whatsapp_crea_el_contacto_con_su_telefono(self):
        c = ConversacionRepository.crear(id_externo=TELEFONO, nombre_perfil="Ana P.")
        assert (c["canal"], c["id_externo"], c["telefono"], c["contacto_nombre"], c["nombre_perfil"]) == (
            "whatsapp", TELEFONO, TELEFONO, "Ana P.", "Ana P.",
        )

    def test_es_crear_o_traer_dos_mensajes_a_la_vez_no_duplican_ni_pierden_al_cliente(self):
        def crear(_):
            return ConversacionRepository.crear(id_externo=TELEFONO)["id"]

        with ThreadPoolExecutor(max_workers=4) as pool:
            ids = list(pool.map(crear, range(8)))
        assert len(set(ids)) == 1  # todos reciben LA conversación; ninguno falla por duplicado
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("select count(*) from contactos where telefono = %s", (TELEFONO,))
            assert cur.fetchone()[0] == 1

    def test_un_cliente_de_instagram_es_un_contacto_sin_telefono(self):
        c = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram", nombre_perfil="ana_ec")
        assert (c["canal"], c["id_externo"], c["telefono"]) == ("instagram", INSTAGRAM, None)
        assert ConversacionRepository.obtener_por_canal("instagram", INSTAGRAM)["id"] == c["id"]
        assert ConversacionRepository.obtener_por_canal("whatsapp", INSTAGRAM) is None  # el canal importa

    def test_el_mismo_identificador_en_otro_canal_es_otra_conversacion(self):
        a = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="whatsapp")
        b = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram")
        assert a["id"] != b["id"] and a["contacto_id"] != b["contacto_id"]

    def test_un_mismo_telefono_en_otro_canal_cuelga_del_mismo_contacto(self):
        wa = ConversacionRepository.crear(id_externo=TELEFONO)
        ig = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram", telefono=TELEFONO)
        assert wa["contacto_id"] == ig["contacto_id"] and wa["id"] != ig["id"]


class TestPedidoPrevioPorContacto:
    def test_un_pedido_cerrado_por_un_canal_cuenta_para_el_contacto_en_cualquier_canal(self):
        wa = ConversacionRepository.crear(id_externo=TELEFONO)
        ig = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram", telefono=TELEFONO)
        lead = LeadRepository.obtener_o_crear(wa["id"], wa["contacto_id"], TELEFONO)
        assert LeadRepository.existe_pedido_previo(ig["contacto_id"]) is False
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("update leads set estado = 'despachado' where id = %s", (lead["id"],))
        assert LeadRepository.existe_pedido_previo(ig["contacto_id"]) is True  # lo ve desde Instagram

    def test_un_lead_puede_no_tener_telefono_si_el_canal_no_lo_da(self):
        ig = ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram")
        lead = LeadRepository.obtener_o_crear(ig["id"], ig["contacto_id"], None)
        assert lead["telefono"] is None and lead["contacto_id"] == ig["contacto_id"]


class TestListarPorCanal:
    def test_filtra_por_canal_y_busca_por_nombre_de_perfil_o_identificador(self):
        ConversacionRepository.crear(id_externo=TELEFONO, nombre_perfil="Ana Wasap")
        ConversacionRepository.crear(id_externo=INSTAGRAM, canal="instagram", nombre_perfil="ana_insta")

        solo_ig = ConversacionRepository.listar(canal="instagram", q="ana_insta")["items"]
        assert [f["id_externo"] for f in solo_ig] == [INSTAGRAM] and solo_ig[0]["canal"] == "instagram"
        por_perfil = ConversacionRepository.listar(q="Ana Wasap")["items"]
        assert [f["id_externo"] for f in por_perfil] == [TELEFONO]
        por_identificador = ConversacionRepository.listar(q=INSTAGRAM)["items"]
        assert [f["id_externo"] for f in por_identificador] == [INSTAGRAM]
