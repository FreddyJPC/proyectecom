"""
Servicio de «Probar con Victoria» con repositorios falsos (sin base ni red) y,
al final, una prueba contra la base local que comprueba que una compra
simulada completa NO deja filas de negocio (conversaciones, mensajes, leads,
pedidos, cola) y solo registra su uso y su entrada en el historial.
"""
from decimal import Decimal

import pytest

from src.config.database import get_connection
from src.integrations.llm import LLMAuthError, LLMRateLimitError, LLMRequestError
from src.routes.ajustes.dto import AjustesNegocio
from src.routes.productos_bot.exceptions import (
    IAFalloError,
    IANoDisponibleError,
    ProductoBotNoEncontradoError,
    PruebaInvalidaError,
    PublicacionBloqueadaError,
    TopeDePruebasAlcanzadoError,
    TransicionInvalidaError,
)
from src.routes.productos_bot.generaciones import TIPO_SIMULACION
from src.routes.productos_bot.pruebas import (
    ACCION_SIMULACION_COMPLETA,
    PruebasService,
    faltantes_para_probar,
)
from src.config.parametros import definicion
from src.routes.productos_bot import pruebas as pruebas_modulo
from tests.unit.routes.productos_bot.test_simulacion import (
    CERRAR,
    CONTRAENTREGA,
    DATOS,
    PRODUCTO,
    LLMGuionado,
    compra_completa,
    ficha,
    herramientas,
    texto,
)

SKU = "SIM-1"

# Mensajes que admite una prueba por defecto (parámetro `pruebas.max_mensajes`).
MAX_MENSAJES_POR_PRUEBA = definicion("pruebas.max_mensajes").defecto


class RepoFalso:
    def __init__(self, fila=None, falla_historial=False):
        self.fila = fila
        self.historial = []
        self.falla_historial = falla_historial

    def obtener(self, sku):
        return self.fila if self.fila and self.fila["sku"] == sku else None

    def registrar_historial(self, sku, accion, usuario, cambios=None):
        if self.falla_historial:
            raise RuntimeError("base caída")
        self.historial.append((sku, accion, usuario, cambios))


class GeneracionesFalsas:
    def __init__(self, usadas=0, falla_registro=False):
        self.usadas = usadas
        self.registros = []
        self.falla_registro = falla_registro

    def contar_hoy(self, tipo):
        assert tipo == TIPO_SIMULACION  # las pruebas tienen su propio tope
        return self.usadas

    def registrar(self, sku, usuario, modelo, resultado, campos, tipo="contenido"):
        if self.falla_registro:
            raise RuntimeError("base caída")
        self.registros.append({"sku": sku, "usuario": usuario, "modelo": modelo, "resultado": resultado, "campos": campos, "tipo": tipo})


class AjustesFalsos:
    def __init__(self, tope=100):
        self.tope = tope

    def obtener_ajustes(self):
        return AjustesNegocio(tope_pruebas_dia=self.tope)


class EntregasFalsas:
    """Las opciones de entrega guardadas del producto (por defecto, ninguna)."""

    def __init__(self, entregas=()):
        self.entregas = list(entregas)

    def listar(self, sku, solo_activas=False):
        return [e for e in self.entregas if not solo_activas or e.get("activo", True)]


def servicio(llm=None, fila="por-defecto", usadas=0, tope=100, entregas=(), **kw):
    repo = RepoFalso(ficha() if fila == "por-defecto" else fila, falla_historial=kw.pop("falla_historial", False))
    generaciones = GeneracionesFalsas(usadas, falla_registro=kw.pop("falla_registro", False))
    s = PruebasService(
        repo=repo, generaciones=generaciones, ajustes_service=AjustesFalsos(tope), llm=llm, modelo="modelo-x",
        entregas_repo=EntregasFalsas(entregas),
    )
    return s, repo, generaciones


def probar(s, mensaje="Hola", historial=(), estado=None, escalada=False, sku=SKU):
    return s.probar(sku, mensaje, list(historial), estado, False, escalada, "ana@ejemplo.com")


