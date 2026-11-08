"""
Contra la base real (la de pruebas local): el SQL de las tablas de la migración 018.
Borra lo que crea para no dejar la base distinta de como estaba.
"""
import pytest

from src.config.database import get_connection
from src.config.parametros.repository import ParametrosRepository as Repo

CLAVE = "test.parametro.repo"


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from parametros_sistema where clave = %s", (CLAVE,))
            cur.execute("delete from parametros_historial where clave = %s", (CLAVE,))


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _historial_de_la_clave():
    return [c for c in Repo.historial(500) if c["clave"] == CLAVE]


class TestGuardar:
    def test_guarda_y_lo_lista(self):
        assert Repo.guardar(CLAVE, "60", "ana@x.com") is True
        fila = Repo.listar()[CLAVE]
        assert (fila["valor"], fila["actualizado_por"]) == ("60", "ana@x.com")
        assert fila["actualizado_en"] is not None

    def test_cambiar_el_valor_actualiza_la_fila_y_anota_el_valor_anterior(self):
        Repo.guardar(CLAVE, "60", "ana@x.com")
        assert Repo.guardar(CLAVE, "70", "bea@x.com") is True
        assert Repo.listar()[CLAVE]["valor"] == "70"
        cambios = _historial_de_la_clave()
        assert [(c["valor_anterior"], c["valor_nuevo"], c["usuario"]) for c in cambios] == [("60", "70", "bea@x.com"), (None, "60", "ana@x.com")]

    def test_guardar_el_mismo_valor_no_escribe_ni_anota(self):
        Repo.guardar(CLAVE, "60", "ana@x.com")
        assert Repo.guardar(CLAVE, "60", "bea@x.com") is False
        assert len(_historial_de_la_clave()) == 1
        assert Repo.listar()[CLAVE]["actualizado_por"] == "ana@x.com"


class TestRestaurar:
    def test_borra_el_valor_y_lo_anota_como_restauracion(self):
        Repo.guardar(CLAVE, "60", "ana@x.com")
        assert Repo.restaurar(CLAVE, "bea@x.com") is True
        assert CLAVE not in Repo.listar()
        ultimo = _historial_de_la_clave()[0]
        assert (ultimo["valor_anterior"], ultimo["valor_nuevo"], ultimo["usuario"]) == ("60", None, "bea@x.com")

    def test_si_no_habia_nada_no_hace_nada(self):
        assert Repo.restaurar(CLAVE, "bea@x.com") is False
        assert _historial_de_la_clave() == []


class TestHistorial:
    def test_viene_del_mas_nuevo_al_mas_viejo_y_respeta_el_limite(self):
        for valor in ("1", "2", "3"):
            Repo.guardar(CLAVE, valor, "ana@x.com")
        nuevos = [c["valor_nuevo"] for c in _historial_de_la_clave()]
        assert nuevos == ["3", "2", "1"]
        assert len(Repo.historial(2)) == 2
