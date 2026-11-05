"""
Servicio de «Probar con Victoria» (Fase E): pone los topes y las reglas
alrededor del motor de ensayo (simulacion.py), que es el que de verdad corre el
cerebro de Victoria sin tocar el mundo real.

Orden de las comprobaciones (de la más barata a la que gasta plata):
  producto existe y no está archivado -> tiene lo mínimo para conversar ->
  la prueba puede seguir -> tope de mensajes de hoy -> la IA.

Qué escribe en la base (y SOLO esto): una fila en `generaciones_ia` por mensaje
de prueba (para el tope y la auditoría) y, cuando una compra simulada se completa
de punta a punta, una entrada «simulacion_completa» en el historial del producto
(alimenta el aviso «no se ha probado una compra completa» de la lista de
verificación al publicar). Ninguna conversación, mensaje, lead ni pedido.
"""
import logging
from typing import Any, Dict, List, Optional

from src.integrations.llm import LLMAuthError, LLMError, LLMRateLimitError
from src.routes.ajustes.services import AjustesService

from .dto import (
    AvisoSimuladoDTO,
    LlamadaHerramientaDTO,
    PedidoSimuladoDTO,
    TurnoSimuladoDTO,
    UsoIADTO,
)
from .exceptions import (
    IAFalloError,
    IANoDisponibleError,
    ProductoBotNoEncontradoError,
    PruebaInvalidaError,
    PublicacionBloqueadaError,
    TopeDePruebasAlcanzadoError,
    TransicionInvalidaError,
)
from .generaciones import TIPO_SIMULACION, GeneracionesIARepository
from .repository import ACCION_SIMULACION_COMPLETA, ProductoBotGestionRepository
from .simulacion import simular_turno
from .verificacion import metodos_de_pago

logger = logging.getLogger(__name__)

# Mensajes del cliente en una misma prueba. Pasado esto la conversación ya no
# enseña nada nuevo y cada mensaje sigue costando (el historial viaja completo).
MAX_MENSAJES_POR_PRUEBA = 20

_A_CAMEL = {
    "nombre_cliente": "nombreCliente",
    "producto_sku": "productoSku",
    "producto_nombre": "productoNombre",
    "producto_variante": "productoVariante",
    "metodo_pago": "metodoPago",
    "id_pedido_local": "idPedidoLocal",
    "id_pedido_rocketfy": "idPedidoRocketfy",
}


def _estado_a_camel(estado: Dict[str, Any]) -> Dict[str, Any]:
    return {_A_CAMEL.get(clave, clave): valor for clave, valor in estado.items()}


def faltantes_para_probar(ficha: dict) -> List[str]:
    """Lo mínimo para que la conversación de prueba tenga sentido. No es la
    lista de verificación de publicar (esa pide más, como el piso de precio): un
    producto con el precio bajo el piso igual se puede probar."""
    faltan: List[str] = []
    if not (ficha.get("nombre") or "").strip():
        faltan.append("Falta el nombre del producto.")
    if not (ficha.get("descripcion") or "").strip():
        faltan.append("Falta la descripción de ventas: es lo que Victoria sabe del producto.")
    if not (ficha.get("tiempo_entrega") or "").strip():
        faltan.append("Falta el tiempo de entrega.")
    if not metodos_de_pago(ficha.get("metodos_pago_aceptados")):
        faltan.append("Falta elegir al menos un método de pago.")
    precio = ficha.get("precio")
    if precio is None or float(precio) <= 0:
        faltan.append("El precio de venta debe ser mayor que cero.")
    return faltan


