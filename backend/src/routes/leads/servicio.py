"""
Lógica de leads (docs/PLAN_LEADS_CRM.md): quién puede cambiar la temperatura y con qué reglas, el enfriamiento por silencio y
«no contactar». Una sola puerta para el dueño (la app), Victoria (herramientas) y el job automático.

Quién manda, de más a menos fuerte: el DUEÑO a mano (queda fijada unos días), los HECHOS (una venta cerrada es «ganado», una
cancelada «perdido»: no se contradicen) y la IA (Victoria: juicio sobre qué tan en serio compra). El tiempo solo ENFRÍA.
"""
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.config.parametros import parametros

from .exceptions import ContactoNoEncontradoError, DatosInvalidosError, LeadNoEncontradoError, VentaYaCerradaError
from .repository import ORDENES_VALIDOS, LeadsRepository
from .temperaturas import (
    ABIERTAS,
    CALIENTE,
    FINALES,
    GANADO,
    MOTIVOS_DE_PERDIDA,
    ORIGEN_DUENO,
    ORIGEN_IA,
    ORIGEN_REGLA,
    PERDIDO,
    TEMPERATURAS,
    es_abierta,
    es_final,
    limpiar_motivo,
    motivo_de_perdida_valido,
    temperatura_por_hechos,
    temperatura_por_silencio,
    tipo_de_contacto,
)

logger = logging.getLogger(__name__)

PERIODOS_VALIDOS_DIAS = (7, 30, 90)
MAXIMO_POR_PAGINA = 100


def desde_de_periodo(dias: Optional[int], ahora: Optional[datetime] = None) -> Optional[datetime]:
    if not dias:
        return None
    return (ahora or datetime.now(timezone.utc)) - timedelta(days=dias)


def _decimal(valor) -> Decimal:
    return Decimal(str(valor or 0))