class TestUso:
    def test_cuenta_las_pruebas_de_hoy_contra_el_tope(self):
        s, _, _ = servicio(usadas=30, tope=100)
        uso = s.uso()
        assert (uso.tope, uso.usadas, uso.restantes) == (100, 30, 70)

    def test_nunca_devuelve_restantes_negativos(self):
        s, _, _ = servicio(usadas=150, tope=100)
        assert s.uso().restantes == 0


class RepoDeInstrucciones:
    """Doble del repositorio de las instrucciones de Victoria: solo importa el borrador."""

    def __init__(self, borrador=None):
        self._borrador = borrador

    def borrador(self):
        return self._borrador


def _servicio_con_borrador(llm, borrador):
    from src.routes.whatsapp.instrucciones import secciones_originales

    fila = None if borrador is None else {"secciones": {**secciones_originales(), **borrador}}
    return PruebasService(
        repo=RepoFalso(ficha()), generaciones=GeneracionesFalsas(), ajustes_service=AjustesFalsos(100), llm=llm,
        modelo="modelo-x", instrucciones_repo=RepoDeInstrucciones(fila),
    )


class TestProbarElBorradorDeLasInstrucciones:
    """Se prueba lo que se está por publicar, sin que los clientes reales lo vean todavía."""

    def test_con_usar_borrador_victoria_recibe_las_instrucciones_del_borrador(self):
        llm = LLMGuionado(texto("ok"))
        s = _servicio_con_borrador(llm, {"personalidad": "Hablas como un pirata."})
        s.probar(SKU, "Hola", [], None, False, False, "ana@ejemplo.com", usar_borrador=True)

        system = llm.llamadas[0]["system"]
        assert "Hablas como un pirata." in system and "Hablas como una persona real" not in system
        assert "Audifonos" in system or "{" not in system  # los huecos se rellenaron

    def test_sin_usar_borrador_se_prueba_con_las_que_rigen_hoy(self):
        llm = LLMGuionado(texto("ok"))
        s = _servicio_con_borrador(llm, {"personalidad": "Hablas como un pirata."})
        s.probar(SKU, "Hola", [], None, False, False, "ana@ejemplo.com")
        assert "Hablas como un pirata." not in llm.llamadas[0]["system"]

    def test_pedir_el_borrador_sin_tenerlo_se_avisa_y_no_gasta_nada(self):
        llm = LLMGuionado(texto("no debe llegar"))
        s = _servicio_con_borrador(llm, None)
        with pytest.raises(PruebaInvalidaError, match="No hay un borrador de instrucciones"):
            s.probar(SKU, "Hola", [], None, False, False, "ana@ejemplo.com", usar_borrador=True)
        assert llm.llamadas == []

    def test_un_borrador_invalido_en_la_base_se_rechaza_con_un_mensaje(self):
        llm = LLMGuionado(texto("no debe llegar"))
        s = PruebasService(
            repo=RepoFalso(ficha()), generaciones=GeneracionesFalsas(), ajustes_service=AjustesFalsos(100), llm=llm,
            modelo="modelo-x", instrucciones_repo=RepoDeInstrucciones({"secciones": {"intro": "solo una"}}),
        )
        with pytest.raises(PruebaInvalidaError, match="El borrador de instrucciones no es válido"):
            s.probar(SKU, "Hola", [], None, False, False, "ana@ejemplo.com", usar_borrador=True)
        assert llm.llamadas == []


