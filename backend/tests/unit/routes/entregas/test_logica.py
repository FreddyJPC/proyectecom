"""Reglas puras de las opciones de entrega (ADR-012). Sin base de datos."""
from decimal import Decimal

from src.routes.entregas.logica import (
    describir,
    elegir_opcion,
    limpiar_y_validar,
    normalizar,
    opciones_aplicables,
    texto_para_la_ficha,
    total_con_envio,
)


def _opcion(id, nombre, tipo="envio", costo="2.00", cantones=(), provincias=(), resto=False, direccion=None, activo=True, tiempo=None):
    return {
        "id": id, "nombre": nombre, "tipo": tipo, "costo_cliente": Decimal(costo), "costo_negocio": None,
        "cantones": list(cantones), "provincias": list(provincias), "resto_del_pais": resto,
        "direccion_retiro": direccion, "tiempo_entrega": tiempo, "activo": activo,
    }


EN_CUENCA = _opcion(1, "Envío en Cuenca", costo="2.00", cantones=["Cuenca"], tiempo="Mismo día")
RETIRO = _opcion(2, "Retiro en tienda", tipo="retiro", costo="0.00", direccion="Calle Larga 1-23")
RESTO = _opcion(3, "Envío al resto del país", costo="5.00", resto=True, tiempo="2 a 3 días")
OPCIONES = [EN_CUENCA, RETIRO, RESTO]


class TestNormalizar:
    def test_quita_tildes_mayusculas_y_prefijos(self):
        assert normalizar("  Cantón CUENCA ") == "cuenca"
        assert normalizar("Ciudad de Quito") == "quito"
        assert normalizar("Azogues") == "azogues"

    def test_vacio_o_none(self):
        assert normalizar(None) == "" and normalizar("   ") == ""


class TestOpcionesAplicables:
    def test_un_cliente_de_cuenca_ve_el_envio_local_y_el_retiro_pero_no_el_resto_del_pais(self):
        nombres = [o["nombre"] for o in opciones_aplicables(OPCIONES, "Cuenca", "Azuay")]
        assert nombres == ["Envío en Cuenca", "Retiro en tienda"]

    def test_un_cliente_de_otra_ciudad_ve_el_resto_del_pais_y_el_retiro(self):
        nombres = [o["nombre"] for o in opciones_aplicables(OPCIONES, "Quito", "Pichincha")]
        assert nombres == ["Retiro en tienda", "Envío al resto del país"]

    def test_compara_sin_tildes_ni_mayusculas(self):
        assert opciones_aplicables([EN_CUENCA], "CUENCA", None) == [EN_CUENCA]
        assert opciones_aplicables([_opcion(9, "Loja", cantones=["Loja"])], "loja", None)

    def test_cobertura_por_provincia(self):
        sierra_sur = _opcion(4, "Sierra sur", provincias=["Azuay", "Cañar"])
        assert opciones_aplicables([sierra_sur], "Azogues", "Cañar") == [sierra_sur]
        assert opciones_aplicables([sierra_sur], "Quito", "Pichincha") == []

    def test_una_opcion_inactiva_no_se_ofrece(self):
        assert opciones_aplicables([_opcion(5, "Pausada", cantones=["Cuenca"], activo=False)], "Cuenca", "Azuay") == []

    def test_sin_ninguna_opcion_que_cubra_el_destino_no_hay_nada(self):
        assert opciones_aplicables([EN_CUENCA], "Quito", "Pichincha") == []

    def test_el_orden_es_el_que_el_dueno_puso(self):
        assert [o["id"] for o in opciones_aplicables([RETIRO, EN_CUENCA], "Cuenca", "Azuay")] == [2, 1]


class TestElegirOpcion:
    def test_por_numero_de_la_lista(self):
        lista = opciones_aplicables(OPCIONES, "Cuenca", "Azuay")
        assert elegir_opcion(lista, "2")["nombre"] == "Retiro en tienda"
        assert elegir_opcion(lista, "9") is None

    def test_por_nombre_exacto_o_parcial_unico(self):
        lista = opciones_aplicables(OPCIONES, "Cuenca", "Azuay")
        assert elegir_opcion(lista, "envío en cuenca")["id"] == 1
        assert elegir_opcion(lista, "retiro")["id"] == 2

    def test_ambiguo_o_inexistente_devuelve_none(self):
        dos = [_opcion(1, "Envío rápido", cantones=["Cuenca"]), _opcion(2, "Envío normal", cantones=["Cuenca"])]
        assert elegir_opcion(dos, "envío") is None
        assert elegir_opcion(dos, "paloma mensajera") is None
        assert elegir_opcion(dos, "") is None


