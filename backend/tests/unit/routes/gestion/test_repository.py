"""Solicitudes de gestión contra la base real: una sola pendiente por conversación, que va subiendo de categoría."""
from decimal import Decimal

import pytest

from src.config.database import get_connection
from src.routes.gestion.repository import SolicitudGestionRepository as Repo
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900005678"


def _limpiar():
    borrar_conversaciones_de_prueba(TELEFONO)


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


@pytest.fixture
def conversacion():
    c = ConversacionRepository.crear(id_externo=TELEFONO, origen="directo")
    lead = LeadRepository.obtener_o_crear(c["id"], c["contacto_id"], telefono=TELEFONO)
    return c["id"], lead["id"]


class TestSolicitar:
    def test_la_primera_crea_y_las_siguientes_completan_la_misma(self, conversacion):
        conversacion_id, lead_id = conversacion

        primera = Repo.solicitar(conversacion_id, lead_id, "quiere_comprar", "lo quiere")
        repetida = Repo.solicitar(conversacion_id, lead_id, "quiere_comprar", "otra vez")
        sube = Repo.solicitar(conversacion_id, lead_id, "quiere_pagar", "quiere pagar")
        mayor = Repo.solicitar(conversacion_id, lead_id, "quiere_ver_producto", "quiere verlo")

        assert primera.creada and primera.tipo == "quiere_comprar"
        assert not repetida.creada and repetida.id == primera.id and not repetida.cambio_de_tipo
        assert not sube.cambio_de_tipo  # misma categoría: no cambia ni vuelve a avisar
        assert mayor.cambio_de_tipo and mayor.tipo == "quiere_ver_producto" and mayor.tipo_anterior == "quiere_comprar"
        assert len(Repo.listar("pendiente")) == 1

    def test_pedido_cerrado_nunca_baja_a_una_categoria_menor(self, conversacion):
        conversacion_id, lead_id = conversacion
        Repo.solicitar(conversacion_id, lead_id, "pedido_cerrado", "pedido")

        resultado = Repo.solicitar(conversacion_id, lead_id, "quiere_comprar", "ya lo quería")

        assert resultado.tipo == "pedido_cerrado" and not resultado.cambio_de_tipo

    def test_la_base_impide_dos_pendientes_en_la_misma_conversacion(self, conversacion):
        import psycopg2.errors

        conversacion_id, lead_id = conversacion
        Repo.solicitar(conversacion_id, lead_id, "otro", "x")
        with pytest.raises(psycopg2.errors.UniqueViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "insert into solicitudes_gestion (conversacion_id, tipo) values (%s, 'otro')", (conversacion_id,)
                    )


class TestListarYAtender:
    def test_listar_trae_los_datos_del_cliente_y_cuenta_pendientes(self, conversacion):
        conversacion_id, lead_id = conversacion
        LeadRepository.actualizar_datos_cliente(lead_id, "Ana", "Calle 1", "Cuenca", "Azuay")
        Repo.solicitar(conversacion_id, lead_id, "quiere_ver_producto", "quiere verlo")

        pendientes = [s for s in Repo.listar("pendiente") if s["conversacion_id"] == conversacion_id]

        assert len(pendientes) == 1
        assert pendientes[0]["telefono"] == TELEFONO and pendientes[0]["nombre_cliente"] == "Ana"
        assert Repo.contar_pendientes() >= 1

    def test_atender_cierra_la_solicitud_y_devuelve_la_conversacion_a_activa(self, conversacion):
        conversacion_id, lead_id = conversacion
        nueva = Repo.solicitar(conversacion_id, lead_id, "quiere_negociar", "pide rebaja")
        ConversacionRepository.marcar_en_gestion(conversacion_id)

        atendida = Repo.atender(nueva.id, "freddy@azoshop.com", "ya lo llamé")

        assert atendida["estado"] == "atendida" and atendida["atendida_por"] == "freddy@azoshop.com"
        assert atendida["nota_atencion"] == "ya lo llamé" and atendida["atendida_en"] is not None
        assert ConversacionRepository.obtener_por_id(conversacion_id)["estado"] == "activa"
        assert Repo.atender(nueva.id, "freddy@azoshop.com", None) is None  # ya estaba atendida

    def test_atender_pasa_la_venta_a_gestionada(self, conversacion):
        conversacion_id, lead_id = conversacion
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "insert into ventas (lead_id, conversacion_id, contacto_id, proveedor_id, estado, subtotal, total, telefono) "
                    "select %s, %s, contacto_id, 2, 'por_gestionar', %s, %s, %s from conversaciones where id = %s returning id",
                    (lead_id, conversacion_id, Decimal("30.00"), Decimal("30.00"), TELEFONO, conversacion_id),
                )
                venta_id = cur.fetchone()[0]
        nueva = Repo.solicitar(conversacion_id, lead_id, "pedido_cerrado", "pedido", venta_id=venta_id)

        Repo.atender(nueva.id, "freddy@azoshop.com", None)

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select estado, gestionada_por, gestionada_en is not null from ventas where id = %s", (venta_id,))
                assert cur.fetchone() == ("gestionada", "freddy@azoshop.com", True)
                cur.execute("delete from ventas where id = %s", (venta_id,))

    def test_despues_de_atender_puede_haber_otra_pendiente_nueva(self, conversacion):
        conversacion_id, lead_id = conversacion
        primera = Repo.solicitar(conversacion_id, lead_id, "otro", "x")
        Repo.atender(primera.id, "freddy", None)

        segunda = Repo.solicitar(conversacion_id, lead_id, "otro", "y")

        assert segunda.creada and segunda.id != primera.id
