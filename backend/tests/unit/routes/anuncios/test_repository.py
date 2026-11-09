"""
Contra la base real (la de pruebas local): el historial de llegadas por anuncio, el vínculo anuncio→producto y los
reportes de rendimiento. Autocontenido: teléfonos, anuncios y productos de prueba propios, con limpieza antes y después.
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import psycopg2.errors
import pytest

from src.config.database import get_connection
from src.routes.anuncios.referral import normalizar_referral
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.productos_bot.repository import ProductoBotGestionRepository as ProductosRepo
from src.routes.whatsapp.repository import ConversacionRepository, MensajeRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

T1, T2, T3 = "593900007001", "593900007002", "593900007003"
ANUNCIO_A, ANUNCIO_B, ANUNCIO_C = "test-anuncio-A", "test-anuncio-B", "test-anuncio-C"
IDS = (ANUNCIO_A, ANUNCIO_B, ANUNCIO_C)


def _limpiar():
    borrar_conversaciones_de_prueba(T1, T2, T3)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from anuncios_productos where id_anuncio like 'test-anuncio-%'")
            cur.execute("delete from productos_bot where nombre like 'TEST-ANUNCIOS %'")


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _referral(id_anuncio=ANUNCIO_A, **extra):
    return {
        "source_id": id_anuncio, "source_type": "ad", "headline": f"Titular {id_anuncio}", "body": "Texto del anuncio",
        "source_url": "https://fb.me/x", "media_type": "image", "image_url": "https://cdn.fb/i.jpg", "ctwa_clid": f"clic-{id_anuncio}",
        **extra,
    }


def _llegada(conversacion_id, referral, wamid):
    mensaje = MensajeRepository.crear(conversacion_id, "cliente", "hola", "texto", wamid)
    return AnuncioRepository.registrar_llegada(conversacion_id, mensaje["id"], wamid, normalizar_referral(referral), referral)


def _producto(nombre="TEST-ANUNCIOS Zapatos"):
    fila = ProductosRepo.crear_propio(
        {
            "nombre": nombre, "descripcion": "Zapatos", "precio": Decimal("30.00"), "tiempo_entrega": "2 días",
            "metodos_pago_aceptados": "contraentrega", "max_unidades_por_pedido": 5, "costo_propio": Decimal("18.00"),
            "controla_stock": True, "stock_ultimo": 5, "envio_incluido": True, "costo_flete_estimado": None, "categoria_id": None,
        },
        [],
    )
    return fila["sku"]


def _venta(telefono, id_anuncio, origen="anuncio", estado="despachada", total="60.00", costo="36.00", cerrada_en=None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "insert into contactos (telefono) values (%s) on conflict (telefono) where telefono is not null "
                "do update set actualizado_en = now() returning id",
                (telefono,),
            )
            contacto_id = cur.fetchone()[0]
            cur.execute(
                """
                insert into ventas (contacto_id, proveedor_id, origen, id_anuncio, estado, subtotal, total, costo_productos, telefono, cerrada_en)
                values (%s, 2, %s, %s, %s, %s, %s, %s, %s, coalesce(%s, now()))
                """,
                (contacto_id, origen, id_anuncio, estado, total, total, costo, telefono, cerrada_en),
            )


def _anuncio(lista, id_anuncio):
    return next(a for a in lista if a["id_anuncio"] == id_anuncio)


class TestRegistrarLlegada:
    def test_guarda_todos_los_datos_y_el_objeto_completo_de_meta(self):
        conversacion = ConversacionRepository.crear(id_externo=T1)
        referral = _referral(welcome_message={"text": "¡Hola!"}, thumbnail_url="https://cdn.fb/m.jpg")

        resultado = _llegada(conversacion["id"], referral, "wamid.A1")

        assert resultado == {"registrada": True, "anuncio_nuevo": True}
        fila = AnuncioRepository.llegadas_de(conversacion["id"])[0]
        assert (fila["id_anuncio"], fila["titulo"], fila["texto"], fila["url_anuncio"]) == (ANUNCIO_A, f"Titular {ANUNCIO_A}", "Texto del anuncio", "https://fb.me/x")
        assert (fila["tipo_origen"], fila["tipo_media"], fila["imagen_url"], fila["miniatura_url"]) == ("ad", "image", "https://cdn.fb/i.jpg", "https://cdn.fb/m.jpg")
        assert (fila["ctwa_clid"], fila["mensaje_bienvenida"], fila["wamid"]) == (f"clic-{ANUNCIO_A}", "¡Hola!", "wamid.A1")
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute("select referral from conversacion_anuncios where conversacion_id = %s", (conversacion["id"],))
            assert cur.fetchone()[0] == referral  # el objeto tal cual llegó

    def test_un_cliente_directo_que_vuelve_por_un_anuncio_pasa_a_origen_anuncio_con_el_anuncio_vigente(self):
        conversacion = ConversacionRepository.crear(id_externo=T1)  # directo
        assert conversacion["origen"] == "directo"

        _llegada(conversacion["id"], _referral(ANUNCIO_A), "wamid.A1")

        c = ConversacionRepository.obtener_por_id(conversacion["id"])
        assert (c["origen"], c["id_anuncio"], c["ctwa_clid"]) == ("anuncio", ANUNCIO_A, f"clic-{ANUNCIO_A}")

    def test_una_segunda_llegada_por_otro_anuncio_actualiza_el_vigente_y_conserva_el_historial(self):
        conversacion = ConversacionRepository.crear(id_externo=T1)
        _llegada(conversacion["id"], _referral(ANUNCIO_A), "wamid.A1")
        _llegada(conversacion["id"], _referral(ANUNCIO_B), "wamid.B1")

        c = ConversacionRepository.obtener_por_id(conversacion["id"])
        assert (c["id_anuncio"], c["ctwa_clid"]) == (ANUNCIO_B, f"clic-{ANUNCIO_B}")
        historial = AnuncioRepository.llegadas_de(conversacion["id"])
        assert [h["id_anuncio"] for h in historial] == [ANUNCIO_B, ANUNCIO_A]  # la más reciente primero

    def test_si_meta_no_manda_el_anuncio_se_conserva_el_anterior(self):
        conversacion = ConversacionRepository.crear(id_externo=T1)
        _llegada(conversacion["id"], _referral(ANUNCIO_A), "wamid.A1")
        _llegada(conversacion["id"], {"source_type": "ad", "headline": "Sin id"}, "wamid.A2")

        c = ConversacionRepository.obtener_por_id(conversacion["id"])
        assert (c["id_anuncio"], c["ctwa_clid"]) == (ANUNCIO_A, f"clic-{ANUNCIO_A}")

    def test_el_mismo_mensaje_reenviado_por_meta_no_se_registra_dos_veces(self):
        conversacion = ConversacionRepository.crear(id_externo=T1)
        mensaje = MensajeRepository.crear(conversacion["id"], "cliente", "hola", "texto", "wamid.DUP")
        datos = normalizar_referral(_referral())

        primero = AnuncioRepository.registrar_llegada(conversacion["id"], mensaje["id"], "wamid.DUP", datos, _referral())
        segundo = AnuncioRepository.registrar_llegada(conversacion["id"], mensaje["id"], "wamid.DUP", datos, _referral())

        assert primero["registrada"] is True and segundo == {"registrada": False, "anuncio_nuevo": False}
        assert len(AnuncioRepository.llegadas_de(conversacion["id"])) == 1

    def test_anuncio_nuevo_solo_la_primera_vez_y_solo_si_no_esta_vinculado(self):
        c1 = ConversacionRepository.crear(id_externo=T1)
        c2 = ConversacionRepository.crear(id_externo=T2)
        sku = _producto()
        AnuncioRepository.vincular(ANUNCIO_B, sku, None)

        assert _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")["anuncio_nuevo"] is True
        assert _llegada(c2["id"], _referral(ANUNCIO_A), "wamid.2")["anuncio_nuevo"] is False  # ya se había visto
        assert _llegada(c2["id"], _referral(ANUNCIO_B), "wamid.3")["anuncio_nuevo"] is False  # ya estaba vinculado

    def test_la_base_se_niega_a_borrar_una_conversacion_con_llegadas_por_anuncio(self):
        # Migración 024: el historial de anuncios de un contacto no se pierde por borrar su conversación.
        conversacion = ConversacionRepository.crear(id_externo=T1)
        _llegada(conversacion["id"], _referral(), "wamid.X")
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            with get_connection() as conn, conn.cursor() as cur:
                cur.execute("delete from conversaciones where id = %s", (conversacion["id"],))
        assert len(AnuncioRepository.llegadas_de(conversacion["id"])) == 1


class TestVinculoAnuncioProducto:
    def test_vincular_leer_cambiar_y_quitar(self):
        sku1, sku2 = _producto("TEST-ANUNCIOS Uno"), _producto("TEST-ANUNCIOS Dos")

        assert AnuncioRepository.vinculo_de(ANUNCIO_A) is None
        AnuncioRepository.vincular(ANUNCIO_A, sku1, "Video principal")
        vinculo = AnuncioRepository.vinculo_de(ANUNCIO_A)
        assert (vinculo["producto_sku"], vinculo["nombre"], vinculo["producto_nombre"]) == (sku1, "Video principal", "TEST-ANUNCIOS Uno")

        AnuncioRepository.vincular(ANUNCIO_A, sku2, None)  # cambia de producto y conserva el nombre
        vinculo = AnuncioRepository.vinculo_de(ANUNCIO_A)
        assert (vinculo["producto_sku"], vinculo["nombre"]) == (sku2, "Video principal")

        assert AnuncioRepository.desvincular(ANUNCIO_A) is True
        assert AnuncioRepository.desvincular(ANUNCIO_A) is False
        assert AnuncioRepository.vinculo_de(ANUNCIO_A) is None


class TestRendimientoPorAnuncio:
    def test_lista_conversaciones_ventas_ingresos_y_ganancia_sin_contar_las_canceladas(self):
        c1 = ConversacionRepository.crear(id_externo=T1)
        c2 = ConversacionRepository.crear(id_externo=T2)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _llegada(c2["id"], _referral(ANUNCIO_A), "wamid.2")
        _venta(T1, ANUNCIO_A, total="60.00", costo="36.00")
        _venta(T2, ANUNCIO_A, estado="cancelada", total="500.00", costo="1.00")  # no cuenta

        a = _anuncio(AnuncioRepository.listar_anuncios(None), ANUNCIO_A)

        assert (a["llegadas"], a["conversaciones"], a["ventas"]) == (2, 2, 1)
        assert (a["ingresos"], a["ganancia"], a["ventas_sin_costo"]) == (Decimal("60.00"), Decimal("24.00"), 0)
        assert a["titulo"] == f"Titular {ANUNCIO_A}" and a["producto_sku"] is None

    def test_la_ganancia_solo_suma_ventas_con_costo_conocido_y_avisa_cuantas_faltan(self):
        c1 = ConversacionRepository.crear(id_externo=T1)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _venta(T1, ANUNCIO_A, total="60.00", costo="36.00")
        _venta(T1, ANUNCIO_A, total="40.00", costo=None)

        a = _anuncio(AnuncioRepository.listar_anuncios(None), ANUNCIO_A)

        assert (a["ventas"], a["ingresos"], a["ganancia"], a["ventas_sin_costo"]) == (2, Decimal("100.00"), Decimal("24.00"), 1)

    def test_un_anuncio_vinculado_de_antemano_aparece_aunque_nadie_haya_llegado(self):
        AnuncioRepository.vincular(ANUNCIO_C, _producto(), "Anuncio de prueba")

        c = _anuncio(AnuncioRepository.listar_anuncios(None), ANUNCIO_C)

        assert (c["llegadas"], c["conversaciones"], c["ventas"]) == (0, 0, 0)
        assert c["nombre_vinculo"] == "Anuncio de prueba" and c["producto_nombre"] == "TEST-ANUNCIOS Zapatos"
        assert c["titulo"] is None and c["ultima_llegada"] is None

    def test_el_periodo_limita_las_cifras_pero_no_oculta_el_anuncio(self):
        c1 = ConversacionRepository.crear(id_externo=T1)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _venta(T1, ANUNCIO_A, cerrada_en=datetime.now(timezone.utc) - timedelta(days=40))
        desde = datetime.now(timezone.utc) - timedelta(days=30)

        reciente = _anuncio(AnuncioRepository.listar_anuncios(desde), ANUNCIO_A)
        todo = _anuncio(AnuncioRepository.listar_anuncios(None), ANUNCIO_A)

        assert reciente["ventas"] == 0 and reciente["llegadas"] == 1
        assert todo["ventas"] == 1

    def test_los_sin_vincular_salen_primero(self):
        c1 = ConversacionRepository.crear(id_externo=T1)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _llegada(c1["id"], _referral(ANUNCIO_B), "wamid.2")
        AnuncioRepository.vincular(ANUNCIO_B, _producto(), None)

        ids = [a["id_anuncio"] for a in AnuncioRepository.listar_anuncios(None) if a["id_anuncio"] in IDS]

        assert ids == [ANUNCIO_A, ANUNCIO_B]


class TestResumenPorOrigen:
    def test_separa_anuncio_de_directo_con_sus_ventas(self):
        base = AnuncioRepository.resumen_por_origen(None)
        c1 = ConversacionRepository.crear(id_externo=T1)  # por anuncio
        c2 = ConversacionRepository.crear(id_externo=T2)  # directo
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _venta(T1, ANUNCIO_A, origen="anuncio", total="60.00", costo="36.00")
        _venta(T2, None, origen="directo", total="30.00", costo="18.00")
        _venta(T2, None, origen="directo", estado="cancelada", total="999.00")

        despues = AnuncioRepository.resumen_por_origen(None)

        assert despues["base"]["conv_anuncio"] - base["base"]["conv_anuncio"] == 1
        assert despues["base"]["conv_directo"] - base["base"]["conv_directo"] == 1
        assert despues["base"]["llegadas"] - base["base"]["llegadas"] == 1
        assert despues["ventas_anuncio"]["ventas"] - base["ventas_anuncio"]["ventas"] == 1
        assert despues["ventas_anuncio"]["ingresos"] - base["ventas_anuncio"]["ingresos"] == Decimal("60.00")
        assert despues["ventas_directo"]["ventas"] - base["ventas_directo"]["ventas"] == 1
        assert despues["ventas_directo"]["ingresos"] - base["ventas_directo"]["ingresos"] == Decimal("30.00")

    def test_cuenta_los_anuncios_sin_vincular(self):
        base = AnuncioRepository.resumen_por_origen(None)["base"]["sin_vincular"]
        c1 = ConversacionRepository.crear(id_externo=T1)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")
        _llegada(c1["id"], _referral(ANUNCIO_B), "wamid.2")
        AnuncioRepository.vincular(ANUNCIO_B, _producto(), None)

        assert AnuncioRepository.resumen_por_origen(None)["base"]["sin_vincular"] - base == 1

    def test_un_cliente_que_llego_por_anuncio_no_cuenta_como_directo(self):
        base = AnuncioRepository.resumen_por_origen(None)["base"]
        c1 = ConversacionRepository.crear(id_externo=T1)
        _llegada(c1["id"], _referral(ANUNCIO_A), "wamid.1")

        despues = AnuncioRepository.resumen_por_origen(None)["base"]

        assert despues["conv_directo"] == base["conv_directo"]  # la conversación nueva no se suma a «directo»