class TestTotal:
    def test_suma_el_envio_con_dos_decimales(self):
        assert total_con_envio("24.99", EN_CUENCA) == Decimal("26.99")
        assert total_con_envio(Decimal("30"), RETIRO) == Decimal("30.00")

    def test_sin_opcion_es_el_subtotal(self):
        assert total_con_envio("24.99", None) == Decimal("24.99")


class TestTextos:
    def test_describir_una_opcion(self):
        assert describir(EN_CUENCA, con_numero=1) == "1) Envío en Cuenca: $2.00 · Mismo día"
        assert "se retira en Calle Larga 1-23" in describir(RETIRO)
        assert "sin costo" in describir(RETIRO)

    def test_ficha_con_envio_incluido(self):
        texto = texto_para_la_ficha(True, [])
        assert "INCLUIDO en el precio" in texto and "registrar_entrega" not in texto

    def test_con_envio_incluido_las_opciones_guardadas_no_se_listan(self):
        assert texto_para_la_ficha(True, OPCIONES) == texto_para_la_ficha(True, [])

    def test_ficha_con_envio_aparte_lista_las_opciones_y_pide_registrar_entrega(self):
        texto = texto_para_la_ficha(False, OPCIONES)
        assert "se cobra aparte" in texto and "Envío en Cuenca" in texto and "registrar_entrega" in texto
        assert "clientes de Cuenca" in texto and "el resto del país" in texto

    def test_ficha_con_envio_aparte_y_sin_opciones_manda_a_escalar(self):
        assert "escalar_a_humano" in texto_para_la_ficha(False, [])


class TestValidar:
    def test_opciones_validas_se_limpian(self):
        limpias, errores = limpiar_y_validar(
            [
                {"nombre": " Envío en Cuenca ", "tipo": "envio", "costo_cliente": "2", "cantones": ["Cuenca", " "]},
                {"nombre": "Retiro", "tipo": "retiro", "direccion_retiro": "Calle Larga", "cantones": ["x"]},
                {"nombre": "Resto", "costo_cliente": 5.5, "resto_del_pais": True},
            ]
        )
        assert errores == []
        assert limpias[0]["nombre"] == "Envío en Cuenca" and limpias[0]["cantones"] == ["Cuenca"]
        assert limpias[0]["costo_cliente"] == Decimal("2.00")
        assert limpias[1]["cantones"] == [] and limpias[1]["resto_del_pais"] is False  # un retiro no tiene cobertura
        assert limpias[2]["costo_cliente"] == Decimal("5.50")

    def test_errores_en_espanol_por_posicion(self):
        _, errores = limpiar_y_validar(
            [
                {"nombre": "", "tipo": "envio", "resto_del_pais": True},
                {"nombre": "Sin cobertura", "tipo": "envio"},
                {"nombre": "Retiro sin dirección", "tipo": "retiro"},
                {"nombre": "Mixta", "tipo": "envio", "resto_del_pais": True, "cantones": ["Cuenca"]},
                {"nombre": "Costo raro", "tipo": "envio", "resto_del_pais": True, "costo_cliente": "-1"},
                {"nombre": "Tipo raro", "tipo": "paloma", "resto_del_pais": True},
            ]
        )
        texto = " | ".join(errores)
        assert "Opción 1: falta el nombre" in texto
        assert "Opción 2: indica a qué cantones" in texto
        assert "Opción 3: un retiro necesita la dirección" in texto
        assert "Opción 4: elige UNA" in texto
        assert "Opción 5" in texto and "negativo" in texto
        assert "Opción 6: el tipo" in texto

    def test_demasiadas_opciones(self):
        _, errores = limpiar_y_validar([{"nombre": f"o{i}", "resto_del_pais": True} for i in range(13)])
        assert errores and "Máximo" in errores[0]
