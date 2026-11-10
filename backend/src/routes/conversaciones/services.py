"""
Servicio del módulo de Conversaciones (dashboard). Reutiliza los
repositorios de src/routes/whatsapp/repository.py -- son las mismas
tablas (conversaciones, mensajes, leads) que ya administra el canal del
bot, así que no se duplica el acceso a datos en un repository.py propio
de este módulo (solo se le agregaron ahí los métodos nuevos que este
módulo necesita: listar/contar para el dashboard, marcar_vista,
actualizar_notas, marcar_esperando_pago).
"""
from datetime import datetime, timezone
from typing import Optional, Tuple

from src.integrations.canales import CanalNoDisponibleError, RegistroCanales, get_registro_canales
from src.integrations.whatsapp import WhatsAppBusinessError, WhatsAppRequestError
from src.routes.anuncios.servicio import AnuncioServicio
from src.routes.gestion.tipos import ESTADOS_EN_MANOS_DEL_DUENO as ESTADOS_QUE_ESPERAN_AL_DUENO
from src.routes.whatsapp.repository import ConversacionRepository, LeadRepository, MensajeRepository

from .dto import (
    AnuncioDTO,
    ConversacionDetalleDTO,
    ConversacionResumenDTO,
    DetalleCompletoDTO,
    LeadDTO,
    LlegadaPorAnuncioDTO,
    ListaConversacionesDTO,
    MensajeDTO,
    ProductoDeAnuncioDTO,
    TotalesPorFiltroRapidoDTO,
    UltimoMensajeDTO,
    VentanaGratuitaDTO,
)
from .exceptions import ArchivoNoDisponibleError, ConversacionNoEncontradaError, EnvioWhatsAppFallidoError, VentanaMensajeriaCerradaError

# Cuántas llegadas por anuncio se listan en la pantalla de una conversación (la más reciente primero).
MAXIMO_LLEGADAS_LISTADAS = 20


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


