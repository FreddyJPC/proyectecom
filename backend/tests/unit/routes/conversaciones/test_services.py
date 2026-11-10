"""
Tests del módulo de Conversaciones (dashboard). Repositorios falsos en
memoria (mismo patrón que routes/whatsapp) + WhatsAppClient mockeado --
ninguno de estos toca Supabase ni WhatsApp real.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from src.integrations.whatsapp import WhatsAppBusinessError
from src.routes.conversaciones.exceptions import (
    SinPedidoEnCursoError,
    ArchivoNoDisponibleError,
    ConversacionNoEncontradaError,
    EnvioWhatsAppFallidoError,
    VentanaMensajeriaCerradaError,
)
from src.routes.anuncios.servicio import AnuncioServicio
from src.routes.conversaciones.services import ConversacionesService
from tests.helpers_canales import registro_de_whatsapp

AHORA = datetime.now(timezone.utc)


class FakeConversacionRepository:
    def __init__(self, conversaciones=None):
        self.tabla = {c["id"]: dict(c) for c in (conversaciones or [])}

    def obtener_por_id(self, conversacion_id):
        fila = self.tabla.get(conversacion_id)
        return dict(fila) if fila else None

    def listar(self, estado=None, origen=None, q=None, page=1, page_size=20, canal=None):
        filas = list(self.tabla.values())
        if estado:
            filas = [f for f in filas if f["estado"] == estado]
        if origen:
            filas = [f for f in filas if f["origen"] == origen]
        if canal:
            filas = [f for f in filas if f["canal"] == canal]
        if q:
            filas = [f for f in filas if q in (f["telefono"] or "") or q.lower() in (f.get("nombre_cliente") or "").lower()]
        filas.sort(key=lambda f: f["creada_en"] if estado == "escalada" else f["actualizada_en"], reverse=(estado != "escalada"))
        total = len(filas)
        inicio = (page - 1) * page_size
        return {"items": filas[inicio : inicio + page_size], "total": total, "page": page, "page_size": page_size}

    def contar_por_filtro_rapido(self):
        filas = list(self.tabla.values())
        return {
            "escaladas": sum(1 for f in filas if f["estado"] == "escalada"),
            "escaladas_sin_revisar": sum(1 for f in filas if f["estado"] == "escalada" and f.get("vista_en") is None),
            "esperando_pago": sum(1 for f in filas if f["estado"] == "esperando_pago"),
        }

    def marcar_vista(self, conversacion_id):
        self.tabla[conversacion_id]["vista_en"] = datetime.now(timezone.utc)

    def actualizar_notas(self, conversacion_id, notas_internas):
        self.tabla[conversacion_id]["notas_internas"] = notas_internas

    def actualizar_estado(self, conversacion_id, estado):
        self.tabla[conversacion_id]["estado"] = estado

    def marcar_manual(self, conversacion_id):
        self.tabla[conversacion_id]["estado"] = "manual"
        self.tabla[conversacion_id]["vista_en"] = datetime.now(timezone.utc)

    def actualizar_timestamp(self, conversacion_id):
        self.tabla[conversacion_id]["actualizada_en"] = datetime.now(timezone.utc)


class FakeLeadRepository:
    def __init__(self, leads_por_conversacion=None):
        self._leads = leads_por_conversacion or {}
        self.pagos_confirmados = []

    def obtener_por_conversacion(self, conversacion_id):
        return self._leads.get(conversacion_id)

    def marcar_pago_confirmado(self, lead_id):
        self.pagos_confirmados.append(lead_id)


class FakeMensajeRepository:
    def __init__(self, mensajes_por_conversacion=None):
        self._mensajes = {k: list(v) for k, v in (mensajes_por_conversacion or {}).items()}
        self._siguiente_id = 1

    def obtener_por_conversacion(self, conversacion_id):
        return list(self._mensajes.get(conversacion_id, []))

    def obtener_por_id(self, mensaje_id):
        return next((dict(m) for ms in self._mensajes.values() for m in ms if m["id"] == mensaje_id), None)

    def crear(self, conversacion_id, rol, contenido, tipo="texto", wamid=None):
        mensaje = {
            "id": self._siguiente_id,
            "conversacion_id": conversacion_id,
            "rol": rol,
            "contenido": contenido,
            "tipo": tipo,
            "wamid": wamid,
            "creado_en": datetime.now(timezone.utc),
        }
        self._mensajes.setdefault(conversacion_id, []).append(mensaje)
        self._siguiente_id += 1
        return mensaje


def _conversacion(
    id=1, telefono="593987654321", origen="directo", estado="activa", vista_en=None,
    notas_internas=None, id_anuncio=None, creada_en=None, actualizada_en=None, canal="whatsapp", id_externo=None,
    contacto_nombre=None,
):
    return {
        "id": id,
        "contacto_id": id,
        "canal": canal,
        "id_externo": id_externo or telefono,
        "telefono": telefono,
        "contacto_nombre": contacto_nombre,
        "origen": origen,
        "estado": estado,
        "id_anuncio": id_anuncio,
        "vista_en": vista_en,
        "notas_internas": notas_internas,
        "creada_en": creada_en or AHORA,
        "actualizada_en": actualizada_en or AHORA,
    }


class FakeAnuncioRepository:
    """Lo que el servicio de anuncios lee de la base, en memoria."""

    def __init__(self, llegadas_por_conversacion=None, vinculos=None):
        self._llegadas = llegadas_por_conversacion or {}
        self._vinculos = vinculos or {}

    def llegadas_de(self, conversacion_id):
        return sorted(self._llegadas.get(conversacion_id, []), key=lambda l: l["creado_en"], reverse=True)

    def vinculo_de(self, id_anuncio):
        return self._vinculos.get(id_anuncio)


def _servicio(conversaciones=None, leads=None, mensajes=None, whatsapp=None, llegadas=None, vinculos=None, bot_worker=None):
    return ConversacionesService(
        bot_worker=bot_worker,
        canales=registro_de_whatsapp(whatsapp or MagicMock()),
        conversacion_repo=FakeConversacionRepository(conversaciones=conversaciones or []),
        lead_repo=FakeLeadRepository(leads_por_conversacion=leads or {}),
        mensaje_repo=FakeMensajeRepository(mensajes_por_conversacion=mensajes or {}),
        anuncio_servicio=AnuncioServicio(repo=FakeAnuncioRepository(llegadas, vinculos), productos=MagicMock()),
    )


class TestVentanaDeMensajeria:
    def test_ventana_cerrada_sin_mensajes_ni_fep(self):
        servicio = _servicio(conversaciones=[_conversacion(origen="directo")])
        with pytest.raises(VentanaMensajeriaCerradaError):
            servicio.enviar_mensaje_manual(1, "hola")

    def test_ventana_abierta_por_servicio_dentro_de_24h(self):
        mensajes = {1: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=2)}]}
        whatsapp = MagicMock()
        servicio = _servicio(conversaciones=[_conversacion()], mensajes=mensajes, whatsapp=whatsapp)

        mensaje = servicio.enviar_mensaje_manual(1, "respuesta del humano")

        assert mensaje.contenido == "respuesta del humano"
        whatsapp.enviar_texto.assert_called_once_with(telefono="593987654321", mensaje="respuesta del humano")

    def test_ventana_cerrada_por_servicio_fuera_de_24h_sin_fep(self):
        mensajes = {1: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=30)}]}
        servicio = _servicio(conversaciones=[_conversacion(origen="directo")], mensajes=mensajes)

        with pytest.raises(VentanaMensajeriaCerradaError):
            servicio.enviar_mensaje_manual(1, "hola")

    def test_la_ventana_gratuita_de_anuncio_no_permite_texto_libre_fuera_de_las_24h(self):
        """Regla vigente de Meta: la ventana de anuncio (FEP) es un beneficio de COSTO, no un permiso para escribir
        texto libre después de las 24 horas. Antes el panel lo permitía (regla anterior) y Meta lo rechazaba."""
        mensajes = {
            1: [
                {"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=30)},
                {"id": 2, "rol": "bot", "contenido": "¡Hola!", "creado_en": AHORA - timedelta(hours=30)},
            ]
        }
        llegadas = {1: [{"id_anuncio": "123", "creado_en": AHORA - timedelta(hours=30)}]}
        whatsapp = MagicMock()
        servicio = _servicio(
            conversaciones=[_conversacion(origen="anuncio", id_anuncio="123")], mensajes=mensajes, whatsapp=whatsapp, llegadas=llegadas
        )

        with pytest.raises(VentanaMensajeriaCerradaError):
            servicio.enviar_mensaje_manual(1, "hola de nuevo")

        whatsapp.enviar_texto.assert_not_called()

    def test_ventana_cerrada_no_llama_whatsapp_ni_inserta_mensaje(self):
        whatsapp = MagicMock()
        mensaje_repo = FakeMensajeRepository()
        servicio = ConversacionesService(
            canales=registro_de_whatsapp(whatsapp),
            conversacion_repo=FakeConversacionRepository(conversaciones=[_conversacion(origen="directo")]),
            lead_repo=FakeLeadRepository(),
            mensaje_repo=mensaje_repo,
            anuncio_servicio=AnuncioServicio(repo=FakeAnuncioRepository(), productos=MagicMock()),
        )

        with pytest.raises(VentanaMensajeriaCerradaError):
            servicio.enviar_mensaje_manual(1, "hola")

        whatsapp.enviar_texto.assert_not_called()
        assert mensaje_repo.obtener_por_conversacion(1) == []

    def test_fallo_de_envio_whatsapp_se_propaga_pero_el_mensaje_ya_quedo_guardado(self):
        mensajes = {1: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=1)}]}
        whatsapp = MagicMock()
        whatsapp.enviar_texto.side_effect = WhatsAppBusinessError("número no en ventana de 24h", code=131047)
        mensaje_repo = FakeMensajeRepository(mensajes_por_conversacion=mensajes)
        servicio = ConversacionesService(
            canales=registro_de_whatsapp(whatsapp),
            conversacion_repo=FakeConversacionRepository(conversaciones=[_conversacion()]),
            lead_repo=FakeLeadRepository(),
            mensaje_repo=mensaje_repo,
            anuncio_servicio=AnuncioServicio(repo=FakeAnuncioRepository(), productos=MagicMock()),
        )

        with pytest.raises(EnvioWhatsAppFallidoError):
            servicio.enviar_mensaje_manual(1, "hola")

        guardados = mensaje_repo.obtener_por_conversacion(1)
        assert any(m["rol"] == "humano" and m["contenido"] == "hola" for m in guardados)


class TestCanales:
    """ADR-014: la conversación sabe por qué canal habla el cliente y el panel no depende de que haya teléfono."""

    def test_el_listado_trae_canal_identificador_y_nombre_aunque_no_haya_telefono(self):
        servicio = _servicio(conversaciones=[
            _conversacion(id=1),
            _conversacion(id=2, telefono=None, canal="instagram", id_externo="17841400000000000", contacto_nombre="ana_ec"),
        ])
        items = {i.id: i for i in servicio.listar_conversaciones().items}
        assert (items[1].canal, items[1].id_externo, items[1].telefono) == ("whatsapp", "593987654321", "593987654321")
        assert (items[2].canal, items[2].id_externo, items[2].telefono, items[2].nombre) == (
            "instagram", "17841400000000000", None, "ana_ec",
        )

    def test_se_puede_filtrar_el_listado_por_canal(self):
        servicio = _servicio(conversaciones=[
            _conversacion(id=1),
            _conversacion(id=2, telefono=None, canal="instagram", id_externo="1784"),
        ])
        assert [i.id for i in servicio.listar_conversaciones(canal="instagram").items] == [2]

    def test_el_detalle_dice_el_canal_y_el_contacto(self):
        servicio = _servicio(conversaciones=[_conversacion(id=2, telefono=None, canal="instagram", id_externo="1784")])
        c = servicio.obtener_detalle(2).conversacion
        assert (c.canal, c.id_externo, c.telefono, c.contacto_id) == ("instagram", "1784", None, 2)

    def test_escribir_a_un_canal_sin_conectar_guarda_el_mensaje_y_avisa_que_no_salio(self):
        mensajes = {2: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=1)}]}
        whatsapp = MagicMock()
        mensaje_repo = FakeMensajeRepository(mensajes_por_conversacion=mensajes)
        servicio = ConversacionesService(
            canales=registro_de_whatsapp(whatsapp),
            conversacion_repo=FakeConversacionRepository(
                conversaciones=[_conversacion(id=2, telefono=None, canal="instagram", id_externo="1784")]
            ),
            lead_repo=FakeLeadRepository(),
            mensaje_repo=mensaje_repo,
            anuncio_servicio=AnuncioServicio(repo=FakeAnuncioRepository(), productos=MagicMock()),
        )

        with pytest.raises(EnvioWhatsAppFallidoError, match="todavía no está conectado"):
            servicio.enviar_mensaje_manual(2, "hola Ana")

        whatsapp.enviar_texto.assert_not_called()  # nunca se manda por el canal equivocado
        assert any(m["rol"] == "humano" for m in mensaje_repo.obtener_por_conversacion(2))


class TestObtenerDetalle:
    def test_marca_como_vista_una_escalada_sin_revisar(self):
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada", vista_en=None)])

        detalle = servicio.obtener_detalle(1)

        assert detalle.conversacion.estado == "escalada"
        # confirmar contra el propio repo (no solo el DTO devuelto)
        assert servicio._conversaciones.obtener_por_id(1)["vista_en"] is not None

    def test_no_toca_vista_en_si_ya_estaba_vista(self):
        vista_previa = AHORA - timedelta(hours=1)
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada", vista_en=vista_previa)])

        servicio.obtener_detalle(1)

        assert servicio._conversaciones.obtener_por_id(1)["vista_en"] == vista_previa

    def test_conversacion_inexistente_lanza_error(self):
        servicio = _servicio(conversaciones=[])
        with pytest.raises(ConversacionNoEncontradaError):
            servicio.obtener_detalle(999)

    def test_lead_ausente_no_rompe(self):
        servicio = _servicio(conversaciones=[_conversacion()], leads={})
        detalle = servicio.obtener_detalle(1)
        assert detalle.lead is None

    def test_incluye_variante_del_lead(self):
        lead = {"nombre_cliente": "Juan", "producto_variante": "negro"}
        servicio = _servicio(conversaciones=[_conversacion()], leads={1: lead})
        detalle = servicio.obtener_detalle(1)
        assert detalle.lead.producto_variante == "negro"


class TestOrigenYAnuncioEnElDetalle:
    LLEGADA = {
        "id_anuncio": "123", "titulo": "Audífonos Pro", "texto": "Cancelación de ruido", "url_anuncio": "https://fb.me/x",
        "tipo_origen": "ad", "tipo_media": "image", "imagen_url": "https://cdn.fb/x.jpg", "miniatura_url": None,
    }

    def test_cliente_directo_no_tiene_anuncio_ni_ventana_gratuita(self):
        detalle = _servicio(conversaciones=[_conversacion()]).obtener_detalle(1)

        assert detalle.conversacion.anuncio is None
        assert detalle.conversacion.llegadas_por_anuncio == []
        assert detalle.conversacion.ventana_gratuita.estado == "sin_anuncio"

    def test_cliente_de_anuncio_muestra_el_anuncio_su_producto_y_la_ventana_gratuita(self):
        ahora = datetime.now(timezone.utc)
        mensajes = {
            1: [
                {"id": 1, "rol": "cliente", "contenido": "hola", "tipo": "texto", "creado_en": ahora - timedelta(hours=1)},
                {"id": 2, "rol": "bot", "contenido": "¡Hola!", "tipo": "texto", "creado_en": ahora - timedelta(minutes=59)},
            ]
        }
        llegadas = {1: [{**self.LLEGADA, "creado_en": ahora - timedelta(hours=1)}]}
        vinculos = {"123": {"producto_sku": "AUD-1", "producto_nombre": "Audífonos Pro"}}
        servicio = _servicio(
            conversaciones=[_conversacion(origen="anuncio", id_anuncio="123")], mensajes=mensajes, llegadas=llegadas, vinculos=vinculos
        )

        c = servicio.obtener_detalle(1).conversacion

        assert c.anuncio.titulo == "Audífonos Pro"
        assert c.anuncio.url_anuncio == "https://fb.me/x"
        assert (c.anuncio.producto.sku, c.anuncio.producto.nombre) == ("AUD-1", "Audífonos Pro")
        assert c.anuncio.llegadas == 1
        assert c.ventana_gratuita.estado == "abierta"
        assert c.ventana_gratuita.expira_en is not None
        assert c.ventana_abierta is True  # el cliente escribió hace 1 h: la de servicio también está abierta

    def test_anuncio_sin_producto_vinculado_deja_el_producto_en_none(self):
        llegadas = {1: [{**self.LLEGADA, "creado_en": datetime.now(timezone.utc)}]}
        servicio = _servicio(conversaciones=[_conversacion(origen="anuncio", id_anuncio="123")], llegadas=llegadas)

        assert servicio.obtener_detalle(1).conversacion.anuncio.producto is None

    def test_el_historial_de_llegadas_va_de_la_mas_reciente_a_la_mas_antigua(self):
        ahora = datetime.now(timezone.utc)
        llegadas = {
            1: [
                {**self.LLEGADA, "id_anuncio": "viejo", "creado_en": ahora - timedelta(days=30)},
                {**self.LLEGADA, "id_anuncio": "nuevo", "creado_en": ahora},
            ]
        }
        servicio = _servicio(conversaciones=[_conversacion(origen="fep", id_anuncio="nuevo")], llegadas=llegadas)

        c = servicio.obtener_detalle(1).conversacion

        assert [l.id_anuncio for l in c.llegadas_por_anuncio] == ["nuevo", "viejo"]
        assert c.anuncio.id_anuncio == "nuevo"
        assert c.anuncio.llegadas == 2


class TestListarConversaciones:
    def test_sin_revisar_y_totales_por_filtro_rapido(self):
        conversaciones = [
            _conversacion(id=1, estado="escalada", vista_en=None),
            _conversacion(id=2, telefono="593900000002", estado="escalada", vista_en=AHORA),
            _conversacion(id=3, telefono="593900000003", estado="esperando_pago"),
            _conversacion(id=4, telefono="593900000004", estado="activa"),
        ]
        servicio = _servicio(conversaciones=conversaciones)

        resultado = servicio.listar_conversaciones()

        por_id = {item.id: item for item in resultado.items}
        assert por_id[1].sin_revisar is True
        assert por_id[2].sin_revisar is False
        assert resultado.totales_por_filtro_rapido.escaladas == 2
        assert resultado.totales_por_filtro_rapido.escaladas_sin_revisar == 1
        assert resultado.totales_por_filtro_rapido.esperando_pago == 1


class TestNotasInternas:
    def test_guarda_y_borra_la_nota(self):
        servicio = _servicio(conversaciones=[_conversacion(notas_internas=None)])

        servicio.actualizar_notas(1, "Cliente prefiere trato directo.")
        assert servicio._conversaciones.obtener_por_id(1)["notas_internas"] == "Cliente prefiere trato directo."

        servicio.actualizar_notas(1, None)
        assert servicio._conversaciones.obtener_por_id(1)["notas_internas"] is None

    def test_conversacion_inexistente_lanza_error(self):
        servicio = _servicio(conversaciones=[])
        with pytest.raises(ConversacionNoEncontradaError):
            servicio.actualizar_notas(999, "nota")


class TestReactivar:
    def test_reactiva_una_conversacion_escalada(self):
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada")])
        servicio.reactivar(1)
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "activa"

    def test_conversacion_inexistente_lanza_error(self):
        servicio = _servicio(conversaciones=[])
        with pytest.raises(ConversacionNoEncontradaError):
            servicio.reactivar(999)


def _con_ventana_abierta(estado):
    mensajes = {1: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=2)}]}
    return _servicio(conversaciones=[_conversacion(estado=estado)], mensajes=mensajes, whatsapp=MagicMock())


class TestTomarLaConversacion:
    """El dueño saca a Victoria de la conversación: con el botón, o solo por escribirle al cliente desde el panel."""

    def test_tomar_pasa_la_conversacion_a_manual_y_la_marca_vista(self):
        servicio = _servicio(conversaciones=[_conversacion(estado="activa")])
        servicio.tomar(1)
        fila = servicio._conversaciones.obtener_por_id(1)
        assert fila["estado"] == "manual"
        assert fila["vista_en"] is not None

    def test_tomar_una_inexistente_lanza_error(self):
        with pytest.raises(ConversacionNoEncontradaError):
            _servicio(conversaciones=[]).tomar(999)

    def test_devolver_a_victoria_regresa_una_manual_a_activa(self):
        servicio = _servicio(conversaciones=[_conversacion(estado="manual")])
        servicio.reactivar(1)
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "activa"

    def test_escribirle_al_cliente_desde_el_panel_toma_la_conversacion(self):
        servicio = _con_ventana_abierta("activa")
        servicio.enviar_mensaje_manual(1, "Hola, soy Freddy")
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "manual"

    def test_escribir_estando_esperando_pago_tambien_la_toma(self):
        servicio = _con_ventana_abierta("esperando_pago")
        servicio.enviar_mensaje_manual(1, "Ya te confirmo el pago")
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "manual"

    def test_si_ya_estaba_escalada_o_en_gestion_no_cambia_de_estado(self):
        for estado in ("escalada", "en_gestion"):
            servicio = _con_ventana_abierta(estado)
            servicio.enviar_mensaje_manual(1, "Hola")
            assert servicio._conversaciones.obtener_por_id(1)["estado"] == estado

    def test_si_la_ventana_esta_cerrada_no_se_toma_la_conversacion(self):
        vieja = AHORA - timedelta(hours=30)
        servicio = _servicio(conversaciones=[_conversacion(estado="activa", actualizada_en=vieja)], mensajes={1: [
            {"id": 1, "conversacion_id": 1, "rol": "cliente", "contenido": "hola", "tipo": "texto", "wamid": "w", "creado_en": vieja}]})
        with pytest.raises(VentanaMensajeriaCerradaError):
            servicio.enviar_mensaje_manual(1, "hola")
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "activa"


def _transferencia(estado_pago="pendiente", metodo_pago="transferencia"):
    return {1: {"id": 77, "metodo_pago": metodo_pago, "estado_pago": estado_pago}}


def _ventana_abierta():
    return {1: [{"id": 1, "rol": "cliente", "contenido": "ya transferí", "creado_en": AHORA - timedelta(hours=2)}]}


class TestContinuarLaVenta:
    """«Confirmar pago» y «Que Victoria continúe»: el dueño le devuelve la conversación a Victoria para que cierre la venta."""

    def test_confirmar_el_pago_lo_marca_deja_un_aviso_reactiva_y_encola_a_victoria(self):
        worker = MagicMock()
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada")], leads=_transferencia(), mensajes=_ventana_abierta(), bot_worker=worker)

        resultado = servicio.continuar_venta(1, pago_confirmado=True)

        assert resultado == {"victoriaContinua": True}
        assert servicio._leads.pagos_confirmados == [77]
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "activa"
        aviso = servicio._mensajes.obtener_por_conversacion(1)[-1]
        assert aviso["rol"] == "sistema" and "CONFIRMÓ" in aviso["contenido"] and "cerrar_venta" in aviso["contenido"]
        worker.encolar.assert_called_once_with(conversacion_id=1, canal="whatsapp", id_externo="593987654321")

    def test_nada_se_le_manda_al_cliente_desde_aqui(self):
        whatsapp = MagicMock()
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada")], leads=_transferencia(), mensajes=_ventana_abierta(), whatsapp=whatsapp, bot_worker=MagicMock())
        servicio.continuar_venta(1, pago_confirmado=True)
        whatsapp.enviar_texto.assert_not_called()

    def test_con_la_ventana_cerrada_queda_todo_listo_pero_no_se_encola(self):
        worker = MagicMock()
        servicio = _servicio(conversaciones=[_conversacion(estado="escalada")], leads=_transferencia(), bot_worker=worker)

        resultado = servicio.continuar_venta(1, pago_confirmado=True)

        assert resultado == {"victoriaContinua": False}
        assert servicio._leads.pagos_confirmados == [77]
        assert servicio._conversaciones.obtener_por_id(1)["estado"] == "activa"
        worker.encolar.assert_not_called()

    def test_no_se_puede_confirmar_un_pago_que_no_es_transferencia(self):
        servicio = _servicio(conversaciones=[_conversacion()], leads=_transferencia(metodo_pago="contraentrega"), mensajes=_ventana_abierta(), bot_worker=MagicMock())
        with pytest.raises(SinPedidoEnCursoError):
            servicio.continuar_venta(1, pago_confirmado=True)
        assert servicio._leads.pagos_confirmados == []

    def test_no_se_puede_confirmar_un_pago_sin_pedido(self):
        servicio = _servicio(conversaciones=[_conversacion()], mensajes=_ventana_abierta(), bot_worker=MagicMock())
        with pytest.raises(SinPedidoEnCursoError):
            servicio.continuar_venta(1, pago_confirmado=True)

    def test_continuar_sin_confirmar_pago_tambien_sirve_y_lleva_la_nota_del_dueno(self):
        worker = MagicMock()
        servicio = _servicio(conversaciones=[_conversacion(estado="manual")], mensajes=_ventana_abierta(), bot_worker=worker)

        servicio.continuar_venta(1, nota="  pídele el número de cédula  ")

        aviso = servicio._mensajes.obtener_por_conversacion(1)[-1]["contenido"]
        assert "te devuelve esta conversación" in aviso and "Indicación del dueño para ti: pídele el número de cédula" in aviso
        assert servicio._leads.pagos_confirmados == []
        worker.encolar.assert_called_once()

    def test_conversacion_inexistente(self):
        with pytest.raises(ConversacionNoEncontradaError):
            _servicio(conversaciones=[]).continuar_venta(5)


class TestArchivosDeLosMensajes:
    """El panel puede ver la foto o escuchar el audio del cliente (el servidor lo trae de Meta al momento)."""

    def _con_foto(self, whatsapp):
        mensajes = {1: [
            {"id": 10, "conversacion_id": 1, "rol": "cliente", "contenido": "[imagen]", "tipo": "imagen", "wamid": "w1", "creado_en": AHORA,
             "media_id": "M1", "media_mime": "image/jpeg", "analisis": "Comprobante de pago: $24.99"},
            {"id": 11, "conversacion_id": 1, "rol": "cliente", "contenido": "hola", "tipo": "texto", "wamid": "w2", "creado_en": AHORA},
            {"id": 12, "conversacion_id": 2, "rol": "cliente", "contenido": "[imagen]", "tipo": "imagen", "wamid": "w3", "creado_en": AHORA, "media_id": "M9"},
        ]}
        return _servicio(conversaciones=[_conversacion(id=1), _conversacion(id=2, telefono="593911111111")], mensajes=mensajes, whatsapp=whatsapp)

    def test_el_detalle_dice_que_mensajes_traen_archivo_y_lo_que_se_entendio(self):
        detalle = self._con_foto(MagicMock()).obtener_detalle(1)
        foto, texto = detalle.mensajes[0], detalle.mensajes[1]
        assert foto.tiene_archivo is True and foto.analisis == "Comprobante de pago: $24.99"
        assert texto.tiene_archivo is False and texto.analisis is None

    def test_trae_el_archivo_de_meta(self):
        whatsapp = MagicMock()
        whatsapp.descargar_media.return_value = (b"JPG", "image/jpeg")
        datos, mime = self._con_foto(whatsapp).obtener_archivo(1, 10)
        assert (datos, mime) == (b"JPG", "image/jpeg")
        assert whatsapp.descargar_media.call_args.args[0] == "M1"

    def test_un_mensaje_de_texto_no_tiene_archivo(self):
        with pytest.raises(ArchivoNoDisponibleError):
            self._con_foto(MagicMock()).obtener_archivo(1, 11)

    def test_no_se_puede_pedir_el_archivo_de_otra_conversacion(self):
        with pytest.raises(ArchivoNoDisponibleError):
            self._con_foto(MagicMock()).obtener_archivo(1, 12)

    def test_si_la_conversacion_no_existe(self):
        with pytest.raises(ConversacionNoEncontradaError):
            self._con_foto(MagicMock()).obtener_archivo(99, 10)

    def test_si_meta_ya_no_lo_entrega_es_un_error_claro(self):
        whatsapp = MagicMock()
        whatsapp.descargar_media.side_effect = RuntimeError("404")
        with pytest.raises(ArchivoNoDisponibleError, match="ya no entrega"):
            self._con_foto(whatsapp).obtener_archivo(1, 10)
