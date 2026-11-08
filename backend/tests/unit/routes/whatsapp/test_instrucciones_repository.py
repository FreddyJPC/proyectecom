"""
Contra la base real (la de pruebas local): el SQL y los índices únicos de la migración 019
(a lo sumo un borrador y una publicada). Deja la tabla vacía al terminar.
"""
import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.whatsapp.instrucciones import secciones_originales
from src.routes.whatsapp.instrucciones_repository import InstruccionesRepository as Repo


def _vaciar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from victoria_instrucciones_versiones")


@pytest.fixture(autouse=True)
def limpio():
    _vaciar()
    yield
    _vaciar()


def _texto(valor):
    return {**secciones_originales(), "objetivo": valor}


class TestBorrador:
    def test_no_hay_nada_al_principio(self):
        assert Repo.publicada() is None and Repo.borrador() is None and Repo.versiones() == []

    def test_crea_el_borrador_y_lo_devuelve_con_sus_secciones(self):
        fila = Repo.guardar_borrador(_texto("Vender A"), "primera idea", "ana@x.com")
        assert (fila["estado"], fila["nota"], fila["creado_por"]) == ("borrador", "primera idea", "ana@x.com")
        assert fila["secciones"]["objetivo"] == "Vender A"  # jsonb vuelve como dict
        assert Repo.borrador()["id"] == fila["id"]

    def test_guardar_otra_vez_reemplaza_el_mismo_borrador(self):
        primero = Repo.guardar_borrador(_texto("A"), None, "ana@x.com")
        segundo = Repo.guardar_borrador(_texto("B"), "ajustado", "bea@x.com")
        assert segundo["id"] == primero["id"]
        assert (Repo.borrador()["secciones"]["objetivo"], Repo.borrador()["creado_por"]) == ("B", "bea@x.com")
        assert len(Repo.versiones()) == 1

    def test_descartar(self):
        Repo.guardar_borrador(_texto("A"), None, None)
        assert Repo.descartar_borrador() is True and Repo.borrador() is None
        assert Repo.descartar_borrador() is False

    def test_la_base_impide_dos_borradores(self):
        Repo.guardar_borrador(_texto("A"), None, None)
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("insert into victoria_instrucciones_versiones (secciones, estado) values ('{}', 'borrador')")


class TestPublicar:
    def test_sin_borrador_no_publica_nada(self):
        assert Repo.publicar_borrador(None) is None

    def test_el_borrador_pasa_a_publicada(self):
        Repo.guardar_borrador(_texto("A"), "mi nota", "ana@x.com")
        fila = Repo.publicar_borrador(None)
        assert fila["estado"] == "publicada" and fila["publicada_en"] is not None and fila["nota"] == "mi nota"
        assert Repo.borrador() is None and Repo.publicada()["id"] == fila["id"]

    def test_la_nota_al_publicar_reemplaza_la_del_borrador(self):
        Repo.guardar_borrador(_texto("A"), "del borrador", None)
        assert Repo.publicar_borrador("al publicar")["nota"] == "al publicar"

    def test_publicar_otra_archiva_la_anterior_y_nunca_hay_dos_publicadas(self):
        Repo.guardar_borrador(_texto("A"), None, None)
        primera = Repo.publicar_borrador(None)
        Repo.guardar_borrador(_texto("B"), None, None)
        segunda = Repo.publicar_borrador(None)

        assert Repo.publicada()["id"] == segunda["id"]
        estados = {v["id"]: v["estado"] for v in Repo.versiones()}
        assert estados == {primera["id"]: "archivada", segunda["id"]: "publicada"}

    def test_la_base_impide_dos_publicadas(self):
        Repo.guardar_borrador(_texto("A"), None, None)
        Repo.publicar_borrador(None)
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("insert into victoria_instrucciones_versiones (secciones, estado) values ('{}', 'publicada')")


class TestVolverALaOriginal:
    def test_la_publicada_queda_archivada_y_ya_no_rige_ninguna(self):
        Repo.guardar_borrador(_texto("A"), None, None)
        publicada = Repo.publicar_borrador(None)
        assert Repo.volver_a_la_original() is True
        assert Repo.publicada() is None
        assert Repo.obtener(publicada["id"])["estado"] == "archivada"

    def test_si_no_habia_publicada_no_hace_nada(self):
        assert Repo.volver_a_la_original() is False


def test_versiones_vienen_de_la_mas_nueva_a_la_mas_vieja_y_obtener_por_id():
    ids = []
    for valor in ("A", "B", "C"):
        Repo.guardar_borrador(_texto(valor), None, None)
        ids.append(Repo.publicar_borrador(None)["id"])
    assert [v["id"] for v in Repo.versiones()] == ids[::-1]
    assert len(Repo.versiones(2)) == 2
    assert Repo.obtener(ids[0])["secciones"]["objetivo"] == "A" and Repo.obtener(999999) is None