class TestUnTurno:
    def test_devuelve_el_turno_registra_el_uso_y_actualiza_el_contador(self):
        s, repo, gen = servicio(LLMGuionado(texto("Hola, soy Victoria")), usadas=4)
        turno = probar(s)

        assert turno.respuesta == "Hola, soy Victoria"
        assert (turno.uso.tope, turno.uso.usadas, turno.uso.restantes) == (100, 5, 95)
        assert gen.registros == [{
            "sku": SKU, "usuario": "ana@ejemplo.com", "modelo": "modelo-x", "resultado": "ok",
            "campos": ["mensaje"], "tipo": TIPO_SIMULACION,
        }]
        assert repo.historial == []  # una charla simple no cuenta como compra completa

    def test_el_estado_sale_en_camel_case(self):
        s, _, _ = servicio(LLMGuionado(herramientas(DATOS), texto("Anotado")))
        estado = probar(s).estado
        assert estado["nombreCliente"] == "Ana Prueba" and "nombre_cliente" not in estado
        assert estado["metodoPago"] is None and estado["productoSku"] is None

    def test_el_estado_de_entrada_se_usa_tal_cual_viene_del_esquema(self):
        llm = LLMGuionado(texto("ok"))
        s, _, _ = servicio(llm)
        probar(s, estado={"nombre_cliente": "Luis", "cantidad": 1})
        assert "Nombre: Luis" in llm.llamadas[0]["system"]

    def test_una_compra_completa_se_anota_en_el_historial_del_producto(self):
        s, repo, _ = servicio(compra_completa())
        turno = probar(s)
        assert turno.pedido.confirmado is True and turno.pedido.payload["total"] == "24.99"
        assert repo.historial == [(SKU, ACCION_SIMULACION_COMPLETA, "ana@ejemplo.com", None)]

    def test_una_compra_que_escala_no_cuenta_como_completa(self):
        s, repo, _ = servicio(LLMGuionado(herramientas(DATOS, PRODUCTO, CONTRAENTREGA, CERRAR), texto("ok")), fila=ficha(precio=Decimal("5.00")))
        turno = probar(s)
        assert turno.pedido is None and turno.escalada is True
        assert repo.historial == [] and turno.avisos

    def test_si_falla_el_historial_la_respuesta_no_se_pierde(self):
        s, _, _ = servicio(compra_completa(), falla_historial=True)
        assert probar(s).pedido is not None

    def test_si_falla_el_registro_del_uso_la_respuesta_no_se_pierde(self):
        s, _, _ = servicio(LLMGuionado(texto("ok")), falla_registro=True)
        assert probar(s).respuesta == "ok"


class TestTopes:
    def test_el_tope_diario_se_respeta_antes_de_llamar_a_la_ia(self):
        llm = LLMGuionado(texto("no debe llegar"))
        s, _, gen = servicio(llm, usadas=100, tope=100)
        with pytest.raises(TopeDePruebasAlcanzadoError) as exc:
            probar(s)
        assert (exc.value.usadas, exc.value.tope) == (100, 100)
        assert llm.llamadas == [] and gen.registros == []

    def test_un_mensaje_menos_que_el_tope_todavia_pasa(self):
        s, _, _ = servicio(LLMGuionado(texto("ok")), usadas=99, tope=100)
        turno = probar(s)
        assert turno.uso.restantes == 0

    def test_la_prueba_tiene_un_maximo_de_mensajes_del_cliente(self):
        historial = [{"rol": "cliente", "contenido": "hola"}] * MAX_MENSAJES_POR_PRUEBA
        llm = LLMGuionado(texto("no debe llegar"))
        s, _, _ = servicio(llm)
        with pytest.raises(PruebaInvalidaError, match="20 mensajes"):
            probar(s, historial=historial)
        assert llm.llamadas == []

    def test_el_uso_informa_cuantos_mensajes_admite_cada_prueba(self):
        s, _, _ = servicio(LLMGuionado(texto("ok")))
        assert s.uso().max_mensajes == MAX_MENSAJES_POR_PRUEBA

    def test_el_maximo_de_mensajes_es_el_parametro_y_se_nota_al_cambiarlo(self, monkeypatch):
        historial = [{"rol": "cliente", "contenido": "hola"}] * 6
        s, _, _ = servicio(LLMGuionado(texto("ok")))
        assert probar(s, historial=historial).respuesta == "ok"  # con 20 todavía cabe

        monkeypatch.setattr(pruebas_modulo.parametros, "valor", lambda clave: 5 if clave == "pruebas.max_mensajes" else None)
        s, _, _ = servicio(LLMGuionado(texto("no debe llegar")))
        with pytest.raises(PruebaInvalidaError, match="5 mensajes"):
            probar(s, historial=historial)

    def test_los_mensajes_del_bot_no_cuentan_para_el_maximo(self):
        historial = [{"rol": "bot", "contenido": "hola"}] * 50 + [{"rol": "cliente", "contenido": "hola"}] * (MAX_MENSAJES_POR_PRUEBA - 1)
        s, _, _ = servicio(LLMGuionado(texto("ok")))
        assert probar(s, historial=historial).respuesta == "ok"


