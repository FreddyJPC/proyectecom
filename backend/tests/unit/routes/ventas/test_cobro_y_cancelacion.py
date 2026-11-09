"""
Contra la base real (la de pruebas local): cobrar y cancelar una venta de un producto propio (ADR-012).

Lo que más importa: cancelar es TODO O NADA y devuelve el stock UNA sola vez (aunque se toque dos veces o
dos personas a la vez), y devuelve exactamente lo que se descontó al cerrar. Autocontenido: usa los
mismos SKU y teléfono de prueba que test_repository.py, con limpieza antes y después.
"""
import time
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import psycopg2
import pytest

from src.config.database import get_connection
from src.routes.gestion.repository import SolicitudGestionRepository
from src.routes.gestion.services import GestionService
from src.routes.productos_bot.repository import ProductoBotGestionRepository as ProductosRepo
from src.routes.ventas.exceptions import AccionDeVentaNoPermitidaError, VentaNoEncontradaError
from src.routes.ventas import repository as repositorio
from src.routes.ventas.repository import VentasRepository
from src.routes.ventas.snapshot import armar_venta
from src.routes.whatsapp.repository import LeadRepository
from tests.unit.routes.ventas.test_repository import (
    _cerrar,
    _estado_conversacion,
    _lead_listo,
    _limpiar,
    _producto,
    _stock,
)

MIGRACION = Path(__file__).resolve().parents[4] / "migrations" / "022_ventas_cobro_y_cancelacion.sql"


@pytest.fixture(autouse=True)
def limpio():
    _limpiar()
    yield
    _limpiar()


def _vender(stock=5, cantidad=2, controla=True):
    """Cierra una venta propia y devuelve (producto, lead, conversación, id de la venta)."""
    producto = _producto(stock=stock, controla=controla)
    lead, conversacion = _lead_listo(producto, cantidad=cantidad)
    resultado = _cerrar(producto, lead, conversacion)
    return producto, lead, conversacion, resultado["venta_id"]


def _solicitud(conversacion_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, estado, atendida_por, nota_atencion from solicitudes_gestion where conversacion_id = %s",
                (conversacion_id,),
            )
            return cur.fetchall()


class TestCobrar:
    def test_marca_la_venta_como_cobrada_con_quien_y_cuando(self):
        _, _, _, venta_id = _vender()

        venta = VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", "Transferencia verificada")

        assert venta["cobrada_en"] is not None
        assert (venta["cobrada_por"], venta["nota_cobro"]) == ("freddy@azoshop.ec", "Transferencia verificada")
        assert venta["estado"] == "por_gestionar"  # cobrar no cambia el estado de la gestión

    def test_no_se_cobra_dos_veces(self):
        _, _, _, venta_id = _vender()
        VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", None)

        with pytest.raises(AccionDeVentaNoPermitidaError) as error:
            VentasRepository.cobrar(venta_id, "otra@persona.ec", None)

        assert "ya estaba marcada como cobrada" in error.value.motivo
        assert VentasRepository.obtener(venta_id)["cobrada_por"] == "freddy@azoshop.ec"

    def test_deshacer_el_cobro_lo_deja_como_estaba_y_se_puede_volver_a_cobrar(self):
        _, _, _, venta_id = _vender()
        VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", "por error")

        venta = VentasRepository.deshacer_cobro(venta_id)

        assert (venta["cobrada_en"], venta["cobrada_por"], venta["nota_cobro"]) == (None, None, None)
        assert VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", None)["cobrada_en"] is not None

    def test_no_se_deshace_un_cobro_que_no_existe(self):
        _, _, _, venta_id = _vender()
        with pytest.raises(AccionDeVentaNoPermitidaError):
            VentasRepository.deshacer_cobro(venta_id)

    def test_una_venta_que_no_existe(self):
        with pytest.raises(VentaNoEncontradaError):
            VentasRepository.cobrar(999999999, "freddy@azoshop.ec", None)

    def test_una_venta_de_rocketfy_no_se_cobra_aqui(self):
        producto = _producto()
        lead, conversacion = _lead_listo(producto, cantidad=1)
        rocketfy = {**producto, "proveedor_id": 1, "proveedor_clave": "rocketfy", "proveedor_cierre": "rocketfy", "costo_rocketfy": Decimal("10.00")}
        venta, lineas = armar_venta(lead, rocketfy, conversacion, None, "despachada", Decimal("0.00"))
        venta_id = VentasRepository.registrar(venta, lineas)

        with pytest.raises(AccionDeVentaNoPermitidaError) as error:
            VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", None)

        assert "Rocketfy" in error.value.motivo


