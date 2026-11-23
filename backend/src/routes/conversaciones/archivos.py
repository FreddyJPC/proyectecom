"""
Archivos que el dueño le manda al cliente desde el panel (pedido de Freddy, 2026-11-23): fotos, videos y documentos (un catálogo
en PDF, una hoja de Excel…).

El tipo se decide por el CONTENIDO del archivo (sus primeros bytes), no por lo que diga el navegador ni el nombre: así nadie puede
colar un archivo de otro tipo con un nombre cambiado. Los límites son los de WhatsApp, salvo el de documentos, que se deja en
16 MB para no cargar archivos enormes en la memoria del servidor.
"""
import re
from dataclasses import dataclass
from typing import Optional

MB = 1024 * 1024
MAXIMO_BYTES_ARCHIVO = 16 * MB  # el más grande de todos: lo que se lee como mucho de la petición

# tipo de mensaje de WhatsApp -> (tipo guardado en `mensajes.tipo`, límite en bytes)
TIPOS = {
    "image": ("imagen", 5 * MB),
    "video": ("video", 16 * MB),
    "document": ("documento", 16 * MB),
}

_OFFICE_ZIP = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_OFFICE_VIEJO = {
    "doc": "application/msword",
    "xls": "application/vnd.ms-excel",
    "ppt": "application/vnd.ms-powerpoint",
}

PERMITIDOS = "fotos JPG o PNG, PDF, Word, Excel, PowerPoint o videos MP4"


class ArchivoInvalidoError(ValueError):
    """El archivo no es de un tipo que se pueda enviar por WhatsApp, o pesa más de lo permitido."""


@dataclass(frozen=True)
class ArchivoParaEnviar:
    tipo_whatsapp: str  # image | video | document
    tipo_mensaje: str  # imagen | video | documento
    mime: str
    nombre: str  # nombre con el que lo ve el cliente (en documentos)


def _extension(nombre: Optional[str]) -> str:
    partes = (nombre or "").rsplit(".", 1)
    return partes[1].lower().strip() if len(partes) == 2 else ""


def nombre_seguro(nombre: Optional[str], extension: str) -> str:
    """Solo el nombre (sin carpetas), sin caracteres raros, de hasta 80 letras y con la extensión correcta."""
    base = re.split(r"[\\/]", nombre or "")[-1]
    base = base.rsplit(".", 1)[0] if "." in base else base
    base = re.sub(r"[^\w\-. ()áéíóúÁÉÍÓÚñÑ]", "_", base).strip(" ._") or "archivo"
    return f"{base[:80]}.{extension}"


def clasificar(datos: bytes, nombre: Optional[str]) -> ArchivoParaEnviar:
    """Qué es el archivo y cómo se manda por WhatsApp. Lanza ArchivoInvalidoError si no se puede enviar."""
    if not datos:
        raise ArchivoInvalidoError("El archivo está vacío.")
    ext = _extension(nombre)

    if datos[:3] == b"\xff\xd8\xff":
        tipo, mime, ext = "image", "image/jpeg", "jpg"
    elif datos[:8] == b"\x89PNG\r\n\x1a\n":
        tipo, mime, ext = "image", "image/png", "png"
    elif datos[:5] == b"%PDF-":
        tipo, mime, ext = "document", "application/pdf", "pdf"
    elif datos[4:8] == b"ftyp":
        marca = datos[8:12]
        if marca.startswith(b"qt"):
            raise ArchivoInvalidoError("Los videos .MOV (iPhone) no los acepta WhatsApp: envíalo como MP4.")
        if marca.startswith(b"3g"):
            tipo, mime, ext = "video", "video/3gpp", "3gp"
        else:
            tipo, mime, ext = "video", "video/mp4", "mp4"
    elif datos[:4] == b"PK\x03\x04" and ext in _OFFICE_ZIP:
        tipo, mime = "document", _OFFICE_ZIP[ext]
    elif datos[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" and ext in _OFFICE_VIEJO:
        tipo, mime = "document", _OFFICE_VIEJO[ext]
    else:
        raise ArchivoInvalidoError(f"Ese tipo de archivo no se puede enviar. Se aceptan {PERMITIDOS}.")

    tipo_mensaje, limite = TIPOS[tipo]
    if len(datos) > limite:
        raise ArchivoInvalidoError(f"El archivo pesa más de {limite // MB} MB: WhatsApp no lo acepta.")
    return ArchivoParaEnviar(tipo, tipo_mensaje, mime, nombre_seguro(nombre, ext))
