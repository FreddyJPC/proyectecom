"""
Servicio del módulo de Conversaciones (dashboard). Reutiliza los
repositorios de src/routes/whatsapp/repository.py -- son las mismas
tablas (conversaciones, mensajes, leads) que ya administra el canal del
bot, así que no se duplica el acceso a datos en un repository.py propio
de este módulo (solo se le agregaron ahí los métodos nuevos que este
módulo necesita: listar/contar para el dashboard, marcar_vista,
actualizar_notas, marcar_esperando_pago).
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from src.integrations.whatsapp import WhatsAppBusinessError, WhatsAppClient, WhatsAppRequestError, get_whatsapp_client
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository

from .dto import (
    ConversacionDetalleDTO,
    ConversacionResumenDTO,
    DetalleCompletoDTO,
    LeadDTO,
    ListaConversacionesDTO,
    MensajeDTO,
    TotalesPorFiltroRapidoDTO,
    UltimoMensajeDTO,
)
from .exceptions import ConversacionNoEncontradaError, EnvioWhatsAppFallidoError, VentanaMensajeriaCerradaError

VENTANA_SERVICIO_HORAS = 24


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


class ConversacionesService:
    def __init__(
        self,
        whatsapp_client: Optional[WhatsAppClient] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        lead_repo: Optional[LeadRepository] = None,
        mensaje_repo: Optional[MensajeRepository] = None,
    ):
        self._whatsapp = whatsapp_client or get_whatsapp_client()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._leads = lead_repo or LeadRepository()
        self._mensajes = mensaje_repo or MensajeRepository()

    def _ventana_abierta(self, conversacion: dict) -> Tuple[bool, Optional[datetime]]:
        """
        ventana_servicio_abierta = existe algún mensaje con rol='cliente' y
            (now() - ese último mensaje.creado_en) < 24 horas
        ventana_fep_abierta = origen == 'fep' AND fep_expira_en is not None
            AND now() < fep_expira_en
        ventana_abierta = servicio OR fep

        Devuelve también CUÁNDO se cierra: la más próxima entre las que
        siguen abiertas (no las que ya cerraron), para que el frontend
        pueda mostrar "se cierra en X horas".
        """
        ahora = datetime.now(timezone.utc)

        cierre_servicio = None
        mensajes_cliente = [m for m in self._mensajes.obtener_por_conversacion(conversacion["id"]) if m["rol"] == "cliente"]
        if mensajes_cliente:
            cierre_servicio = mensajes_cliente[-1]["creado_en"] + timedelta(hours=VENTANA_SERVICIO_HORAS)

        cierre_fep = None
        if conversacion.get("origen") == "fep" and conversacion.get("fep_expira_en") is not None:
            cierre_fep = conversacion["fep_expira_en"]

        vigentes = [c for c in (cierre_servicio, cierre_fep) if c is not None and c > ahora]
        if not vigentes:
            return False, None
        return True, min(vigentes)

    def listar_conversaciones(
        self,
        estado: Optional[str] = None,
        origen: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> ListaConversacionesDTO:
        resultado = self._conversaciones.listar(estado=estado, origen=origen, q=q, page=page, page_size=page_size)

        items = []
        for fila in resultado["items"]:
            ultimo_mensaje = None
            if fila.get("ultimo_mensaje_contenido") is not None:
                ultimo_mensaje = UltimoMensajeDTO(
                    rol=fila["ultimo_mensaje_rol"],
                    contenido=fila["ultimo_mensaje_contenido"],
                    creado_en=_iso(fila["ultimo_mensaje_creado_en"]),
                )
            items.append(
                ConversacionResumenDTO(
                    id=fila["id"],
                    telefono=fila["telefono"],
                    nombre_cliente=fila.get("nombre_cliente"),
                    origen=fila["origen"],
                    estado=fila["estado"],
                    producto_interes=fila.get("producto_nombre"),
                    sin_revisar=(fila["estado"] == "escalada" and fila.get("vista_en") is None),
                    ultimo_mensaje=ultimo_mensaje,
                    creada_en=_iso(fila["creada_en"]),
                    actualizada_en=_iso(fila["actualizada_en"]),
                )
            )

        totales = self._conversaciones.contar_por_filtro_rapido()
        return ListaConversacionesDTO(
            items=items,
            total=resultado["total"],
            page=resultado["page"],
            page_size=resultado["page_size"],
            totales_por_filtro_rapido=TotalesPorFiltroRapidoDTO(
                escaladas=totales["escaladas"],
                escaladas_sin_revisar=totales["escaladas_sin_revisar"],
                esperando_pago=totales["esperando_pago"],
            ),
        )

    def obtener_detalle(self, conversacion_id: int) -> DetalleCompletoDTO:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")

        if conversacion["estado"] == "escalada" and conversacion.get("vista_en") is None:
            self._conversaciones.marcar_vista(conversacion_id)
            conversacion["vista_en"] = datetime.now(timezone.utc)

        abierta, expira_en = self._ventana_abierta(conversacion)

        lead_row = self._leads.obtener_por_conversacion(conversacion_id)
        lead_dto = None
        if lead_row is not None:
            lead_dto = LeadDTO(
                nombre_cliente=lead_row.get("nombre_cliente"),
                direccion=lead_row.get("direccion"),
                canton=lead_row.get("canton"),
                provincia=lead_row.get("provincia"),
                producto_sku=lead_row.get("producto_sku"),
                producto_nombre=lead_row.get("producto_nombre"),
                producto_variante=lead_row.get("producto_variante"),
                total=lead_row.get("total"),
                metodo_pago=lead_row.get("metodo_pago"),
                estado_pago=lead_row.get("estado_pago"),
                estado=lead_row.get("estado"),
                id_pedido_local=lead_row.get("id_pedido_local"),
                id_pedido_rocketfy=lead_row.get("id_pedido_rocketfy"),
            )

        mensajes = [
            MensajeDTO(id=m["id"], rol=m["rol"], contenido=m["contenido"], tipo=m["tipo"], creado_en=_iso(m["creado_en"]))
            for m in self._mensajes.obtener_por_conversacion(conversacion_id)
        ]

        conversacion_dto = ConversacionDetalleDTO(
            id=conversacion["id"],
            telefono=conversacion["telefono"],
            origen=conversacion["origen"],
            estado=conversacion["estado"],
            id_anuncio=conversacion.get("id_anuncio"),
            notas_internas=conversacion.get("notas_internas"),
            ventana_abierta=abierta,
            ventana_expira_en=_iso(expira_en),
            creada_en=_iso(conversacion["creada_en"]),
            actualizada_en=_iso(conversacion["actualizada_en"]),
        )

        return DetalleCompletoDTO(conversacion=conversacion_dto, lead=lead_dto, mensajes=mensajes)

    def enviar_mensaje_manual(self, conversacion_id: int, contenido: str) -> MensajeDTO:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")

        abierta, _ = self._ventana_abierta(conversacion)
        if not abierta:
            raise VentanaMensajeriaCerradaError(
                "La ventana de mensajería de 24 horas está cerrada y esta conversación no tiene una ventana "
                "FEP activa. No se puede enviar texto libre — solo una plantilla aprobada, que todavía no "
                "está disponible desde este panel."
            )

        mensaje = self._mensajes.crear(
            conversacion_id=conversacion_id, rol="humano", contenido=contenido, tipo="texto", wamid=None
        )

        try:
            self._whatsapp.enviar_texto(telefono=conversacion["telefono"], mensaje=contenido)
        except (WhatsAppRequestError, WhatsAppBusinessError) as exc:
            # El mensaje YA quedó guardado arriba -- el dueño necesita
            # saber que probablemente no llegó, no que se pierda en
            # silencio.
            raise EnvioWhatsAppFallidoError(str(exc)) from exc

        self._conversaciones.actualizar_timestamp(conversacion_id)
        return MensajeDTO(
            id=mensaje["id"], rol=mensaje["rol"], contenido=mensaje["contenido"], tipo=mensaje["tipo"],
            creado_en=_iso(mensaje["creado_en"]),
        )

    def reactivar(self, conversacion_id: int) -> None:
        if self._conversaciones.obtener_por_id(conversacion_id) is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")
        # Nota (ya conocida): si el lead está despachado, la próxima
        # escritura del cliente lo vuelve a escalar automáticamente por la
        # regla determinista de postventa -- no es un bug.
        self._conversaciones.actualizar_estado(conversacion_id, "activa")

    def actualizar_notas(self, conversacion_id: int, notas_internas: Optional[str]) -> None:
        if self._conversaciones.obtener_por_id(conversacion_id) is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")
        self._conversaciones.actualizar_notas(conversacion_id, notas_internas)