class TestCancelar:
    def test_cancela_todo_en_una_transaccion_y_devuelve_el_stock(self):
        producto, lead, conversacion, venta_id = _vender(stock=5, cantidad=2)
        assert _stock(producto["sku"]) == 3
        assert _estado_conversacion(conversacion["id"]) == "en_gestion"

        resultado = VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", "El cliente se arrepintió")

        assert resultado["estado"] == "cancelada"
        assert (resultado["cancelada_por"], resultado["motivo_cancelacion"]) == ("freddy@azoshop.ec", "El cliente se arrepintió")
        assert resultado["cancelada_en"] is not None
        assert resultado["stock_devuelto"] == 2 and _stock(producto["sku"]) == 5
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] == "cancelado"
        # Cancelar la venta pasa el lead de «ganado» a «perdido» (motivo: el que escribió el dueño), con su historial.
        perdido = LeadRepository.obtener_por_id(lead["id"])
        assert (perdido["temperatura"], perdido["motivo_perdida"], perdido["temperatura_motivo"]) == (
            "perdido", "otro", "El cliente se arrepintió")
        # La solicitud pendiente de esa venta ya no tiene nada que gestionar y el chat queda libre.
        assert _solicitud(conversacion["id"])[0][1:] == ("atendida", "freddy@azoshop.ec", "Venta cancelada: El cliente se arrepintió")
        assert _estado_conversacion(conversacion["id"]) == "activa"

    def test_sin_motivo_la_nota_dice_solo_que_se_cancelo(self):
        _, _, conversacion, venta_id = _vender()
        VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)
        assert _solicitud(conversacion["id"])[0][3] == "Venta cancelada."

    def test_no_se_cancela_dos_veces_ni_se_devuelve_el_stock_dos_veces(self):
        producto, _, _, venta_id = _vender(stock=5, cantidad=2)
        VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        with pytest.raises(AccionDeVentaNoPermitidaError) as error:
            VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert "ya estaba cancelada" in error.value.motivo
        assert _stock(producto["sku"]) == 5

    def test_dos_cancelaciones_a_la_vez_devuelven_el_stock_una_sola_vez(self, monkeypatch):
        producto, _, _, venta_id = _vender(stock=5, cantidad=2)

        # Una transacción tan corta casi nunca se solapa con otra: se ensancha a propósito la ventana de la
        # carrera (pausa DENTRO de la transacción, después de decidir). Sin el bloqueo de la fila, las dos
        # cancelaciones verían la venta abierta y devolverían el stock dos veces.
        original = repositorio.motivo_para_no_cancelar

        def lenta(venta):
            motivo = original(venta)
            time.sleep(0.3)
            return motivo

        monkeypatch.setattr(repositorio, "motivo_para_no_cancelar", lenta)

        def intentar(_):
            try:
                VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)
                return "cancelada"
            except AccionDeVentaNoPermitidaError:
                return "rechazada"

        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados = sorted(pool.map(intentar, range(2)))

        assert resultados == ["cancelada", "rechazada"]
        assert _stock(producto["sku"]) == 5

    def test_una_venta_cobrada_no_se_cancela_hasta_deshacer_el_cobro(self):
        producto, lead, conversacion, venta_id = _vender(stock=5, cantidad=2)
        VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", None)

        with pytest.raises(AccionDeVentaNoPermitidaError) as error:
            VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert "deshaz primero el cobro" in error.value.motivo
        # Nada cambió: ni el stock, ni el estado, ni el lead, ni la solicitud.
        assert _stock(producto["sku"]) == 3
        assert VentasRepository.obtener(venta_id)["estado"] == "por_gestionar"
        assert LeadRepository.obtener_por_id(lead["id"])["estado"] == "por_gestionar"
        assert _solicitud(conversacion["id"])[0][1] == "pendiente"

        VentasRepository.deshacer_cobro(venta_id)
        assert VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)["estado"] == "cancelada"
        assert _stock(producto["sku"]) == 5

    def test_si_se_vendio_la_ultima_unidad_el_stock_vuelve_pero_el_producto_sigue_agotado(self):
        producto, _, _, venta_id = _vender(stock=2, cantidad=2)
        assert ProductosRepo.obtener(producto["sku"])["estado"] == "agotado"

        resultado = VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert _stock(producto["sku"]) == 2
        # Reanudar es manual (igual que al agotarse): la pantalla se lo avisa al dueño.
        assert resultado["producto_sigue_agotado"] is True
        assert ProductosRepo.obtener(producto["sku"])["estado"] == "agotado"

    def test_un_producto_sin_control_de_stock_no_devuelve_nada(self):
        producto, _, _, venta_id = _vender(controla=False, cantidad=2)

        resultado = VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert resultado["stock_devuelto"] == 0 and _stock(producto["sku"]) is None

    def test_devuelve_lo_que_se_descontó_aunque_despues_se_apague_el_control_de_stock(self):
        producto, _, _, venta_id = _vender(stock=5, cantidad=2)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update productos_bot set controla_stock = false where sku = %s", (producto["sku"],))

        resultado = VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert resultado["stock_devuelto"] == 2 and _stock(producto["sku"]) == 5

    def test_no_inventa_unidades_si_el_control_de_stock_se_encendio_despues_de_vender(self):
        producto, _, _, venta_id = _vender(controla=False, cantidad=2)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "update productos_bot set controla_stock = true, stock_ultimo = 10 where sku = %s", (producto["sku"],)
                )

        resultado = VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert resultado["stock_devuelto"] == 0 and _stock(producto["sku"]) == 10

    def test_cancelar_una_venta_ya_atendida_no_toca_el_chat(self):
        producto, _, conversacion, venta_id = _vender(stock=5, cantidad=1)
        solicitud_id = _solicitud(conversacion["id"])[0][0]
        SolicitudGestionRepository.atender(solicitud_id, "freddy@azoshop.ec", "Coordinado")
        # Después de atender, el chat volvió a Victoria; cancelar no debe cambiar nada de eso.
        assert _estado_conversacion(conversacion["id"]) == "activa"

        VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert _solicitud(conversacion["id"])[0][1:] == ("atendida", "freddy@azoshop.ec", "Coordinado")
        assert _estado_conversacion(conversacion["id"]) == "activa"
        assert _stock(producto["sku"]) == 5

    def test_una_venta_de_rocketfy_no_se_cancela_aqui(self):
        producto = _producto()
        lead, conversacion = _lead_listo(producto, cantidad=1)
        rocketfy = {**producto, "proveedor_id": 1, "proveedor_clave": "rocketfy", "proveedor_cierre": "rocketfy", "costo_rocketfy": Decimal("10.00")}
        venta, lineas = armar_venta(lead, rocketfy, conversacion, None, "despachada", Decimal("0.00"))
        venta_id = VentasRepository.registrar(venta, lineas)

        with pytest.raises(AccionDeVentaNoPermitidaError) as error:
            VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        assert "Rocketfy" in error.value.motivo
        assert VentasRepository.obtener(venta_id)["estado"] == "despachada"

    def test_una_venta_que_no_existe(self):
        with pytest.raises(VentaNoEncontradaError):
            VentasRepository.cancelar(999999999, "freddy@azoshop.ec", None)


