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
        "canton, provincia, esperado",
        [
            ("quto", "Pichincha", ("Quito", "Pichincha")),
            ("kito", "Pichincha", ("Quito", "Pichincha")),
            ("guayakil", "Guayas", ("Guayaquil", "Guayas")),
            ("cuenka", "Azuay", ("Cuenca", "Azuay")),
            ("latakunga", "Cotopaxi", ("Latacunga", "Cotopaxi")),
            ("anbato", "Tungurahua", ("Ambato", "Tungurahua")),
            ("quito sur", "Pichincha", ("Quito", "Pichincha")),
            ("sangolqi", "pichinca", ("Sangolqui", "Pichincha")),  # también la provincia, escrita mal
        ],
    )
    def test_un_error_evidente_se_corrige_sin_preguntar(self, canton, provincia, esperado):
        r = revisar_ubicacion(CATALOGO, canton, provincia)
        assert not r.hay_problema and (r.canton, r.provincia) == esperado
        assert "no hace falta preguntarle" in r.nota

    def test_con_adornos_como_canton_quito_no_hay_nada_que_corregir(self):
        r = revisar_ubicacion(CATALOGO, "Cantón Quito", "Pichincha")
        assert not r.hay_problema and (r.canton, r.provincia) == ("Quito", "Pichincha")

    def test_dos_lugares_que_contienen_lo_escrito_se_preguntan(self):
        r = revisar_ubicacion(CATALOGO, "coca", "Orellana")  # «El Coca» o «San Sebastián del Coca»
        assert r.hay_problema and r.canton is None

    def test_quito_coma_pichincha_en_el_campo_del_canton(self):
        r = revisar_ubicacion(CATALOGO, "Quito, Pichincha", None)
        assert not r.hay_problema and (r.canton, r.provincia) == ("Quito", "Pichincha")

    def test_una_abreviatura_se_entiende(self):
        r = revisar_ubicacion(CATALOGO, "sto domingo", "Santo Domingo de los Tsachilas")
        assert not r.hay_problema and r.canton == "Santo Domingo"

    @pytest.mark.parametrize("provincia", ["pichinca", "Pichincha", "provincia de pichincha"])
    def test_la_provincia_mal_escrita_tambien_se_corrige(self, provincia):
        r = revisar_ubicacion(CATALOGO, "Quito", provincia)
        assert not r.hay_problema and r.provincia == "Pichincha"

    @pytest.mark.parametrize("provincia, esperada", [("sto domingo", "Santo Domingo de los Tsáchilas"), ("zamora", "Zamora Chinchipe"), ("oro", "El Oro")])
    def test_una_provincia_contenida_en_otra_palabra(self, provincia, esperada):
        assert revisar_ubicacion(CATALOGO, None, provincia).provincia == esperada

    def test_cantón_de_otra_provincia_no_cuadra_y_se_aclara_con_el_cliente(self):
        for canton in ("Quito", "Guayaquil"):
            r = revisar_ubicacion(CATALOGO, canton, "Pichincha" if canton == "Guayaquil" else "Guayas")
            assert r.hay_problema and r.canton is None and "No cuadra" in r.mensaje

    def test_el_mensaje_de_no_cuadra_dice_donde_esta(self):
        r = revisar_ubicacion(CATALOGO, "Guayaquil", "Pichincha")
        assert "Guayaquil está en Guayas, no en Pichincha" in r.mensaje and r.provincia == "Pichincha"

    def test_con_un_error_de_ortografia_y_la_provincia_equivocada_tampoco_se_adivina(self):
        r = revisar_ubicacion(CATALOGO, "guayakil", "Pichincha")
        assert r.hay_problema and "Guayaquil está en Guayas" in r.mensaje

    def test_si_hay_dos_opciones_razonables_se_pregunta_cual(self):
        r = revisar_ubicacion(CATALOGO, "san", "Pichincha")  # demasiado corto: podría ser muchas
        assert r.hay_problema or r.canton is None

    def test_el_mensaje_de_problema_manda_a_escalar_si_no_se_aclara(self):
        r = revisar_ubicacion(CATALOGO, "xyzxyz", "Pichincha")
        assert r.hay_problema and "escalar_a_humano" in r.mensaje

    def test_solo_provincia_se_guarda(self):
        r = revisar_ubicacion(CATALOGO, None, "Azuay")
        assert not r.hay_problema and r.provincia == "Azuay" and r.canton is None

    def test_solo_canton_conocido_completa_la_provincia_sin_preguntar(self):
        for dicho, esperado in (("Quito", ("Quito", "Pichincha")), ("guayaquil", ("Guayaquil", "Guayas")), ("guayakil", ("Guayaquil", "Guayas"))):
            r = revisar_ubicacion(CATALOGO, dicho, None)
            assert not r.hay_problema and (r.canton, r.provincia) == esperado

    def test_algo_que_no_se_parece_a_nada_pide_aclarar_y_no_inventa(self):
        for canton, provincia in (("xyzxyz", "Pichincha"), ("xyzxyz", None)):
            r = revisar_ubicacion(CATALOGO, canton, provincia)
            assert r.hay_problema and r.canton is None and "otra vez" in r.mensaje

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

    def test_un_error_evidente_se_corrige_y_se_le_dice_a_victoria_que_no_pregunte(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), nombre_cliente="Ana", canton="quto", provincia="pichincha")
        assert (leads.leads[1]["canton"], leads.leads[1]["provincia"]) == ("Quito", "Pichincha")
        assert "no hace falta preguntarle" in respuesta and "«quto» -> «Quito»" in respuesta

    def test_solo_la_ciudad_mal_escrita_completa_la_provincia(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), canton="guayakil")
        assert (leads.leads[1]["canton"], leads.leads[1]["provincia"]) == ("Guayaquil", "Guayas")
        assert "Se guardó Guayaquil, Guayas" in respuesta

    def test_si_no_cuadra_no_se_guarda_el_canton_pero_el_resto_si(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), nombre_cliente="Ana", canton="Guayaquil", provincia="Pichincha")
        assert leads.leads[1]["nombre_cliente"] == "Ana" and leads.leads[1]["provincia"] == "Pichincha"
        assert "canton" not in leads.leads[1]
        assert "No cuadra" in respuesta and "ubicación" in respuesta

    def test_solo_una_ciudad_inexistente_dice_que_no_se_guardo(self):
        leads = FakeLeadRepository(leads={1: {}})
        respuesta = _guardar(_herramientas(lead_repo=leads), canton="xyzxyz")
        assert respuesta.startswith("No se guardó la ubicación") and "escalar_a_humano" in respuesta
        assert "canton" not in leads.leads[1]

    def test_un_valor_bueno_ya_guardado_no_se_pisa_con_uno_dudoso(self):
        leads = FakeLeadRepository(leads={1: {"canton": "Quito", "provincia": "Pichincha"}})
        _guardar(_herramientas(lead_repo=leads), canton="xyzxyz")
        assert leads.leads[1]["canton"] == "Quito"

    def test_con_la_provincia_ya_guardada_basta_decir_la_ciudad(self):
        leads = FakeLeadRepository(leads={1: {"provincia": "Azuay"}})
        _guardar(_herramientas(lead_repo=leads), canton="cuenka")
        assert leads.leads[1]["canton"] == "Cuenca"

    def test_en_un_producto_propio_lo_dudoso_se_guarda_tal_cual_lo_escribio_el_cliente(self):
        propio = {"sku": "PROPIO-1", "nombre": "Mi producto", "activo": True, "proveedor_cierre": "manual", "proveedor_clave": "propio"}
        leads = FakeLeadRepository(leads={1: {"producto_sku": "PROPIO-1"}})
        productos = FakeProductoBotRepository({"PROPIO-1": propio})
        _guardar(_herramientas(lead_repo=leads, producto_repo=productos), canton="Pueblo Desconocido", provincia="Pichincha")
        assert leads.leads[1]["canton"] == "Pueblo Desconocido"  # el dueño gestiona el envío; no se bloquea

    def test_en_un_producto_propio_lo_evidente_tambien_se_corrige(self):
        propio = {"sku": "PROPIO-1", "nombre": "Mi producto", "activo": True, "proveedor_cierre": "manual", "proveedor_clave": "propio"}
        leads = FakeLeadRepository(leads={1: {"producto_sku": "PROPIO-1"}})
        productos = FakeProductoBotRepository({"PROPIO-1": propio})
        _guardar(_herramientas(lead_repo=leads, producto_repo=productos), canton="kito", provincia="Pichincha")
        assert leads.leads[1]["canton"] == "Quito"