class ConversacionesService:
    def __init__(
        self,
        canales: Optional[RegistroCanales] = None,
        conversacion_repo: Optional[ConversacionRepository] = None,
        lead_repo: Optional[LeadRepository] = None,
        mensaje_repo: Optional[MensajeRepository] = None,
        anuncio_servicio: Optional[AnuncioServicio] = None,
    ):
        self._anuncios = anuncio_servicio or AnuncioServicio()
        self._canales = canales or get_registro_canales()
        self._conversaciones = conversacion_repo or ConversacionRepository()
        self._leads = lead_repo or LeadRepository()
        self._mensajes = mensaje_repo or MensajeRepository()

    def _ventana_abierta(self, conversacion: dict) -> Tuple[bool, Optional[datetime]]:
        """Ventana de SERVICIO de WhatsApp: abierta mientras no hayan pasado 24 horas desde el último mensaje del
        cliente. Es la ÚNICA que permite mandar texto libre (fuera de ella, Meta solo acepta plantillas aprobadas).

        La ventana gratuita de los anuncios NO cuenta aquí: según la regla vigente de Meta es un beneficio de costo
        (los mensajes no se cobran), no un permiso para escribir texto libre después de las 24 horas. Antes se trataba
        como permiso («72 h de FEP»): esa era la regla anterior. Ver routes/anuncios/ventana.py.

        Devuelve también CUÁNDO se cierra, para que el frontend pueda mostrar «se cierra en X horas»."""
        mensajes = self._mensajes.obtener_por_conversacion(conversacion["id"])
        return self._anuncios.ventana_de_servicio(mensajes, datetime.now(timezone.utc))

    def listar_conversaciones(
        self,
        estado: Optional[str] = None,
        origen: Optional[str] = None,
        q: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        canal: Optional[str] = None,
    ) -> ListaConversacionesDTO:
        resultado = self._conversaciones.listar(
            estado=estado, origen=origen, q=q, page=page, page_size=page_size, canal=canal
        )

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
                    canal=fila.get("canal") or "whatsapp",
                    id_externo=fila.get("id_externo"),
                    telefono=fila.get("telefono"),
                    nombre=fila.get("contacto_nombre") or fila.get("nombre_perfil"),
                    nombre_cliente=fila.get("nombre_cliente"),
                    origen=fila["origen"],
                    estado=fila["estado"],
                    producto_interes=fila.get("producto_nombre"),
                    sin_revisar=(fila["estado"] in ESTADOS_QUE_ESPERAN_AL_DUENO and fila.get("vista_en") is None),
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
                en_gestion=totales.get("en_gestion", 0),
            ),
        )

    def obtener_detalle(self, conversacion_id: int) -> DetalleCompletoDTO:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")

        if conversacion["estado"] in ESTADOS_QUE_ESPERAN_AL_DUENO and conversacion.get("vista_en") is None:
            self._conversaciones.marcar_vista(conversacion_id)
            conversacion["vista_en"] = datetime.now(timezone.utc)

        mensajes_crudos = self._mensajes.obtener_por_conversacion(conversacion_id)
        abierta, expira_en = self._anuncios.ventana_de_servicio(mensajes_crudos, datetime.now(timezone.utc))
        origen = self._anuncios.origen_de_conversacion(conversacion, mensajes_crudos)

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
            MensajeDTO(
                id=m["id"], rol=m["rol"], contenido=m["contenido"], tipo=m["tipo"], creado_en=_iso(m["creado_en"]),
                tiene_archivo=bool(m.get("media_id")), analisis=m.get("analisis"),
            )
            for m in mensajes_crudos
        ]

        conversacion_dto = ConversacionDetalleDTO(
            id=conversacion["id"],
            contacto_id=conversacion["contacto_id"],
            canal=conversacion["canal"],
            id_externo=conversacion["id_externo"],
            telefono=conversacion.get("telefono"),
            nombre=conversacion.get("contacto_nombre") or conversacion.get("nombre_perfil"),
            origen=conversacion["origen"],
            estado=conversacion["estado"],
            id_anuncio=conversacion.get("id_anuncio"),
            notas_internas=conversacion.get("notas_internas"),
            ventana_abierta=abierta,
            ventana_expira_en=_iso(expira_en),
            creada_en=_iso(conversacion["creada_en"]),
            actualizada_en=_iso(conversacion["actualizada_en"]),
            ventana_gratuita=VentanaGratuitaDTO(
                estado=origen["ventana_gratuita"]["estado"],
                expira_en=_iso(origen["ventana_gratuita"]["expira_en"]),
                responder_antes_de=_iso(origen["ventana_gratuita"]["responder_antes_de"]),
            ),
            anuncio=self._anuncio_dto(origen),
            llegadas_por_anuncio=[
                LlegadaPorAnuncioDTO(id_anuncio=l.get("id_anuncio"), titulo=l.get("titulo"), creado_en=_iso(l["creado_en"]))
                for l in origen["llegadas"][:MAXIMO_LLEGADAS_LISTADAS]
            ],
        )

        return DetalleCompletoDTO(conversacion=conversacion_dto, lead=lead_dto, mensajes=mensajes)

    @staticmethod
    def _anuncio_dto(origen: dict) -> Optional[AnuncioDTO]:
        ultima = origen["ultima"]
        if ultima is None:
            return None
        producto = origen["producto"]
        return AnuncioDTO(
            id_anuncio=ultima.get("id_anuncio"),
            titulo=ultima.get("titulo"),
            texto=ultima.get("texto"),
            url_anuncio=ultima.get("url_anuncio"),
            tipo_origen=ultima.get("tipo_origen"),
            tipo_media=ultima.get("tipo_media"),
            imagen_url=ultima.get("imagen_url"),
            miniatura_url=ultima.get("miniatura_url"),
            producto=ProductoDeAnuncioDTO(sku=producto["producto_sku"], nombre=producto["producto_nombre"]) if producto else None,
            llegadas=len(origen["llegadas"]),
        )

    def enviar_mensaje_manual(self, conversacion_id: int, contenido: str) -> MensajeDTO:
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        if conversacion is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")

        abierta, _ = self._ventana_abierta(conversacion)
        if not abierta:
            raise VentanaMensajeriaCerradaError(
                "La ventana de mensajería de 24 horas está cerrada: solo se puede escribir texto libre dentro de las "
                "24 horas siguientes al último mensaje del cliente. Fuera de ella, Meta solo acepta plantillas "
                "aprobadas, que todavía no están disponibles desde este panel."
            )

        mensaje = self._mensajes.crear(
            conversacion_id=conversacion_id, rol="humano", contenido=contenido, tipo="texto", wamid=None
        )

        try:
            self._canales.para(conversacion["canal"]).enviar_texto(conversacion["id_externo"], contenido)
        except (WhatsAppRequestError, WhatsAppBusinessError, CanalNoDisponibleError) as exc:
            # El mensaje YA quedó guardado arriba -- el dueño necesita
            # saber que probablemente no llegó, no que se pierda en
            # silencio.
            raise EnvioWhatsAppFallidoError(str(exc)) from exc

        self._conversaciones.actualizar_timestamp(conversacion_id)
        return MensajeDTO(
            id=mensaje["id"], rol=mensaje["rol"], contenido=mensaje["contenido"], tipo=mensaje["tipo"],
            creado_en=_iso(mensaje["creado_en"]),
        )

    def obtener_archivo(self, conversacion_id: int, mensaje_id: int):
        """La foto, el audio o el PDF de un mensaje, traído de Meta en este momento (no se guarda en ningún otro lado; Meta lo
        conserva unos 30 días). Devuelve (bytes, tipo_mime). Solo si el mensaje es de ESA conversación y trae un archivo."""
        if self._conversaciones.obtener_por_id(conversacion_id) is None:
            raise ConversacionNoEncontradaError(f"No existe una conversación con id={conversacion_id}.")
        mensaje = self._mensajes.obtener_por_id(mensaje_id)
        if mensaje is None or mensaje["conversacion_id"] != conversacion_id or not mensaje.get("media_id"):
            raise ArchivoNoDisponibleError("Ese mensaje no tiene un archivo.")
        conversacion = self._conversaciones.obtener_por_id(conversacion_id)
        try:
            datos, mime = self._canales.para(conversacion["canal"]).descargar_media(mensaje["media_id"])
        except Exception as exc:
            # Lo más común: Meta ya no lo guarda (pasaron ~30 días) o el enlace venció.
            raise ArchivoNoDisponibleError(f"Meta ya no entrega este archivo ({exc}).") from exc
        return datos, (mensaje.get("media_mime") or mime or "application/octet-stream")

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