class TestLaListaDeGestionMuestraLaVenta:
    """Lo que ve la pantalla «Por gestionar» sale de la consulta real: se prueba contra la base."""

    def test_una_venta_abierta_deja_cobrar_y_cancelar(self):
        _, _, _, venta_id = _vender()

        item = GestionService().listar("pendiente")[0]

        assert item["venta_id"] == venta_id and item["venta_estado"] == "por_gestionar"
        assert (item["puede_cobrar"], item["puede_deshacer_cobro"], item["puede_cancelar"]) == (True, False, True)

    def test_tras_cobrar_se_ve_quien_y_cuando(self):
        _, _, _, venta_id = _vender()
        VentasRepository.cobrar(venta_id, "freddy@azoshop.ec", "Transferencia verificada")

        item = GestionService().listar("pendiente")[0]

        assert item["venta_cobrada_por"] == "freddy@azoshop.ec" and item["venta_nota_cobro"] == "Transferencia verificada"
        assert item["venta_cobrada_en"] is not None
        assert (item["puede_cobrar"], item["puede_deshacer_cobro"], item["puede_cancelar"]) == (False, True, False)

    def test_tras_cancelar_pasa_a_atendidas_con_el_motivo(self):
        _, _, _, venta_id = _vender()
        VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", "Se arrepintió")

        assert GestionService().listar("pendiente") == []
        item = GestionService().listar("atendida")[0]

        assert item["venta_estado"] == "cancelada" and item["venta_motivo_cancelacion"] == "Se arrepintió"
        assert item["venta_cancelada_por"] == "freddy@azoshop.ec" and item["venta_cancelada_en"] is not None
        assert (item["puede_cobrar"], item["puede_deshacer_cobro"], item["puede_cancelar"]) == (False, False, False)


class TestLineasRecuerdanElStockDescontado:
    def test_el_cierre_guarda_cuantas_unidades_descontó(self):
        _, _, _, venta_id = _vender(stock=5, cantidad=2)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select stock_descontado from ventas_lineas where venta_id = %s", (venta_id,))
                assert cur.fetchall() == [(2,)]

    def test_sin_control_de_stock_no_guarda_nada(self):
        _, _, _, venta_id = _vender(controla=False)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select stock_descontado from ventas_lineas where venta_id = %s", (venta_id,))
                assert cur.fetchall() == [(None,)]


class TestMigracion022:
    def test_se_puede_aplicar_dos_veces(self):
        sql = MIGRACION.read_text(encoding="utf8")
        for _ in range(2):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(sql)

    def test_una_venta_cancelada_no_puede_quedar_cobrada(self):
        _, _, _, venta_id = _vender()
        VentasRepository.cancelar(venta_id, "freddy@azoshop.ec", None)

        with pytest.raises(psycopg2.errors.CheckViolation):
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("update ventas set cobrada_en = now() where id = %s", (venta_id,))
