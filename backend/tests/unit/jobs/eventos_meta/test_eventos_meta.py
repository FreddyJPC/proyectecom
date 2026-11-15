"""
Aviso de ventas a Meta (ADR-016, pendiente #68): solo las ventas de anuncio ya CONFIRMADAS, una sola vez por venta, sin que Meta pueda
afectar la venta, y sin reintentar a ciegas cuando no se sabe si Meta lo recibió (Meta no deduplica).
Las pruebas de la bandeja usan la base de pruebas real (nunca la de producción) y limpian antes y después.
"""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.config.database import get_connection
from src.config.parametros import parametros
from src.integrations.meta import MetaRechazoError, MetaRespuestaDudosaError
from src.jobs.eventos_meta.reglas import minutos_para_reintentar, venta_confirmada
from src.jobs.eventos_meta.repository import EventosMetaRepository
from src.jobs.eventos_meta.service import EventosMetaService
from src.routes.anuncios.referral import normalizar_referral
from src.routes.anuncios.repository import AnuncioRepository
from src.routes.productos_bot.repository import ProductoBotGestionRepository as ProductosRepo
from src.routes.ventas.repository import VentasRepository
from src.routes.ventas.snapshot import armar_venta
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository
from tests.helpers_db import borrar_conversaciones_de_prueba

TELEFONO = "593900007777"
ID_ANUNCIO = "anuncio-meta-test"


class TestLasReglas:
    def test_una_venta_con_pedido_de_rocketfy_esta_confirmada(self):
        assert venta_confirmada({"estado": "despachada", "id_pedido_rocketfy": 77, "cobrada_en": None})

    def test_un_producto_propio_solo_cuenta_cuando_se_cobra(self):
        assert not venta_confirmada({"estado": "por_gestionar", "id_pedido_rocketfy": None, "cobrada_en": None})
        assert venta_confirmada({"estado": "gestionada", "id_pedido_rocketfy": None, "cobrada_en": datetime.now(timezone.utc)})

    def test_una_venta_cancelada_nunca_cuenta(self):
        assert not venta_confirmada({"estado": "cancelada", "id_pedido_rocketfy": 77, "cobrada_en": datetime.now(timezone.utc)})

    def test_los_reintentos_esperan_cada_vez_mas(self):
        assert [minutos_para_reintentar(n) for n in (0, 1, 2, 3)] == [15, 15, 30, 45]


# ---------------------------------------------------------------------------------------------------------------------
# El servicio, con una bandeja falsa (sin base de datos): qué hace con cada respuesta de Meta
# ---------------------------------------------------------------------------------------------------------------------
def _evento(id=1, intentos=1, venta_estado="por_gestionar", pedido=None, cobrada=datetime(2026, 11, 11, tzinfo=timezone.utc)):
    return {
        "id": id, "venta_id": 10 + id, "ctwa_clid": "clic-1", "valor": Decimal("30.00"), "moneda": "USD",
        "ocurrido_en": datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc), "intentos": intentos,
        "venta_estado": venta_estado, "id_pedido_rocketfy": pedido, "cobrada_en": cobrada,
    }


@pytest.fixture
def encendido():
    parametros.guardar("meta.activo", True, "test@ejemplo.com")
    yield
    parametros.restaurar("meta.activo", "test@ejemplo.com")


def _servicio(eventos, cliente=None):
    repo = MagicMock()
    repo.recuperar_colgados.return_value = 0
    repo.reclamar.return_value = eventos
    telegram = MagicMock()
    return EventosMetaService(repo=repo, cliente=cliente or MagicMock(), telegram=telegram), repo, telegram


