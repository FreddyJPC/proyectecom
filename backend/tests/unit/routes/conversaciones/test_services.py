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

    def actualizar_timestamp(self, conversacion_id):
        self.tabla[conversacion_id]["actualizada_en"] = datetime.now(timezone.utc)


class FakeLeadRepository:
    def __init__(self, leads_por_conversacion=None):
        self._leads = leads_por_conversacion or {}

    def obtener_por_conversacion(self, conversacion_id):
        return self._leads.get(conversacion_id)


class FakeMensajeRepository:
    def __init__(self, mensajes_por_conversacion=None):
        self._mensajes = {k: list(v) for k, v in (mensajes_por_conversacion or {}).items()}
        self._siguiente_id = 1

    def obtener_por_conversacion(self, conversacion_id):
        return list(self._mensajes.get(conversacion_id, []))

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


def _servicio(conversaciones=None, leads=None, mensajes=None, whatsapp=None, llegadas=None, vinculos=None):
    return ConversacionesService(
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
