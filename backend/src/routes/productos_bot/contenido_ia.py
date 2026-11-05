"""
Servicio de «Redactar con IA» (Fase D del plan de gestión de productos).

Orquesta: tope diario -> datos de Rocketfy EN VIVO -> prompt -> LLM con
herramienta forzada (JSON de esquema fijo) -> interpretación -> verificaciones
con código -> registro del uso. Las reglas de fondo (por qué la IA no decide,
por qué el texto de Rocketfy no es de fiar) están en redaccion.py.

Qué NO hace, a propósito:
- No guarda el borrador ni toca la ficha: devuelve el borrador y punto. La
  persona lo acepta (pasa al formulario), lo guarda y lo publica.
- No cambia el estado del producto ni el precio.
- No le da a la IA costos, precios ni stock.
"""
import logging
from typing import List, Optional

from src.integrations.llm import LLMAuthError, LLMError, LLMRateLimitError, MensajeLLM
from src.routes.ajustes.services import AjustesService
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError

from .dto import AlertaContenidoDTO, BorradorContenidoDTO, CamposContenidoDTO, UsoIADTO
from .exceptions import (
    IAFalloError,
    IANoDisponibleError,
    ProductoBotNoEncontradoError,
    TopeDeIAAlcanzadoError,
    TransicionInvalidaError,
)
from .generaciones import GeneracionesIARepository
from .redaccion import (
    CAMPOS,
    NOMBRE_HERRAMIENTA,
    ORIGEN_VERIFICACION,
    Alerta,
    BorradorInvalidoError,
    NotasDelDueno,
    construir_mensaje,
    construir_system,
    frases_de_instrucciones,
    herramienta_borrador,
    interpretar_respuesta,
    verificar_borrador,
)
from .repository import ProductoBotGestionRepository
from .services import ProductosBotService, _limpiar_texto_de_rocketfy

logger = logging.getLogger(__name__)

# Una ficha completa son unos 1.5k tokens de salida; con margen.
MAX_TOKENS_DE_SALIDA = 2500

_A_CAMEL = {
    "nombre": "nombre",
    "descripcion": "descripcion",
    "variantes": "variantes",
    "preguntas_frecuentes": "preguntasFrecuentes",
    "temas_no_responder": "temasNoResponder",
}


def _camel(campo: Optional[str]) -> Optional[str]:
    return _A_CAMEL.get(campo) if campo else None


def _campos_dto(valores: dict) -> CamposContenidoDTO:
    return CamposContenidoDTO(**{c: valores.get(c) for c in CAMPOS})


