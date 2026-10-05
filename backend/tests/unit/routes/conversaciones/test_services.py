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
from src.routes.conversaciones.services import ConversacionesService

AHORA = datetime.now(timezone.utc)


class FakeConversacionRepository:
    def __init__(self, conversaciones=None):
        self.tabla = {c["id"]: dict(c) for c in (conversaciones or [])}

    def obtener_por_id(self, conversacion_id):
        fila = self.tabla.get(conversacion_id)
        return dict(fila) if fila else None

    def listar(self, estado=None, origen=None, q=None, page=1, page_size=20):
        filas = list(self.tabla.values())
        if estado:
            filas = [f for f in filas if f["estado"] == estado]
        if origen:
            filas = [f for f in filas if f["origen"] == origen]
        if q:
            filas = [f for f in filas if q in f["telefono"] or q.lower() in (f.get("nombre_cliente") or "").lower()]
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
    id=1, telefono="593987654321", origen="directo", estado="activa", fep_expira_en=None, vista_en=None,
    notas_internas=None, id_anuncio=None, creada_en=None, actualizada_en=None,
):
    return {
        "id": id,
        "telefono": telefono,
        "origen": origen,
        "estado": estado,
        "fep_expira_en": fep_expira_en,
        "id_anuncio": id_anuncio,
        "vista_en": vista_en,
        "notas_internas": notas_internas,
        "creada_en": creada_en or AHORA,
        "actualizada_en": actualizada_en or AHORA,
    }


def _servicio(conversaciones=None, leads=None, mensajes=None, whatsapp=None):
    return ConversacionesService(
        whatsapp_client=whatsapp or MagicMock(),
        conversacion_repo=FakeConversacionRepository(conversaciones=conversaciones or []),
        lead_repo=FakeLeadRepository(leads_por_conversacion=leads or {}),
        mensaje_repo=FakeMensajeRepository(mensajes_por_conversacion=mensajes or {}),
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

    def test_ventana_abierta_solo_por_fep_fuera_de_24h_de_servicio(self):
        mensajes = {1: [{"id": 1, "rol": "cliente", "contenido": "hola", "creado_en": AHORA - timedelta(hours=30)}]}
        conv = _conversacion(origen="fep", fep_expira_en=AHORA + timedelta(hours=10))
        whatsapp = MagicMock()
        servicio = _servicio(conversaciones=[conv], mensajes=mensajes, whatsapp=whatsapp)

        servicio.enviar_mensaje_manual(1, "hola de nuevo")

        whatsapp.enviar_texto.assert_called_once()

    def test_ventana_cerrada_no_llama_whatsapp_ni_inserta_mensaje(self):
        whatsapp = MagicMock()
        mensaje_repo = FakeMensajeRepository()
        servicio = ConversacionesService(
            whatsapp_client=whatsapp,
            conversacion_repo=FakeConversacionRepository(conversaciones=[_conversacion(origen="directo")]),
            lead_repo=FakeLeadRepository(),
            mensaje_repo=mensaje_repo,
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
            whatsapp_client=whatsapp,
            conversacion_repo=FakeConversacionRepository(conversaciones=[_conversacion()]),
            lead_repo=FakeLeadRepository(),
            mensaje_repo=mensaje_repo,
        )

        with pytest.raises(EnvioWhatsAppFallidoError):
            servicio.enviar_mensaje_manual(1, "hola")

        guardados = mensaje_repo.obtener_por_conversacion(1)
        assert any(m["rol"] == "humano" and m["contenido"] == "hola" for m in guardados)


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