class PruebasService:
    def __init__(self, repo=None, generaciones=None, ajustes_service=None, llm=None, modelo=None):
        self._repo = repo or ProductoBotGestionRepository()
        self._generaciones = generaciones or GeneracionesIARepository()
        self._ajustes = ajustes_service or AjustesService()
        self._llm = llm
        self._modelo = modelo

    # ------------------------------------------------------------------
    def uso(self) -> UsoIADTO:
        tope = self._ajustes.obtener_ajustes().tope_pruebas_dia
        usadas = self._generaciones.contar_hoy(TIPO_SIMULACION)
        return UsoIADTO(tope=tope, usadas=usadas, restantes=max(0, tope - usadas))

    def probar(
        self,
        sku: str,
        mensaje: str,
        historial: List[Dict[str, str]],
        estado: Optional[Dict[str, Any]],
        desde_anuncio: bool,
        escalada: bool,
        usuario: Optional[str],
    ) -> TurnoSimuladoDTO:
        sku = (sku or "").strip()
        ficha = self._repo.obtener(sku)
        if ficha is None:
            raise ProductoBotNoEncontradoError(f"No existe un producto con el SKU '{sku}'.")
        if ficha["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede probar: restáuralo primero.")
        faltan = faltantes_para_probar(ficha)
        if faltan:
            raise PublicacionBloqueadaError(faltan)

        self._validar_que_la_prueba_siga(historial, estado, escalada)

        # El tope se mira antes de gastar nada.
        uso = self.uso()
        if uso.restantes <= 0:
            raise TopeDePruebasAlcanzadoError(uso.usadas, uso.tope)

        llm = self._cliente_llm()
        modelo = self._nombre_del_modelo()
        try:
            turno = simular_turno(
                producto=ficha,
                mensaje=mensaje,
                historial=historial,
                estado=estado,
                desde_anuncio=desde_anuncio,
                llm=llm,
            )
        except LLMAuthError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo")
            logger.error("La IA rechazó las credenciales en una prueba: %s", exc)
            raise IANoDisponibleError("La IA no está configurada correctamente (revisa ANTHROPIC_API_KEY en Railway).") from exc
        except LLMRateLimitError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo")
            raise IANoDisponibleError("La IA está saturada en este momento. Intenta de nuevo en un minuto.") from exc
        except LLMError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo")
            logger.error("Falló la llamada a la IA en una prueba: %s", exc)
            raise IAFalloError("No se pudo contactar a la IA. Intenta de nuevo en un momento.") from exc
        except Exception:
            # Un fallo nuestro (no del proveedor): no debe contar para el tope.
            self._registrar(ficha["sku"], usuario, modelo, "fallo")
            raise

        self._registrar(ficha["sku"], usuario, modelo, "ok")
        if turno.pedido is not None and turno.pedido["confirmado"]:
            self._anotar_simulacion_completa(ficha["sku"], usuario)

        return TurnoSimuladoDTO(
            respuesta=turno.respuesta,
            herramientas=[
                LlamadaHerramientaDTO(nombre=h["nombre"], entrada=h["entrada"], resultado=h["resultado"])
                for h in turno.herramientas
            ],
            estado=_estado_a_camel(turno.estado),
            escalada=turno.escalada,
            pedido=PedidoSimuladoDTO(payload=turno.pedido["payload"], confirmado=turno.pedido["confirmado"])
            if turno.pedido
            else None,
            avisos=[AvisoSimuladoDTO(canal=a["canal"], texto=a["texto"]) for a in turno.avisos],
            uso=UsoIADTO(tope=uso.tope, usadas=uso.usadas + 1, restantes=max(0, uso.restantes - 1)),
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _validar_que_la_prueba_siga(historial, estado, escalada: bool) -> None:
        if escalada:
            raise PruebaInvalidaError(
                "Victoria ya pasó esta conversación a una persona: en la vida real no seguiría respondiendo. "
                "Reinicia la prueba para empezar otra."
            )
        if (estado or {}).get("estado") == "despachado":
            raise PruebaInvalidaError(
                "La compra de esta prueba ya se cerró: en la vida real, si el cliente vuelve a escribir, lo atiende "
                "una persona. Reinicia la prueba para empezar otra."
            )
        del_cliente = sum(1 for h in historial if h.get("rol") == "cliente")
        if del_cliente >= MAX_MENSAJES_POR_PRUEBA:
            raise PruebaInvalidaError(
                f"La prueba llegó a {MAX_MENSAJES_POR_PRUEBA} mensajes. Reiníciala para empezar de nuevo."
            )

    def _anotar_simulacion_completa(self, sku: str, usuario: Optional[str]) -> None:
        """Es un registro de auditoría: si falla, la prueba ya se hizo y no debe tumbar la respuesta."""
        try:
            self._repo.registrar_historial(sku, ACCION_SIMULACION_COMPLETA, usuario, None)
        except Exception:
            logger.exception("No se pudo anotar la simulación completa de '%s' en el historial", sku)

    def _cliente_llm(self):
        if self._llm is None:
            from src.integrations.llm import get_llm_client

            try:
                self._llm = get_llm_client()
            except ValueError as exc:
                # Falta ANTHROPIC_API_KEY (o el proveedor no está soportado).
                raise IANoDisponibleError("Probar con Victoria no está configurado en el servidor (falta la clave de la IA).") from exc
        return self._llm

    def _nombre_del_modelo(self) -> Optional[str]:
        if self._modelo is None:
            from src.config.settings import load_settings

            self._modelo = load_settings().llm_model
        return self._modelo

    def _registrar(self, sku: str, usuario: Optional[str], modelo: Optional[str], resultado: str) -> None:
        """Auditoría y tope; si falla no debe tumbar la respuesta."""
        try:
            self._generaciones.registrar(sku, usuario, modelo, resultado, ["mensaje"], tipo=TIPO_SIMULACION)
        except Exception:
            logger.exception("No se pudo registrar el uso de una prueba (resultado=%s)", resultado)