class TestElServicio:
    def test_apagado_no_hace_nada(self):
        servicio, repo, _ = _servicio([_evento()])
        assert servicio.ejecutar() == 0
        repo.detectar.assert_not_called()
        repo.reclamar.assert_not_called()

    def test_sin_las_variables_del_servidor_no_envia_nada(self, encendido, monkeypatch):
        for v in ("META_CAPI_TOKEN", "META_DATASET_ID", "WHATSAPP_WABA_ID"):
            monkeypatch.delenv(v, raising=False)
        repo = MagicMock()
        servicio = EventosMetaService(repo=repo, telegram=MagicMock())
        assert servicio.ejecutar() == 0
        repo.detectar.assert_not_called()

    def test_un_envio_aceptado_queda_enviado(self, encendido):
        cliente = MagicMock()
        cliente.enviar_compra.return_value = '{"events_received": 1}'
        servicio, repo, telegram = _servicio([_evento()], cliente)
        assert servicio.ejecutar() == 1
        repo.marcar_enviado.assert_called_once_with(1, '{"events_received": 1}')
        cliente.enviar_compra.assert_called_once_with("clic-1", Decimal("30.00"), "USD", datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc))
        telegram.notificar_aviso.assert_not_called()

    def test_si_la_venta_se_cancelo_antes_de_enviar_no_se_avisa(self, encendido):
        cliente = MagicMock()
        servicio, repo, _ = _servicio([_evento(venta_estado="cancelada")], cliente)
        assert servicio.ejecutar() == 0
        cliente.enviar_compra.assert_not_called()
        repo.marcar_descartado.assert_called_once()

    def test_si_se_deshizo_el_cobro_antes_de_enviar_no_se_avisa(self, encendido):
        cliente = MagicMock()
        servicio, repo, _ = _servicio([_evento(cobrada=None)], cliente)
        servicio.ejecutar()
        cliente.enviar_compra.assert_not_called()
        repo.marcar_descartado.assert_called_once()

    def test_un_rechazo_se_reprograma_con_espera_creciente(self, encendido):
        cliente = MagicMock()
        cliente.enviar_compra.side_effect = MetaRechazoError("parámetro inválido")
        servicio, repo, telegram = _servicio([_evento(intentos=2)], cliente)
        servicio.ejecutar()
        repo.reprogramar.assert_called_once_with(1, "parámetro inválido", 30)
        repo.marcar_fallido.assert_not_called()
        telegram.notificar_aviso.assert_not_called()

    def test_al_agotar_los_intentos_queda_fallido_y_avisa_por_telegram(self, encendido):
        cliente = MagicMock()
        cliente.enviar_compra.side_effect = MetaRechazoError("token vencido")
        servicio, repo, telegram = _servicio([_evento(intentos=3)], cliente)  # 3 = el máximo por defecto
        servicio.ejecutar()
        repo.marcar_fallido.assert_called_once()
        repo.reprogramar.assert_not_called()
        telegram.notificar_aviso.assert_called_once()

    def test_una_respuesta_dudosa_nunca_se_reintenta_y_avisa(self, encendido):
        cliente = MagicMock()
        cliente.enviar_compra.side_effect = MetaRespuestaDudosaError("tardó demasiado")
        servicio, repo, telegram = _servicio([_evento(intentos=1)], cliente)
        servicio.ejecutar()
        repo.marcar_dudoso.assert_called_once_with(1, "tardó demasiado")
        repo.reprogramar.assert_not_called()
        repo.marcar_fallido.assert_not_called()
        telegram.notificar_aviso.assert_called_once()

    def test_un_fallo_inesperado_deja_el_evento_dudoso_y_no_impide_los_demas(self, encendido):
        cliente = MagicMock()
        cliente.enviar_compra.side_effect = [RuntimeError("boom"), '{"events_received": 1}']
        servicio, repo, _ = _servicio([_evento(id=1), _evento(id=2)], cliente)
        assert servicio.ejecutar() == 1
        repo.marcar_dudoso.assert_called_once()
        repo.marcar_enviado.assert_called_once_with(2, '{"events_received": 1}')

    def test_lo_que_quedo_a_medias_se_avisa_como_dudoso(self, encendido):
        servicio, repo, telegram = _servicio([])
        repo.recuperar_colgados.return_value = 2
        servicio.ejecutar()
        telegram.notificar_aviso.assert_called_once()

    def test_la_espera_y_la_antiguedad_salen_de_los_parametros(self, encendido):
        servicio, repo, _ = _servicio([])
        servicio.ejecutar()
        repo.detectar.assert_called_once_with(60, 7)


