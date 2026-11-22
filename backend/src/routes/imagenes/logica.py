"""
Reglas de la galería de un producto (ADR-012): fotos Y videos, todo es «material del producto» (entrada 0.0.163). Lógica
PURA: se prueba sin base de datos.

Las fotos las sube la propia app al bucket público `productos` (con la sesión del dueño) y después le avisa al
servidor la ruta del archivo. El servidor NUNCA acepta una URL escrita por el cliente: la arma él mismo a partir
de la ruta, para que solo se puedan registrar archivos de ese bucket.

Cada producto tiene su carpeta en el bucket: `p<id>` (el id numérico, no el SKU: un SKU puede traer espacios o
símbolos que Storage no admite en una ruta).
"""
import re
from typing import Any, Dict, List
from urllib.parse import quote

BUCKET = "productos"
MAXIMO_POR_PRODUCTO = 12
EXTENSIONES_FOTO = ("jpg", "jpeg", "png")
# WhatsApp solo acepta video MP4 o 3GP (con video H.264 y audio AAC) y de hasta 16 MB. Un .mov del iPhone no sirve.
EXTENSIONES_VIDEO = ("mp4", "3gp")
EXTENSIONES = EXTENSIONES_FOTO + EXTENSIONES_VIDEO
TIPO_FOTO = "imagen"
TIPO_VIDEO = "video"
# Cómo queda en el historial cada archivo enviado, lo mande Victoria o el dueño desde el panel (y cómo se cuentan después:
# `contar_fotos` busca el SKU entre paréntesis).
PREFIJO_FOTO = "📷 Foto de "
PREFIJO_VIDEO = "🎬 Video de "
_NOMBRE_DE_ARCHIVO = re.compile(r"^[A-Za-z0-9._-]{1,120}$")


class RutaDeImagenInvalida(ValueError):
    pass


def url_publica(supabase_url: str, ruta: str) -> str:
    """Enlace https público de un archivo del bucket."""
    return f"{supabase_url.rstrip('/')}/storage/v1/object/public/{BUCKET}/{quote(ruta, safe='/')}"


def carpeta_de(producto_id: int) -> str:
    """La carpeta del producto dentro del bucket."""
    return f"p{producto_id}"


def validar_ruta(carpeta_esperada: str, ruta: str) -> str:
    """La ruta tiene que ser `<carpeta>/<archivo>.jpg|png|mp4|3gp`: dentro de la carpeta de ESTE producto, sin subcarpetas
    ni trucos (`..`). Devuelve la ruta limpia o lanza `RutaDeImagenInvalida`."""
    ruta = (ruta or "").strip()
    carpeta, _, archivo = ruta.rpartition("/")
    if carpeta != carpeta_esperada or not _NOMBRE_DE_ARCHIVO.match(archivo) or ".." in archivo:
        raise RutaDeImagenInvalida("La foto debe estar en la carpeta de este producto, con un nombre simple.")
    if archivo.rsplit(".", 1)[-1].lower() not in EXTENSIONES:
        raise RutaDeImagenInvalida("Solo se aceptan fotos JPG o PNG y videos MP4 o 3GP (WhatsApp no acepta otros formatos).")
    return ruta


def tipo_de(ruta_o_url: str) -> str:
    """«video» o «imagen», por la extensión del archivo (la app sube los videos tal cual y las fotos siempre como JPG)."""
    extension = (ruta_o_url or "").split("?", 1)[0].rsplit(".", 1)[-1].lower()
    return TIPO_VIDEO if extension in EXTENSIONES_VIDEO else TIPO_FOTO


def galeria_para_enviar(subidas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Lo que Victoria puede mandar, como `{"url", "tipo"}`: SOLO el material (fotos y videos) que el dueño subió a la ficha
    (bucket de Supabase), en su orden. La foto de Rocketfy nunca se envía a un cliente (pedido de Freddy 2026-11-09). Solo
    enlaces https: Meta no descarga otra cosa."""
    return [
        {"url": i["url"], "tipo": tipo_de(i.get("storage_path") or i["url"])}
        for i in subidas
        if str(i.get("url", "")).lower().startswith("https://")
    ]