class TestLaPruebaTerminoDeVerdad:
    def test_despues_de_escalar_ya_no_responde(self):
        s, _, _ = servicio(LLMGuionado(texto("no")))
        with pytest.raises(PruebaInvalidaError, match="pasó esta conversación a una persona"):
            probar(s, escalada=True)

    def test_despues_de_cerrar_la_compra_ya_no_responde(self):
        s, _, _ = servicio(LLMGuionado(texto("no")))
        with pytest.raises(PruebaInvalidaError, match="ya se cerró"):
            probar(s, estado={"estado": "despachado"})


class TestProductoNoProbable:
    def test_sku_inexistente(self):
        s, _, _ = servicio(fila=None)
        with pytest.raises(ProductoBotNoEncontradoError):
            probar(s)

    def test_archivado(self):
        s, _, _ = servicio(fila=ficha(estado="archivado"))
        with pytest.raises(TransicionInvalidaError):
            probar(s)

    @pytest.mark.parametrize(
        "cambio, fragmento",
        [
            ({"nombre": " "}, "nombre"),
            ({"descripcion": ""}, "descripción"),
            ({"tiempo_entrega": None}, "tiempo de entrega"),
            ({"metodos_pago_aceptados": ""}, "método de pago"),
            ({"precio": Decimal("0")}, "precio"),
            ({"precio": None}, "precio"),
        ],
    )
    def test_le_falta_lo_minimo_para_conversar(self, cambio, fragmento):
        llm = LLMGuionado(texto("no debe llegar"))
        s, _, gen = servicio(llm, fila=ficha(**cambio))
        with pytest.raises(PublicacionBloqueadaError) as exc:
            probar(s)
        assert any(fragmento in b.lower() for b in exc.value.bloqueos)
        assert llm.llamadas == [] and gen.registros == []

    def test_un_precio_bajo_el_piso_igual_se_puede_probar(self):
        # La prueba sirve justamente para ver qué pasa: la lista de publicar es la que bloquea.
        assert faltantes_para_probar(ficha(precio=Decimal("0.50"), costo_rocketfy=Decimal("9.00"))) == []


class TestFallosDeLaIA:
    @pytest.mark.parametrize(
        "error, esperado",
        [(LLMAuthError("clave"), IANoDisponibleError), (LLMRateLimitError("limite"), IANoDisponibleError), (LLMRequestError("red"), IAFalloError)],
    )
    def test_un_fallo_del_proveedor_se_traduce_y_no_cuenta_para_el_tope(self, error, esperado):
        class LLMQueFalla(LLMGuionado):
            def generar_respuesta(self, *args, **kwargs):
                raise error

        s, _, gen = servicio(LLMQueFalla())
        with pytest.raises(esperado):
            probar(s)
        assert [r["resultado"] for r in gen.registros] == ["fallo"]

    def test_un_error_inesperado_sube_pero_tampoco_cuenta(self):
        class LLMRoto(LLMGuionado):
            def generar_respuesta(self, *args, **kwargs):
                raise ZeroDivisionError("bug")

        s, _, gen = servicio(LLMRoto())
        with pytest.raises(ZeroDivisionError):
            probar(s)
        assert [r["resultado"] for r in gen.registros] == ["fallo"]

    def test_sin_clave_de_ia_el_mensaje_es_claro(self, monkeypatch):
        def sin_clave():
            raise ValueError("ANTHROPIC_API_KEY es requerida")

        monkeypatch.setattr("src.integrations.llm.get_llm_client", sin_clave)
        s, _, gen = servicio(llm=None)
        with pytest.raises(IANoDisponibleError, match="falta la clave"):
            probar(s)
        assert gen.registros == []


