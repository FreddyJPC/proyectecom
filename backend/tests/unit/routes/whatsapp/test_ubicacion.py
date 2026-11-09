"""
Ciudades mal escritas: «kito», «guayakil», «cuenka»… (lógica pura de `ubicacion.py` y su uso al guardar los datos).

El catálogo es el real de Rocketfy (832 cantones, `data/rocket-cantones-ecuador.csv`).
"""
import pytest

from src.catalogs.ecuador_locations import get_catalog
from src.routes.whatsapp.tools import HerramientasVictoria
from src.routes.whatsapp.ubicacion import revisar_ubicacion
from tests.unit.routes.whatsapp.test_tools import FakeLeadRepository, FakeProductoBotRepository, _herramientas

CATALOGO = get_catalog()


class TestRevisarUbicacion:
    @pytest.mark.parametrize(
        "canton, provincia, esperado",
        [
            ("Quito", "Pichincha", ("Quito", "Pichincha")),
            ("QUITO", "pichincha", ("Quito", "Pichincha")),
            ("  quito  ", "PICHINCHA", ("Quito", "Pichincha")),
            ("Ruminahui", "Pichincha", ("Rumiñahui", "Pichincha")),  # sin la eñe ni la tilde
            ("Portoviejo", "Manabi", ("Portoviejo", "Manabí")),
            ("Guayaquil", "guayas", ("Guayaquil", "Guayas")),
        ],
    )
    def test_si_coincide_se_guarda_con_el_nombre_oficial(self, canton, provincia, esperado):
        r = revisar_ubicacion(CATALOGO, canton, provincia)
        assert not r.hay_problema and (r.canton, r.provincia) == esperado

    @pytest.mark.parametrize(
        "canton, provincia, sugerido",
        [
            ("kito", "Pichincha", "Quito"),
            ("guayakil", "Guayas", "Guayaquil"),
            ("cuenka", "Azuay", "Cuenca"),
            ("latakunga", "Cotopaxi", "Latacunga"),
            ("anbato", "Tungurahua", "Ambato"),
            ("coca", "Orellana", "El Coca"),
        ],
    )
    def test_un_error_de_ortografia_no_se_guarda_y_se_sugiere(self, canton, provincia, sugerido):
        r = revisar_ubicacion(CATALOGO, canton, provincia)
        assert r.hay_problema and r.canton is None  # nunca se corrige solo
        assert sugerido in r.mensaje and "Pregúntaselo al cliente" in r.mensaje

    def test_la_provincia_mal_escrita_se_sugiere(self):
        r = revisar_ubicacion(CATALOGO, "Quito", "pichinca")
        assert r.hay_problema and r.provincia is None and "Pichincha" in r.mensaje

    def test_cantón_de_otra_provincia(self):
        r = revisar_ubicacion(CATALOGO, "Quito", "Guayas")
        assert r.hay_problema and r.provincia == "Guayas" and r.canton is None
        assert "Pichincha" in r.mensaje

    def test_solo_provincia_se_guarda(self):
        r = revisar_ubicacion(CATALOGO, None, "Azuay")
        assert not r.hay_problema and r.provincia == "Azuay" and r.canton is None

    def test_solo_canton_conocido_completa_la_provincia(self):
        r = revisar_ubicacion(CATALOGO, "Quito", None)
        assert not r.hay_problema and (r.canton, r.provincia) == ("Quito", "Pichincha") and "Pichincha" in r.nota

    def test_solo_canton_mal_escrito_se_sugiere(self):
        r = revisar_ubicacion(CATALOGO, "kito", None)
        assert r.hay_problema and "Quito" in r.mensaje

    def test_algo_que_no_se_parece_a_nada_pide_aclarar(self):
        r = revisar_ubicacion(CATALOGO, "xyzxyz", "Pichincha")
        assert r.hay_problema and r.sugerencias == [] and "otra vez" in r.mensaje

    def test_sin_nada_no_hay_problema(self):
        assert not revisar_ubicacion(CATALOGO, None, None).hay_problema
        assert not revisar_ubicacion(CATALOGO, "  ", "").hay_problema


def _guardar(herramientas, **entrada):
    return herramientas.ejecutar("guardar_datos_cliente", lead_id=1, conversacion_id=1, entrada=entrada, id_llamada="t").contenido


class TestGuardarConUbicacion:
    def test_el_nombre_oficial_es_el_que_queda_guardado(self):
        leads = FakeLeadRepository(leads={1: {}})
        _guardar(_herramientas(lead_repo=leads), canton="QUITO", provincia="pichincha")
        assert (leads.leads[1]["canton"], leads.leads[1]["provincia"]) == ("Quito", "Pichincha")

    def test_una_ciudad_mal_escrita_no_se_guarda_pero_el_resto_si(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), nombre_cliente="Ana", canton="guayakil", provincia="Guayas")
        assert leads.leads[1]["nombre_cliente"] == "Ana" and leads.leads[1]["provincia"] == "Guayas"
        assert "canton" not in leads.leads[1]
        assert "Guayaquil" in respuesta and "ubicación" in respuesta

    def test_solo_la_ciudad_mal_escrita_dice_que_no_se_guardo(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), canton="kito")
        assert respuesta.startswith("No se guardó la ubicación") and "Quito" in respuesta
        assert "canton" not in leads.leads[1]

    def test_un_valor_bueno_ya_guardado_no_se_pisa_con_uno_dudoso(self):
        leads = FakeLeadRepository(leads={1: {"canton": "Quito", "provincia": "Pichincha"}})
        _guardar(_herramientas(lead_repo=leads), canton="kito")
        assert leads.leads[1]["canton"] == "Quito"

    def test_con_la_provincia_ya_guardada_basta_decir_la_ciudad(self):
        leads = FakeLeadRepository(leads={1: {"provincia": "Azuay"}})
        _guardar(_herramientas(lead_repo=leads), canton="cuenca")
        assert leads.leads[1]["canton"] == "Cuenca"

    def test_solo_el_canton_completa_la_provincia(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), canton="Quito")
        assert (leads.leads[1]["canton"], leads.leads[1]["provincia"]) == ("Quito", "Pichincha")
        assert "Pichincha" in respuesta

    def test_en_un_producto_propio_se_guarda_tal_cual_lo_escribio_el_cliente(self):
        propio = {"sku": "PROPIO-1", "nombre": "Mi producto", "activo": True, "proveedor_cierre": "manual", "proveedor_clave": "propio"}
        leads = FakeLeadRepository(leads={1: {"producto_sku": "PROPIO-1"}})
        productos = FakeProductoBotRepository({"PROPIO-1": propio})
        respuesta = _guardar(_herramientas(lead_repo=leads, producto_repo=productos), canton="kito", provincia="Pichincha")
        assert leads.leads[1]["canton"] == "kito"  # el dueño gestiona el envío; no se bloquea
        assert "Quito" in respuesta