class TestVariantes:
    PRODUCTO = {"sku": "AUD-1", "nombre": "Audífonos", "precio": "24.99", "activo": True, "variantes": "Negro, blanco",
                "max_unidades_por_pedido": 3, "tiempo_entrega": "2 días", "metodos_pago_aceptados": "contraentrega"}

    def _registrar(self, variante):
        leads = FakeLeadRepository(leads={1: {}})
        h = _herramientas(lead_repo=leads, producto_repo=FakeProductoBotRepository({"AUD-1": self.PRODUCTO}))
        r = h.ejecutar("registrar_producto", lead_id=1, conversacion_id=1,
                       entrada={"producto_sku": "AUD-1", "producto_nombre": "Audífonos", "variante": variante}, id_llamada="t").contenido
        return leads.leads[1].get("producto_variante"), r

    def test_un_error_evidente_se_corrige_sin_preguntar(self):
        guardada, respuesta = self._registrar("negrp")
        assert guardada == "Negro" and "no hace falta preguntarle" in respuesta

    def test_si_ya_viene_bien_no_dice_nada(self):
        guardada, respuesta = self._registrar("blanco")
        assert guardada == "blanco" or guardada == "Blanco"
        assert "no hace falta" not in respuesta

    def test_una_variante_que_no_existe_no_se_inventa_y_no_frena_la_venta(self):
        guardada, respuesta = self._registrar("rojo")
        assert guardada is None and "Producto registrado" in respuesta and "las disponibles son Negro, blanco" in respuesta