# ----------------------------------------------------------------------
# Contra la base local: cero filas de negocio
# ----------------------------------------------------------------------
TABLAS_DE_NEGOCIO = ("conversaciones", "mensajes", "leads", "pedidos", "cola_mensajes", "rocketfy_minimos_observados")
SKU_REAL = "TEST-FASE-E-SIM"


def _contar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cantidades = {}
            for tabla in TABLAS_DE_NEGOCIO:
                cur.execute(f"select count(*) from {tabla}")
                cantidades[tabla] = cur.fetchone()[0]
            return cantidades


def _limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from generaciones_ia where sku = %s", (SKU_REAL,))
            cur.execute("delete from productos_bot_historial where sku = %s", (SKU_REAL,))
            cur.execute("delete from productos_bot where sku = %s", (SKU_REAL,))


@pytest.fixture
def producto_real():
    _limpiar()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into productos_bot (sku, nombre, descripcion, precio, tiempo_entrega, metodos_pago_aceptados,
                                           max_unidades_por_pedido, estado, activo, stock_ultimo)
                values (%s, 'Audifonos de prueba', 'Audifonos con 20 horas de bateria.', 24.99, '2 a 4 dias',
                        'contraentrega', 2, 'borrador', false, 50)
                """,
                (SKU_REAL,),
            )
    yield SKU_REAL
    _limpiar()


class TestContraLaBaseLocal:
    def test_una_compra_simulada_completa_no_deja_filas_de_negocio(self, producto_real):
        antes = _contar()
        producto_antes = _estado_del_producto(producto_real)
        s = PruebasService(llm=LLMGuionado(
            herramientas(
                DATOS,
                ("registrar_producto", {"producto_sku": producto_real, "producto_nombre": "Audifonos de prueba"}),
                CONTRAENTREGA,
                CERRAR,
            ),
            texto("Listo"),
        ), modelo="modelo-x")

        turno = s.probar(producto_real, "Quiero comprar", [], None, False, False, "ana@ejemplo.com")

        assert turno.pedido is not None and turno.pedido.confirmado is True
        assert _contar() == antes  # ninguna conversación, mensaje, lead, pedido ni cola nuevos
        assert _estado_del_producto(producto_real) == producto_antes  # sigue en borrador, inactivo
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select tipo, resultado, campos from generaciones_ia where sku = %s", (producto_real,))
                assert cur.fetchall() == [(TIPO_SIMULACION, "ok", "mensaje")]
                cur.execute("select accion from productos_bot_historial where sku = %s", (producto_real,))
                assert cur.fetchall() == [(ACCION_SIMULACION_COMPLETA,)]
        assert s.uso().usadas >= 1

    def test_el_conteo_de_hoy_separa_pruebas_de_borradores(self, producto_real):
        s = PruebasService(llm=LLMGuionado(texto("ok"), texto("ok")), modelo="m")
        s.probar(producto_real, "Hola", [], None, False, False, None)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into generaciones_ia (sku, tipo, resultado) values (%s, 'contenido', 'ok')", (producto_real,)
                )
        from src.routes.productos_bot.generaciones import GeneracionesIARepository as G

        con_sim = G.contar_hoy(TIPO_SIMULACION)
        con_contenido = G.contar_hoy("contenido")
        assert con_sim >= 1 and con_contenido >= 1
        s.probar(producto_real, "Otra", [], None, False, False, None)
        assert G.contar_hoy(TIPO_SIMULACION) == con_sim + 1
        assert G.contar_hoy("contenido") == con_contenido


def _estado_del_producto(sku):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("select estado, activo, nombre, precio, stock_ultimo from productos_bot where sku = %s", (sku,))
            return cur.fetchone()