# ---------------------------------------------------------------------------------------------------------------------
# La bandeja contra la base real
# ---------------------------------------------------------------------------------------------------------------------
def _limpiar():
    borrar_conversaciones_de_prueba(TELEFONO)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("delete from productos_bot where nombre like 'TEST-META %'")


@pytest.fixture
def base():
    _limpiar()
    yield
    _limpiar()


def _producto():
    fila = ProductosRepo.crear_propio(
        {
            "nombre": "TEST-META Zapatos", "descripcion": "Zapatos", "precio": Decimal("30.00"), "tiempo_entrega": "2 días",
            "metodos_pago_aceptados": "contraentrega", "max_unidades_por_pedido": 5, "costo_propio": Decimal("18.00"),
            "controla_stock": True, "stock_ultimo": 10, "envio_incluido": True, "costo_flete_estimado": None, "categoria_id": None,
        },
        [],
    )
    return ProductosRepo.cambiar_estado(fila["sku"], "activo", "test")


def _venta_de_anuncio(con_clic=True, anuncio=True):
    """Cierra una venta propia (por gestionar, sin cobrar). Devuelve su id."""
    producto = _producto()
    conversacion = ConversacionRepository.crear(id_externo=TELEFONO, origen="anuncio" if anuncio else "directo", id_anuncio=ID_ANUNCIO if anuncio else None)
    if anuncio:
        referral = {"source_id": ID_ANUNCIO, "source_type": "ad"}
        if con_clic:
            referral["ctwa_clid"] = "clic-meta-test"
        AnuncioRepository.registrar_llegada(conversacion["id"], None, "wamid.meta-test", normalizar_referral(referral), referral)
    lead = LeadRepository.obtener_o_crear(conversacion["id"], conversacion["contacto_id"], telefono=TELEFONO)
    LeadRepository.actualizar_datos_cliente(lead["id"], "Ana", "Calle 1", "Cuenca", "Azuay")
    LeadRepository.actualizar_producto(lead["id"], producto["sku"], producto["nombre"], Decimal("60.00"), variante="40", cantidad=2)
    LeadRepository.actualizar_metodo_pago(lead["id"], "contraentrega", esperar_comprobante=False)
    lead = LeadRepository.obtener_por_id(lead["id"])
    conversacion = ConversacionRepository.obtener_por_id(conversacion["id"])
    venta, lineas = armar_venta(lead, producto, conversacion, None, "por_gestionar", Decimal("0.00"))
    return VentasRepository.cerrar_manual(venta, lineas, producto["sku"], 2, True, "detalle")["venta_id"]


def _eventos():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select e.estado, e.motivo, e.ctwa_clid, e.valor, e.venta_id from eventos_meta e join ventas v on v.id = e.venta_id "
                "where v.telefono = %s order by e.id",
                (TELEFONO,),
            )
            return cur.fetchall()