class LeadsServicio:
    def __init__(self, repo: Optional[LeadsRepository] = None):
        self._repo = repo or LeadsRepository()

    # ------------------------------------------------------------------ lectura (la pantalla)
    def listar(
        self,
        temperaturas: Optional[List[str]] = None,
        etapa: Optional[str] = None,
        origen: Optional[str] = None,
        canal: Optional[str] = None,
        producto_sku: Optional[str] = None,
        q: Optional[str] = None,
        no_contactar: Optional[bool] = None,
        sin_respuesta_dias: Optional[int] = None,
        orden: str = "actividad",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        invalidas = [t for t in (temperaturas or []) if t not in TEMPERATURAS]
        if invalidas:
            raise DatosInvalidosError(f"Temperatura desconocida: {', '.join(invalidas)}.")
        if orden not in ORDENES_VALIDOS:
            raise DatosInvalidosError(f"El orden debe ser uno de: {', '.join(ORDENES_VALIDOS)}.")
        return self._repo.listar(
            temperaturas=temperaturas, etapa=etapa, origen=origen, canal=canal, producto_sku=producto_sku,
            q=(q or "").strip() or None, no_contactar=no_contactar, sin_respuesta_dias=sin_respuesta_dias,
            orden=orden, page=max(page, 1), page_size=min(max(page_size, 1), MAXIMO_POR_PAGINA),
        )

    def resumen(self, dias: Optional[int]) -> Dict[str, Any]:
        crudo = self._repo.resumen(desde_de_periodo(dias))
        ganados, perdidos = int(crudo["ganados"] or 0), int(crudo["perdidos"] or 0)
        cerrados = ganados + perdidos
        return {
            "calientes": int(crudo["calientes"] or 0),
            "tibios": int(crudo["tibios"] or 0),
            "frios": int(crudo["frios"] or 0),
            "valor_en_juego": _decimal(crudo["valor_en_juego"]),
            "nuevos": int(crudo["nuevos"] or 0),
            "ganados": ganados,
            "perdidos": perdidos,
            "ingresos_ganados": _decimal(crudo["ingresos_ganados"]),
            # Tasa de cierre: de los leads que ya terminaron en el periodo, cuántos se vendieron. Sin cierres no hay tasa.
            "tasa_de_cierre": (Decimal(ganados) * 100 / Decimal(cerrados)).quantize(Decimal("0.1")) if cerrados else None,
            "no_contactar": int(crudo["no_contactar"] or 0),
            "motivos_de_perdida": [
                {"motivo": f["motivo"], "etiqueta": MOTIVOS_DE_PERDIDA.get(f["motivo"], f["motivo"]), "leads": int(f["leads"])}
                for f in crudo["motivos_de_perdida"]
            ],
        }

    def detalle(self, lead_id: int) -> Dict[str, Any]:
        lead = self._repo.obtener(lead_id)
        if lead is None:
            raise LeadNoEncontradoError(f"No existe el lead {lead_id}.")
        ficha = self._repo.ficha_de_contacto(lead["contacto_id"])
        if ficha is not None:
            ficha["tipo"] = tipo_de_contacto(int(ficha["compras"]["compras"] or 0))
        return {"lead": lead, "historial": self._repo.historial(lead_id), "contacto": ficha}

    # ------------------------------------------------------------------ el dueño
    def cambiar_temperatura(
        self, lead_id: int, temperatura: str, motivo_perdida: Optional[str], motivo: Optional[str], usuario: Optional[str]
    ) -> Dict[str, Any]:
        """El dueño cambia la temperatura a mano. Queda FIJADA unos días (`leads.dias_fijar`): el enfriamiento automático y
        Victoria no la pisan. Una venta cerrada o cancelada manda sobre la temperatura y no se contradice."""
        if temperatura not in TEMPERATURAS:
            raise DatosInvalidosError(f"La temperatura debe ser una de: {', '.join(TEMPERATURAS)}.")
        lead = self._repo.obtener(lead_id)
        if lead is None:
            raise LeadNoEncontradoError(f"No existe el lead {lead_id}.")
        impuesta = temperatura_por_hechos(lead["etapa"])
        if impuesta is not None and temperatura != impuesta:
            raise VentaYaCerradaError(
                "Este lead ya tiene una venta cerrada: es «ganado»." if impuesta == GANADO
                else "La venta de este lead se canceló: es «perdido»."
            )
        if temperatura == PERDIDO:
            motivo_perdida = motivo_perdida or "otro"
            if not motivo_de_perdida_valido(motivo_perdida):
                raise DatosInvalidosError(f"El motivo de pérdida debe ser uno de: {', '.join(MOTIVOS_DE_PERDIDA)}.")
        fijada_hasta = None
        if es_abierta(temperatura):
            fijada_hasta = datetime.now(timezone.utc) + timedelta(days=parametros.valor("leads.dias_fijar"))
        self._repo.fijar_temperatura(
            lead_id, temperatura, ORIGEN_DUENO, motivo=motivo, usuario=usuario,
            motivo_perdida=motivo_perdida, fijada_hasta=fijada_hasta,
        )
        return self.detalle(lead_id)

    def marcar_no_contactar(self, contacto_id: int, valor: bool, motivo: Optional[str], usuario: Optional[str]) -> None:
        if not self._repo.marcar_no_contactar(contacto_id, valor, motivo, ORIGEN_DUENO, usuario):
            raise ContactoNoEncontradoError(f"No existe el contacto {contacto_id}.")

    # ------------------------------------------------------------------ Victoria
    def clasificar_por_ia(
        self, lead_id: int, temperatura: str, motivo: Optional[str], motivo_perdida: Optional[str] = None
    ) -> Dict[str, Any]:
        """Victoria dice qué tan en serio compra el cliente. Devuelve `{"aplicado": bool, "razon": texto}`; `razon` explica,
        en lenguaje que Victoria entiende, por qué no se aplicó. Reglas: no pisa lo que fijó el dueño, no contradice una venta
        cerrada o cancelada, no reabre un lead terminado y no puede dar «ganado» (eso lo decide la venta, no su juicio)."""
        if temperatura not in TEMPERATURAS:
            return {"aplicado": False, "razon": f"Temperatura desconocida: usa una de {', '.join(TEMPERATURAS)}."}
        if temperatura == GANADO:
            return {"aplicado": False, "razon": "«ganado» lo pone el sistema cuando la venta se cierra; tú no lo marcas."}
        lead = self._repo.obtener(lead_id)
        if lead is None:
            return {"aplicado": False, "razon": "No existe el lead."}
        if es_final(lead["temperatura"]):
            return {"aplicado": False, "razon": "Este lead ya terminó (ganado o perdido): un cliente nuevo abre uno nuevo."}
        fijada = lead["temperatura_fijada_hasta"]
        if fijada is not None and fijada > datetime.now(timezone.utc):
            return {"aplicado": False, "razon": "El dueño fijó la temperatura de este lead a mano: no se cambia."}
        if temperatura == PERDIDO:
            motivo_perdida = motivo_perdida if motivo_de_perdida_valido(motivo_perdida) else "otro"
        cambio = self._repo.fijar_temperatura(
            lead_id, temperatura, ORIGEN_IA, motivo=motivo, motivo_perdida=motivo_perdida if temperatura == PERDIDO else None
        )
        return {"aplicado": True, "cambio": cambio, "razon": ""}

    def no_contactar_por_ia(self, contacto_id: int, motivo: Optional[str]) -> bool:
        """El cliente pidió que no le escribamos: se marca en su contacto y sus leads abiertos pasan a «perdido»."""
        return self._repo.marcar_no_contactar(contacto_id, True, motivo or "El cliente pidió que no lo contacten", ORIGEN_IA, None)

    # ------------------------------------------------------------------ el tiempo
    def enfriar_por_silencio(self, ahora: Optional[datetime] = None) -> Dict[str, int]:
        """Baja la temperatura de los leads abiertos cuyo cliente dejó de escribir. Solo si `leads.enfriar_activo`. Nunca lanza:
        un lead que falla no impide enfriar los demás."""
        if not parametros.valor("leads.enfriar_activo"):
            return {"revisados": 0, "enfriados": 0}
        ahora = ahora or datetime.now(timezone.utc)
        a_tibio = parametros.valor("leads.dias_a_tibio")
        a_frio = parametros.valor("leads.dias_a_frio")
        a_perdido = parametros.valor("leads.dias_a_perdido")
        revisados = enfriados = 0
        for candidato in self._repo.candidatos_a_enfriar():
            revisados += 1
            dias = (ahora - candidato["ultimo_cliente_en"]).total_seconds() / 86400
            nueva = temperatura_por_silencio(candidato["temperatura"], dias, a_tibio, a_frio, a_perdido)
            if nueva == candidato["temperatura"]:
                continue
            try:
                motivo = f"El cliente no escribe hace {int(dias)} días"
                if self._repo.fijar_temperatura(
                    candidato["id"], nueva, ORIGEN_REGLA, motivo=motivo,
                    motivo_perdida="sin_respuesta" if nueva == PERDIDO else None,
                ):
                    enfriados += 1
            except Exception:
                logger.exception("No se pudo enfriar el lead %s", candidato["id"])
        if enfriados:
            logger.info("Enfriamiento de leads: %d de %d revisados cambiaron de temperatura", enfriados, revisados)
        return {"revisados": revisados, "enfriados": enfriados}
