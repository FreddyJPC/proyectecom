"""
Anotar y revisar los casos de «Aprendizaje de Victoria».

`RegistroAprendizaje.anotar` lo llaman Victoria (al pasar a un asesor), las reglas del código (cierre frenado, agencia por
definir, fallos) y el panel (el dueño tuvo que intervenir). NUNCA rompe la conversación: si guardar falla, se registra en el log
y la venta sigue. Usa los mismos repositorios que quien lo llama (así los tests y la simulación lo alimentan con lo suyo).
"""
import logging
from typing import Any, Callable, Dict, Optional

from . import logica
from .repository import AprendizajeRepository

logger = logging.getLogger(__name__)


class RegistroAprendizaje:
    def __init__(self, leads=None, mensajes=None, conversaciones=None, guardar: Optional[Callable[[Dict[str, Any]], Any]] = None):
        self._leads = leads
        self._mensajes = mensajes
        self._conversaciones = conversaciones
        self._guardar = guardar or AprendizajeRepository.insertar

    def anotar(
        self,
        tipo: str,
        origen: str,
        motivo: str,
        conversacion_id: Optional[int],
        lead: Optional[Dict[str, Any]] = None,
        contexto: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            self._guardar(self._armar(tipo, origen, motivo, conversacion_id, lead, contexto))
        except Exception:  # noqa: BLE001 — anotar para aprender nunca puede frenar una venta
            logger.warning("No se pudo anotar el caso de aprendizaje (%s)", tipo, exc_info=True, extra={"conversacion_id": conversacion_id})

    def _armar(self, tipo, origen, motivo, conversacion_id, lead, contexto) -> Dict[str, Any]:
        if lead is None and conversacion_id is not None and self._leads is not None:
            lead = self._leads.obtener_por_conversacion(conversacion_id)
        mensajes = []
        if conversacion_id is not None and self._mensajes is not None:
            mensajes = self._mensajes.obtener_por_conversacion(conversacion_id) or []
        contacto_id = (lead or {}).get("contacto_id")
        if contacto_id is None and conversacion_id is not None and self._conversaciones is not None:
            contacto_id = (self._conversaciones.obtener_por_id(conversacion_id) or {}).get("contacto_id")
        return {
            "conversacion_id": conversacion_id,
            "lead_id": (lead or {}).get("id"),
            "contacto_id": contacto_id,
            "tipo": logica.tipo_valido(tipo),
            "origen": origen if origen in logica.ORIGENES else "sistema",
            "motivo": logica.recortar(motivo, logica.LARGO_MAXIMO_MOTIVO) or logica.TIPOS[logica.tipo_valido(tipo)],
            "mensaje_cliente": logica.ultimo_del_cliente(mensajes),
            "etapa": logica.etapa_de_venta(lead),
            "producto_sku": (lead or {}).get("producto_sku"),
            "contexto": {**(contexto or {}), "mensajes": logica.extracto(mensajes)},
        }


class RegistroQueNoGuarda(RegistroAprendizaje):
    """Para «Probar con Victoria»: una conversación de ensayo no debe dejar casos reales."""

    def anotar(self, *args, **kwargs) -> None:
        return None


class CasoNoEncontradoError(Exception):
    pass


class DatosInvalidosError(ValueError):
    pass


class AprendizajeServicio:
    def __init__(self, repo=None):
        self._repo = repo or AprendizajeRepository

    def listar(self, estado: Optional[str], tipo: Optional[str], dias: Optional[int], pagina: int, por_pagina: int):
        if estado and estado not in logica.ESTADOS:
            raise DatosInvalidosError("Estado desconocido.")
        if tipo and tipo not in logica.TIPOS:
            raise DatosInvalidosError("Tipo desconocido.")
        por_pagina = max(1, min(por_pagina, 100))
        pagina = max(1, pagina)
        filas, total = self._repo.listar(estado, tipo, dias, por_pagina, (pagina - 1) * por_pagina)
        return {"casos": filas, "total": total, "pagina": pagina, "porPagina": por_pagina}

    def resumen(self, dias: Optional[int]) -> Dict[str, Any]:
        return self._repo.resumen(dias)

    def revisar(self, caso_id: int, estado: str, categoria: Optional[str], accion: Optional[str], nota: Optional[str], usuario: Optional[str]):
        if estado not in logica.ESTADOS:
            raise DatosInvalidosError("Estado desconocido.")
        if accion and accion not in logica.ACCIONES:
            raise DatosInvalidosError("Acción desconocida.")
        categoria = logica.recortar(categoria, 80)
        nota = logica.recortar(nota, 1000)
        if not self._repo.revisar(caso_id, estado, categoria, accion or None, nota, usuario):
            raise CasoNoEncontradoError(f"No existe el caso {caso_id}.")
        return self._repo.obtener(caso_id)