def _pasar_a_rocketfy(venta_id):
    """Simula que la venta se cerró con un pedido de Rocketfy (ya viene confirmado)."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("update ventas set id_pedido_rocketfy = 987001, id_pedido_local = 987001 where id = %s", (venta_id,))


class TestLaBandejaContraLaBase:
    def test_una_venta_propia_sin_cobrar_todavia_no_cuenta(self, base):
        _venta_de_anuncio()
        assert EventosMetaRepository.detectar(0, 7) == 0
        assert _eventos() == []

    def test_una_venta_propia_cobrada_se_anota_con_su_valor_y_su_clic(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        assert EventosMetaRepository.detectar(0, 7) == 1
        estado, motivo, clic, valor, vid = _eventos()[0]
        assert (estado, motivo, clic, valor, vid) == ("pendiente", None, "clic-meta-test", Decimal("60.00"), venta_id)

    def test_una_venta_de_rocketfy_cuenta_apenas_se_cierra(self, base):
        venta_id = _venta_de_anuncio()
        _pasar_a_rocketfy(venta_id)
        assert EventosMetaRepository.detectar(0, 7) == 1

    def test_repetir_la_deteccion_nunca_duplica_el_evento(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        assert EventosMetaRepository.detectar(0, 7) == 1
        assert EventosMetaRepository.detectar(0, 7) == 0
        assert len(_eventos()) == 1

    def test_respeta_la_espera_antes_de_avisar(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        assert EventosMetaRepository.detectar(60, 7) == 0  # se cobró hace un instante: aún no pasaron 60 minutos
        assert _eventos() == []

    def test_una_venta_cancelada_no_se_anota(self, base):
        venta_id = _venta_de_anuncio()
        _pasar_a_rocketfy(venta_id)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update ventas set estado = 'cancelada' where id = %s", (venta_id,))
        assert EventosMetaRepository.detectar(0, 7) == 0

    def test_una_venta_directa_no_se_avisa_a_meta(self, base):
        venta_id = _venta_de_anuncio(anuncio=False)
        VentasRepository.cobrar(venta_id, "dueno", None)
        assert EventosMetaRepository.detectar(0, 7) == 0
        assert _eventos() == []

    def test_una_venta_de_anuncio_sin_clic_queda_descartada_con_su_motivo(self, base):
        venta_id = _venta_de_anuncio(con_clic=False)
        VentasRepository.cobrar(venta_id, "dueno", None)
        EventosMetaRepository.detectar(0, 7)
        estado, motivo, clic, _, _ = _eventos()[0]
        assert estado == "descartado" and clic is None and "identificador del clic" in motivo

    def test_una_venta_demasiado_antigua_queda_descartada(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update ventas set cobrada_en = now() - interval '10 days' where id = %s", (venta_id,))
        EventosMetaRepository.detectar(0, 7)
        estado, motivo, *_ = _eventos()[0]
        assert estado == "descartado" and "antigua" in motivo

    def test_reclamar_reserva_el_evento_y_nadie_mas_lo_toma(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        EventosMetaRepository.detectar(0, 7)
        tomados = EventosMetaRepository.reclamar(10)
        mios = [t for t in tomados if t["venta_id"] == venta_id]
        assert len(mios) == 1 and mios[0]["intentos"] == 1 and mios[0]["venta_estado"] == "por_gestionar"
        assert [t for t in EventosMetaRepository.reclamar(10) if t["venta_id"] == venta_id] == []
        assert _eventos()[0][0] == "enviando"

    def test_un_envio_que_quedo_a_medias_pasa_a_dudoso_y_no_se_reenvia(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        EventosMetaRepository.detectar(0, 7)
        EventosMetaRepository.reclamar(10)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("update eventos_meta set actualizado_en = now() - interval '1 hour' where venta_id = %s", (venta_id,))
        assert EventosMetaRepository.recuperar_colgados(10) >= 1
        assert _eventos()[0][0] == "dudoso"
        assert [t for t in EventosMetaRepository.reclamar(10) if t["venta_id"] == venta_id] == []

    def test_un_rechazo_reprogramado_no_se_vuelve_a_tomar_antes_de_tiempo(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        EventosMetaRepository.detectar(0, 7)
        evento = [t for t in EventosMetaRepository.reclamar(10) if t["venta_id"] == venta_id][0]
        EventosMetaRepository.reprogramar(evento["id"], "rechazado", 15)
        assert [t for t in EventosMetaRepository.reclamar(10) if t["venta_id"] == venta_id] == []
        assert _eventos()[0][0] == "pendiente"

    def test_el_ciclo_completo_con_un_cliente_falso_envia_una_sola_vez(self, base):
        venta_id = _venta_de_anuncio()
        VentasRepository.cobrar(venta_id, "dueno", None)
        parametros.guardar("meta.activo", True, "test@ejemplo.com")
        parametros.guardar("meta.minutos_espera", 0, "test@ejemplo.com")
        try:
            cliente = MagicMock()
            cliente.enviar_compra.return_value = '{"events_received": 1}'
            servicio = EventosMetaService(cliente=cliente, telegram=MagicMock())
            servicio.ejecutar()
            servicio.ejecutar()  # una segunda pasada no vuelve a enviar
            llamadas = [c for c in cliente.enviar_compra.call_args_list if c.args[0] == "clic-meta-test"]
            assert len(llamadas) == 1 and llamadas[0].args[1] == Decimal("60.00")
            assert _eventos()[0][0] == "enviado"
        finally:
            parametros.restaurar("meta.activo", "test@ejemplo.com")
            parametros.restaurar("meta.minutos_espera", "test@ejemplo.com")
