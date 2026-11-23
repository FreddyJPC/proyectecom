"""
Quién atiende una conversación (módulo «Inmuebles», migración 037): Victoria («ventas») o el asistente de propiedades
(«inmuebles»). Lo decide, en este orden:

1. El ANUNCIO por el que llegó el cliente: si está vinculado a una propiedad, la atiende el asistente de inmuebles y ya se sabe
   de qué propiedad se habla. Así funciona aunque el anuncio apunte al mismo número que Victoria.
2. El NÚMERO del negocio al que escribió: cada número registrado en `numeros_whatsapp` tiene su asistente. Un número que no
   está registrado (p. ej. el principal) se atiende como siempre, con Victoria.

Nunca lanza: ante cualquier fallo, Victoria (lo de siempre).
"""
import logging
from typing import Optional, Tuple

from .repository import AnuncioInmuebleRepository, NumeroWhatsappRepository

logger = logging.getLogger(__name__)

VENTAS = "ventas"
INMUEBLES = "inmuebles"
ASISTENTES = (VENTAS, INMUEBLES)


class RuteoDeAsistente:
    def __init__(self, numeros: Optional[NumeroWhatsappRepository] = None, anuncios: Optional[AnuncioInmuebleRepository] = None):
        self._numeros = numeros or NumeroWhatsappRepository()
        self._anuncios = anuncios or AnuncioInmuebleRepository()

    def para_numero(self, numero_negocio: Optional[str]) -> str:
        try:
            return self._numeros.asistente_de(numero_negocio) or VENTAS
        except Exception:
            logger.exception("No se pudo leer qué asistente atiende el número %s", numero_negocio)
            return VENTAS

    def inmueble_de_anuncio(self, id_anuncio: Optional[str]) -> Optional[int]:
        try:
            return self._anuncios.inmueble_de_anuncio(id_anuncio)
        except Exception:
            logger.exception("No se pudo leer de qué propiedad habla el anuncio %s", id_anuncio)
            return None

    def decidir(self, numero_negocio: Optional[str], id_anuncio: Optional[str] = None) -> Tuple[str, Optional[int]]:
        inmueble_id = self.inmueble_de_anuncio(id_anuncio)
        if inmueble_id is not None:
            return INMUEBLES, inmueble_id
        return self.para_numero(numero_negocio), None
