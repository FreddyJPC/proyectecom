"""
Anuncios de Click-to-WhatsApp: registrar cada llegada por anuncio, saber de dónde vino un cliente, vincular un
anuncio con su producto y medir cuánto vende cada anuncio.

Para qué sirve (pedido de Freddy, 2026-11-09: «debemos siempre saber de dónde viene cada cliente»):
- Cada vez que un cliente escribe tocando un anuncio se guarda TODO lo que Meta manda (anuncio, título, texto, enlace,
  imagen, clic) aunque el cliente ya existiera: antes solo se guardaba la primera vez y solo dos datos.
- Con el anuncio vinculado a un producto, Victoria sabe de qué hablar sin preguntar.
- Con las ventas marcadas con su origen y anuncio, se puede medir qué anuncio vende.
"""
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


from .exceptions import AnuncioInvalidoError, AnuncioNoVinculadoError, AnuncioYaVinculadoError, ProductoNoExisteError
from .referral import normalizar_referral
from .repository import AnuncioRepository
from .ventana import ventana_de_servicio, ventana_gratuita

logger = logging.getLogger(__name__)

# El ID de un anuncio de Meta es numérico y largo (unos 15-17 dígitos); se acepta cualquier identificador razonable.
_ID_ANUNCIO = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_LARGO_NOMBRE = 120
PERIODOS_VALIDOS_DIAS = (7, 30, 90)

TEXTO_DIRECTO = "Escribió directo (sin anuncio)"


def validar_id_anuncio(id_anuncio: str) -> str:
    limpio = (id_anuncio or "").strip()
    if not _ID_ANUNCIO.match(limpio):
        raise AnuncioInvalidoError(
            "El ID del anuncio solo puede tener letras, números, guiones y puntos (hasta 64 caracteres). "
            "Lo ves en el Administrador de anuncios de Meta."
        )
    return limpio


def desde_de_periodo(dias: Optional[int], ahora: Optional[datetime] = None) -> Optional[datetime]:
    """Fecha de inicio del periodo (None = todo el tiempo)."""
    if not dias:
        return None
    return (ahora or datetime.now(timezone.utc)) - timedelta(days=dias)


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


class AnuncioServicio:
    def __init__(self, repo: Optional[AnuncioRepository] = None, productos=None):
        self._repo = repo or AnuncioRepository()
        if productos is None:
            # Import local: `whatsapp` importa este módulo, y a la vez `whatsapp.repository` vive en ese paquete.
            from src.routes.whatsapp.repository import ProductoBotRepository

            productos = ProductoBotRepository()
        self._productos = productos

    # ------------------------------------------------------------------ llegada por anuncio

    def registrar_llegada(
        self, conversacion_id: int, mensaje_id: Optional[int], wamid: Optional[str], referral: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Guarda la llegada y actualiza el origen de la conversación. Devuelve `{"registrada", "anuncio_nuevo", "datos"}`."""
        datos = normalizar_referral(referral)
        resultado = self._repo.registrar_llegada(conversacion_id, mensaje_id, wamid, datos, referral)
        return {**resultado, "datos": datos}

    def describir_origen(self, conversacion_id: int) -> str:
        """Una línea para los avisos de Telegram: de dónde viene este cliente. Best-effort: nunca lanza."""
        try:
            llegadas = self._repo.llegadas_de(conversacion_id)
        except Exception:
            logger.exception("No se pudo leer el origen de la conversación %s", conversacion_id)
            return ""
        if not llegadas:
            return TEXTO_DIRECTO
        ultima = llegadas[0]
        partes = ["Viene de un anuncio"]
        if ultima.get("titulo"):
            partes.append(f"«{ultima['titulo']}»")
        if ultima.get("id_anuncio"):
            partes.append(f"(ID {ultima['id_anuncio']})")
        if len(llegadas) > 1:
            partes.append(f"· llegó {len(llegadas)} veces por anuncio")
        return " ".join(partes)

    def origen_de_conversacion(self, conversacion: Dict[str, Any], mensajes: List[Dict[str, Any]], ahora: Optional[datetime] = None) -> Dict[str, Any]:
        """Todo lo que la pantalla de una conversación necesita saber del origen: el anuncio, su producto, el historial de
        llegadas y el estado de la ventana gratuita."""
        ahora = ahora or datetime.now(timezone.utc)
        llegadas = self._repo.llegadas_de(conversacion["id"])
        id_anuncio = conversacion.get("id_anuncio")
        vinculo = self._repo.vinculo_de(id_anuncio) if id_anuncio else None
        gratuita = ventana_gratuita([l["creado_en"] for l in llegadas], mensajes, ahora)
        return {
            "ultima": llegadas[0] if llegadas else None,
            "producto": vinculo,
            "llegadas": llegadas,
            "ventana_gratuita": gratuita,
        }

    @staticmethod
    def ventana_de_servicio(mensajes: List[Dict[str, Any]], ahora: Optional[datetime] = None):
        return ventana_de_servicio(mensajes, ahora or datetime.now(timezone.utc))

    # ------------------------------------------------------------------ vincular anuncio y producto

    def vincular(self, id_anuncio: str, sku: str, nombre: Optional[str] = None, reasignar: bool = False) -> Dict[str, Any]:
        id_anuncio = validar_id_anuncio(id_anuncio)
        sku = (sku or "").strip()
        producto = self._productos.obtener_por_sku(sku) if sku else None
        if producto is None:
            raise ProductoNoExisteError(sku)
        actual = self._repo.vinculo_de(id_anuncio)
        if actual is not None and actual["producto_sku"] != sku and not reasignar:
            raise AnuncioYaVinculadoError(id_anuncio, actual["producto_sku"], actual.get("producto_nombre"))
        nombre_limpio = (nombre or "").strip()[:_LARGO_NOMBRE] or None
        self._repo.vincular(id_anuncio, sku, nombre_limpio)
        return {"id_anuncio": id_anuncio, "producto_sku": sku, "producto_nombre": producto["nombre"]}

    def desvincular(self, id_anuncio: str) -> None:
        id_anuncio = validar_id_anuncio(id_anuncio)
        if not self._repo.desvincular(id_anuncio):
            raise AnuncioNoVinculadoError(id_anuncio)

    # ------------------------------------------------------------------ rendimiento

    def listar(self, dias: Optional[int]) -> List[Dict[str, Any]]:
        return self._repo.listar_anuncios(desde_de_periodo(dias))

    def resumen(self, dias: Optional[int]) -> Dict[str, Any]:
        crudo = self._repo.resumen_por_origen(desde_de_periodo(dias))
        base = crudo["base"] or {}
        return {
            "anuncio": {"conversaciones": int(base.get("conv_anuncio") or 0), **crudo["ventas_anuncio"]},
            "directo": {"conversaciones": int(base.get("conv_directo") or 0), **crudo["ventas_directo"]},
            "llegadas": int(base.get("llegadas") or 0),
            "anuncios_activos": int(base.get("anuncios_activos") or 0),
            "anuncios_sin_vincular": int(base.get("sin_vincular") or 0),
        }
