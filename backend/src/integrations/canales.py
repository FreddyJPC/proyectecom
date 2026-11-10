"""
Canales de mensajería (ADR-014): POR DÓNDE habla un cliente con el negocio.

Para qué existe: el negocio quiere vender por WhatsApp, Instagram y Messenger. Cada canal tiene su propia API para enviar
mensajes y su propio identificador de cliente (un teléfono en WhatsApp; un identificador de Meta en Instagram y Messenger).
El resto del sistema (el bot, el panel de conversaciones, la cola de respuestas) no debe saber de esas diferencias: pide
«enviar este texto a este cliente por este canal» y este módulo lo encamina.

No confundir con el ORIGEN (`anuncio` | `directo` | …): el origen es CÓMO llegó el cliente; el canal es POR DÓNDE conversa.

Hoy solo WhatsApp está conectado. Instagram y Messenger ya existen como valores válidos en la base, pero pedir su canal lanza
`CanalNoDisponibleError` (un mensaje claro, no un fallo misterioso) hasta que se construya e inscriba su adaptador:
bastará con una clase nueva con los mismos métodos y registrarla en `get_registro_canales()`.
"""
from functools import lru_cache
from typing import Dict, Optional

from .whatsapp import WhatsAppClient, get_whatsapp_client

CANAL_WHATSAPP = "whatsapp"
CANAL_INSTAGRAM = "instagram"
CANAL_MESSENGER = "messenger"
CANALES = (CANAL_WHATSAPP, CANAL_INSTAGRAM, CANAL_MESSENGER)

NOMBRES_DE_CANAL = {CANAL_WHATSAPP: "WhatsApp", CANAL_INSTAGRAM: "Instagram", CANAL_MESSENGER: "Messenger"}


class CanalNoDisponibleError(Exception):
    """El canal es válido pero todavía no está conectado a este sistema."""


def nombre_de_canal(canal: Optional[str]) -> str:
    return NOMBRES_DE_CANAL.get(canal or CANAL_WHATSAPP, canal or "WhatsApp")


def etiqueta_de_cliente(canal: Optional[str], id_externo: Optional[str], telefono: Optional[str] = None) -> str:
    """Cómo nombrar a un cliente en un aviso: «WhatsApp · 593987654321». En WhatsApp el identificador ES el teléfono; en
    otros canales se usa el teléfono si ya se conoce y, si no, el identificador del canal."""
    return f"{nombre_de_canal(canal)} · {telefono or id_externo or '—'}"


class CanalWhatsApp:
    """Adaptador de WhatsApp: el `id_externo` de un cliente de WhatsApp es su número de teléfono."""

    nombre = CANAL_WHATSAPP

    def __init__(self, cliente: WhatsAppClient):
        self._cliente = cliente

    def enviar_texto(self, id_externo: str, mensaje: str) -> dict:
        return self._cliente.enviar_texto(telefono=id_externo, mensaje=mensaje)

    def enviar_imagen(self, id_externo: str, url: str, descripcion: Optional[str] = None) -> dict:
        return self._cliente.enviar_imagen(telefono=id_externo, url=url, descripcion=descripcion)

    def descargar_media(self, media_id: str, max_bytes: int = 8 * 1024 * 1024):
        """Baja una foto, audio o documento que mandó el cliente. Devuelve (bytes, tipo_mime)."""
        return self._cliente.descargar_media(media_id, max_bytes=max_bytes)

    def enviar_plantilla(self, id_externo: str, nombre_plantilla: str, variables: Optional[list] = None, idioma: str = "es") -> dict:
        """Mensaje de plantilla aprobada por Meta: lo único que se puede enviar fuera de las 24 h. Solo WhatsApp lo tiene:
        un canal sin este método no puede recibir seguimientos automáticos."""
        return self._cliente.enviar_plantilla(
            telefono=id_externo, nombre_plantilla=nombre_plantilla, variables=variables, idioma=idioma
        )


class RegistroCanales:
    """Los canales conectados, por nombre. `para(canal)` devuelve el adaptador o lanza `CanalNoDisponibleError`."""

    def __init__(self, canales: Dict[str, object]):
        self._canales = dict(canales)

    def para(self, canal: Optional[str]):
        nombre = canal or CANAL_WHATSAPP
        adaptador = self._canales.get(nombre)
        if adaptador is None:
            raise CanalNoDisponibleError(
                f"El canal «{nombre_de_canal(nombre)}» todavía no está conectado: no se puede enviar por él."
            )
        return adaptador

    def conectados(self):
        return tuple(self._canales)

    def con_plantillas(self):
        """Los canales conectados que saben enviar plantillas (hoy, WhatsApp): los únicos a los que el seguimiento automático
        puede escribirle fuera de las 24 h."""
        return tuple(nombre for nombre, adaptador in self._canales.items() if hasattr(adaptador, "enviar_plantilla"))


@lru_cache(maxsize=1)
def get_registro_canales() -> RegistroCanales:
    """Registro singleton por proceso (mismo motivo que get_whatsapp_client())."""
    return RegistroCanales({CANAL_WHATSAPP: CanalWhatsApp(get_whatsapp_client())})