class ContenidoIAService:
    def __init__(self, productos=None, repo=None, generaciones=None, ajustes_service=None, llm=None, modelo=None):
        self._productos = productos or ProductosBotService()
        self._repo = repo or ProductoBotGestionRepository()
        self._generaciones = generaciones or GeneracionesIARepository()
        self._ajustes = ajustes_service or AjustesService()
        self._llm = llm
        self._modelo = modelo

    # ------------------------------------------------------------------
    def uso(self) -> UsoIADTO:
        tope = self._ajustes.obtener_ajustes().tope_redacciones_dia
        usadas = self._generaciones.contar_hoy()
        return UsoIADTO(tope=tope, usadas=usadas, restantes=max(0, tope - usadas))

    def generar(
        self, sku: str, notas: NotasDelDueno, campos: Optional[List[str]], usuario: Optional[str]
    ) -> BorradorContenidoDTO:
        sku = (sku or "").strip()
        ficha = self._repo.obtener(sku)
        if ficha is None:
            raise ProductoBotNoEncontradoError(f"No existe un producto con el SKU '{sku}'.")
        if ficha["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede editar: restáuralo primero.")

        campos = [c for c in CAMPOS if campos is None or c in campos]
        if not campos:
            raise ValueError("No se pidió ningún campo para redactar.")

        # 1) Tope diario: antes de gastar nada.
        uso = self.uso()
        if uso.restantes <= 0:
            raise TopeDeIAAlcanzadoError(uso.usadas, uso.tope)

        # 2) Datos de Rocketfy EN VIVO (la `descripcion` guardada en la ficha ya
        #    pudo ser editada por la persona, así que no sirve como "lo que dice Rocketfy").
        en_vivo = self._consultar_rocketfy(ficha["sku"])
        datos_rocketfy = {
            "nombre": str(en_vivo.get("name") or "").strip(),
            "descripcion": _limpiar_texto_de_rocketfy(en_vivo.get("description")),
            "peso_kg": en_vivo.get("weight"),
        }

        # 3) La IA. Se le pide el borrador con una herramienta forzada.
        system = construir_system(notas.producto_de_salud)
        mensaje = construir_mensaje(datos_rocketfy, notas, ficha, campos)
        herramienta = herramienta_borrador(campos)
        modelo = self._nombre_del_modelo()
        try:
            respuesta = self._cliente_llm().generar_respuesta(
                system=system,
                mensajes=[MensajeLLM(rol="user", texto=mensaje)],
                herramientas=[herramienta],
                max_tokens=MAX_TOKENS_DE_SALIDA,
                forzar_herramienta=NOMBRE_HERRAMIENTA,
            )
        except LLMAuthError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo", campos)
            logger.error("La IA rechazó las credenciales: %s", exc)
            raise IANoDisponibleError("La IA no está configurada correctamente (revisa ANTHROPIC_API_KEY en Railway).") from exc
        except LLMRateLimitError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo", campos)
            raise IANoDisponibleError("La IA está saturada en este momento. Intenta de nuevo en un minuto.") from exc
        except LLMError as exc:
            self._registrar(ficha["sku"], usuario, modelo, "fallo", campos)
            logger.error("Falló la llamada a la IA: %s", exc)
            raise IAFalloError("No se pudo contactar a la IA. Intenta de nuevo en un momento.") from exc

        # 4) Interpretar y verificar (con código, sin creerle a ciegas).
        entrada = next((l.entrada for l in respuesta.llamadas_herramientas if l.nombre == NOMBRE_HERRAMIENTA), None)
        try:
            borrador = interpretar_respuesta(entrada, campos)
        except BorradorInvalidoError as exc:
            # La IA contestó (costó), pero sin el formato pedido.
            self._registrar(ficha["sku"], usuario, modelo, "invalido", campos)
            logger.warning("Borrador inválido de la IA para '%s': %s", ficha["sku"], exc)
            raise IAFalloError("La IA no devolvió un borrador válido. Intenta de nuevo (este intento cuenta en tu tope).") from exc

        corpus = "\n".join(
            [
                datos_rocketfy["nombre"],
                datos_rocketfy["descripcion"],
                str(datos_rocketfy.get("peso_kg") or ""),
                notas.dirigido_a,
                notas.destacar,
                notas.evitar,
                notas.otros_datos,
                *(str(ficha.get(c) or "") for c in CAMPOS),
            ]
        )
        borrador = verificar_borrador(borrador, corpus, producto_de_salud=notas.producto_de_salud)

        # Si el texto de Rocketfy trae frases que parecen órdenes, se avisa aunque la IA las haya ignorado.
        sospechosas = frases_de_instrucciones(datos_rocketfy["nombre"] + "\n" + datos_rocketfy["descripcion"])
        if sospechosas:
            borrador.alertas.insert(
                0,
                Alerta(
                    None,
                    "El texto de Rocketfy contiene frases que parecen instrucciones ("
                    + ", ".join(f"«{f}»" for f in sospechosas[:3])
                    + "). Se trataron como datos y se ignoraron; revisa el borrador con más cuidado.",
                    ORIGEN_VERIFICACION,
                ),
            )

        self._registrar(ficha["sku"], usuario, modelo, "ok", campos)
        self._repo.registrar_historial(ficha["sku"], "redactado_ia", usuario, {"campos": campos})

        return BorradorContenidoDTO(
            campos=_campos_dto(borrador.campos),
            fuentes=_campos_dto(borrador.fuentes),
            alertas=[AlertaContenidoDTO(campo=_camel(a.campo), texto=a.texto, origen=a.origen) for a in borrador.alertas],
            uso=UsoIADTO(tope=uso.tope, usadas=uso.usadas + 1, restantes=max(0, uso.restantes - 1)),
        )

    # ------------------------------------------------------------------
    def _consultar_rocketfy(self, sku: str) -> dict:
        # Si Rocketfy falla, el error sube tal cual (el controlador lo traduce a 502).
        producto = self._productos.consultar_rocketfy(sku)
        if producto is None:
            raise SkuNoExisteEnRocketfyError(f"El SKU '{sku}' ya no existe en el catálogo de Rocketfy.")
        return producto

    def _cliente_llm(self):
        if self._llm is None:
            from src.integrations.llm import get_llm_client

            try:
                self._llm = get_llm_client()
            except ValueError as exc:
                # Falta ANTHROPIC_API_KEY (o el proveedor no está soportado).
                raise IANoDisponibleError("La redacción con IA no está configurada en el servidor.") from exc
        return self._llm

    def _nombre_del_modelo(self) -> Optional[str]:
        if self._modelo is None:
            from src.config.settings import load_settings

            self._modelo = load_settings().llm_model
        return self._modelo

    def _registrar(self, sku: str, usuario: Optional[str], modelo: Optional[str], resultado: str, campos: List[str]) -> None:
        """El registro es auditoría y tope; si falla no debe tumbar la respuesta."""
        try:
            self._generaciones.registrar(sku, usuario, modelo, resultado, campos)
        except Exception:
            logger.exception("No se pudo registrar el uso de la IA (resultado=%s)", resultado)
