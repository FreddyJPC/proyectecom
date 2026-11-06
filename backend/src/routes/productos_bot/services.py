"""
Gestión de los productos que Victoria puede vender, desde el dashboard (Fase B
del plan de gestión de productos, docs/PLAN_GESTION_PRODUCTOS.md).

Reglas que este servicio hace cumplir:
- Un producto nace SIEMPRE como borrador desde un SKU que existe EXACTAMENTE
  igual en Rocketfy (se usa el SKU tal como lo escribe Rocketfy, no como lo
  tecleó la persona): un SKU inventado fue la causa del primer fallo real de
  una venta.
- Nada llega a Victoria hasta pulsar publicar (o reanudar), y para eso se
  vuelve a consultar Rocketfy EN VIVO. Si Rocketfy no responde, no se publica
  a ciegas (a diferencia de la venta, que sí sigue sin saber el stock).
- `estado` y `activo` cambian juntos en un único lugar
  (ProductoBotGestionRepository.cambiar_estado).
- Todo cambio queda en el historial con el correo de quien lo hizo.
"""
import html
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.integrations.rocketfy import get_rocketfy_client
from src.routes.ajustes.services import AjustesService
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError
from src.routes.productos.repository import SkuMonitoreadoRepository

from .calculadora import envio_para_piso, ganancia_por_unidad, margen_pct, recomendar
from .dto import (
    EvaluacionPrecioDTO,
    HistorialDTO,
    NivelPrecioDTO,
    ProductoBotDetalleDTO,
    ProductoBotResumenDTO,
    RecomendacionPrecioDTO,
    VerificacionDTO,
)
from .exceptions import (
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    TransicionInvalidaError,
)
from .repository import ACCION_SIMULACION_COMPLETA, ProductoBotGestionRepository
from .verificacion import bloqueos_de_contenido, metodos_de_pago, verificar_producto

logger = logging.getLogger(__name__)

UMBRAL_STOCK_AL_PUBLICAR = 5
LARGO_MAXIMO_DESCRIPCION_ROCKETFY = 1500
LARGO_MAXIMO_VALOR_EN_HISTORIAL = 300

# accion -> (estados desde los que se permite, estado destino, acción en el historial)
_TRANSICIONES = {
    "publicar": ({"borrador", "listo"}, "activo", "publicado"),
    "reanudar": ({"pausado", "agotado"}, "activo", "reanudado"),
    "pausar": ({"activo"}, "pausado", "pausado"),
    "archivar": ({"borrador", "listo", "activo", "pausado", "agotado"}, "archivado", "archivado"),
    "restaurar": ({"archivado"}, "borrador", "restaurado"),
}


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


def _dinero(valor) -> Optional[str]:
    if valor is None or valor == "":
        return None
    try:
        return f"{Decimal(str(valor)).quantize(Decimal('0.01')):.2f}"
    except InvalidOperation:
        return None


def _decimal(valor, exponente: str) -> Optional[Decimal]:
    if valor is None or valor == "":
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal(exponente))
    except InvalidOperation:
        return None


def _entero(valor) -> Optional[int]:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _limpiar_texto_de_rocketfy(texto: Optional[str]) -> str:
    """La descripción de Rocketfy puede traer HTML y espacios de sobra. Se deja
    como texto plano para usarla de punto de partida (la persona la revisa)."""
    if not texto:
        return ""
    sin_etiquetas = re.sub(r"<[^>]+>", " ", str(texto))
    plano = re.sub(r"\s+", " ", html.unescape(sin_etiquetas)).strip()
    if len(plano) > LARGO_MAXIMO_DESCRIPCION_ROCKETFY:
        plano = plano[: LARGO_MAXIMO_DESCRIPCION_ROCKETFY - 1].rstrip() + "…"
    return plano


def _valor_para_historial(valor):
    if isinstance(valor, str) and len(valor) > LARGO_MAXIMO_VALOR_EN_HISTORIAL:
        return valor[: LARGO_MAXIMO_VALOR_EN_HISTORIAL - 1] + "…"
    return valor


class ProductosBotService:
    def __init__(self, client=None, repo=None, monitoreo_repo=None, ajustes_service=None):
        self._client = client
        self._repo = repo or ProductoBotGestionRepository()
        self._monitoreo = monitoreo_repo or SkuMonitoreadoRepository()
        self._ajustes = ajustes_service or AjustesService()

    @property
    def _rocketfy(self):
        # Perezoso: listar la gestión no necesita armar el cliente HTTP.
        if self._client is None:
            self._client = get_rocketfy_client()
        return self._client

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    def listar(self, incluir_archivados: bool = False) -> List[ProductoBotResumenDTO]:
        return [self._a_resumen(fila) for fila in self._repo.listar(incluir_archivados)]

    def obtener_detalle(self, sku: str) -> ProductoBotDetalleDTO:
        return self._a_detalle(self._obtener_o_error(sku))

    # ------------------------------------------------------------------
    # Crear y editar
    # ------------------------------------------------------------------
    def crear_borrador(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        sku = (sku or "").strip()
        if not sku or "/" in sku:
            raise SkuInvalidoError("El SKU no puede estar vacío ni contener '/'.")

        producto = self._buscar_en_rocketfy(sku)
        if producto is None:
            raise SkuNoExisteEnRocketfyError(f"El SKU '{sku}' no existe en el catálogo de Rocketfy.")

        # La coincidencia es exacta (sin distinguir mayúsculas), así que si el
        # SKU tecleado no traía '/', el de Rocketfy tampoco.
        sku_real = str(producto["sku"]).strip()

        if self._repo.obtener(sku_real) is not None:
            # (La base también lo impide con una restricción UNIQUE; esto da el
            # mensaje claro sin esperar al error.)
            raise ProductoBotYaExisteError(
                f"Ya existe un producto con el SKU '{sku_real}': ábrelo desde la lista en vez de crearlo otra vez."
            )

        datos = self._datos_de_rocketfy(producto)
        # Precio inicial: el sugerido por Rocketfy, o el costo si no hay. Es solo
        # un punto de partida; el borrador no se vende hasta que la persona lo
        # confirme y publique (y no puede quedar por debajo del piso).
        precio_inicial = datos["precio_sugerido_rocketfy"] or datos["costo_rocketfy"] or Decimal("0.00")

        fila = self._repo.crear_borrador(
            sku=sku_real,
            nombre=str(producto.get("name") or sku_real).strip(),
            descripcion=_limpiar_texto_de_rocketfy(producto.get("description")),
            precio=precio_inicial,
            # Decisión de arranque: solo contraentrega (la transferencia obliga a una persona a verificar el comprobante).
            metodos_pago_aceptados="contraentrega",
            datos_rocketfy=datos,
        )
        self._repo.registrar_historial(sku_real, "creado", usuario, {"desde": "rocketfy"})
        return self._a_detalle(fila)

    def editar(self, sku: str, cambios: Dict[str, Any], usuario: Optional[str]) -> ProductoBotDetalleDTO:
        actual = self._obtener_o_error(sku)
        if actual["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede editar: restáuralo primero.")

        nuevos = {campo: valor for campo, valor in cambios.items() if actual.get(campo) != valor}
        if not nuevos:
            return self._a_detalle(actual)

        if actual["estado"] == "activo":
            # Un producto que Victoria está vendiendo no puede quedar peor por
            # una edición. Se bloquea solo lo que la edición EMPEORA: si ya
            # tenía un problema de antes, otras ediciones no quedan bloqueadas.
            envio = self._envio_para_piso()
            antes = set(bloqueos_de_contenido(actual, envio))
            despues = bloqueos_de_contenido({**actual, **nuevos}, envio)
            empeora = [b for b in despues if b not in antes]
            if empeora:
                raise PublicacionBloqueadaError(empeora)

        fila = self._repo.actualizar_campos(actual["sku"], nuevos)
        self._repo.registrar_historial(
            actual["sku"],
            "editado",
            usuario,
            {
                campo: [_valor_para_historial(actual.get(campo)), _valor_para_historial(valor)]
                for campo, valor in nuevos.items()
            },
        )
        return self._a_detalle(fila)

    def actualizar_desde_rocketfy(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        actual = self._obtener_o_error(sku)
        producto = self._buscar_en_rocketfy(actual["sku"])
        if producto is None:
            raise SkuNoExisteEnRocketfyError(f"El SKU '{actual['sku']}' ya no existe en el catálogo de Rocketfy.")

        datos = self._datos_de_rocketfy(producto)
        fila = self._repo.guardar_datos_rocketfy(actual["sku"], datos)

        cambios = {}
        for clave in ("costo_rocketfy", "precio_sugerido_rocketfy"):
            if actual.get(clave) != datos[clave]:
                cambios[clave] = [_dinero(actual.get(clave)), _dinero(datos[clave])]
        if cambios:
            self._repo.registrar_historial(actual["sku"], "actualizado_rocketfy", usuario, cambios)
        return self._a_detalle(fila)

    # ------------------------------------------------------------------
    # Precio (Fase C)
    # ------------------------------------------------------------------
    def recomendar_precio(
        self, sku: str, precio: Optional[Decimal] = None, competencia: Optional[Decimal] = None
    ) -> RecomendacionPrecioDTO:
        """Calcula los tres niveles de precio con los ajustes del dueño y, si se
        pasa `precio`, evalúa cuánto se gana con ese precio (sin guardar nada).
        `competencia` sustituye al precio de la competencia guardado (para ver
        el efecto de lo que se está tecleando antes de guardarlo)."""
        fila = self._obtener_o_error(sku)
        ajustes = self._ajustes.obtener_ajustes()
        costo = _decimal(fila.get("costo_rocketfy"), "0.01")
        sugerido = _decimal(fila.get("precio_sugerido_rocketfy"), "0.01")
        if competencia is None:
            competencia = _decimal(fila.get("precio_competencia"), "0.01")

        resultado = recomendar(costo, sugerido, ajustes, precio_evaluado=precio, precio_competencia=competencia)
        ev = resultado.evaluacion
        return RecomendacionPrecioDTO(
            ajustes_confirmados=ajustes.confirmado,
            costo=_dinero(costo),
            piso=_dinero(resultado.piso),
            envio_estimado=_dinero(ajustes.envio_estimado),
            otros_costos_fijos=_dinero(ajustes.otros_costos_fijos),
            otros_costos_pct=f"{ajustes.otros_costos_pct:.2f}",
            margen_minimo_pct=f"{ajustes.margen_minimo_pct:.2f}",
            margen_objetivo_pct=f"{ajustes.margen_objetivo_pct:.2f}",
            precio_sugerido=_dinero(sugerido),
            precio_competencia=_dinero(competencia),
            niveles=[
                NivelPrecioDTO(
                    clave=n.clave,
                    nombre=n.nombre,
                    precio=_dinero(n.precio),
                    ganancia=_dinero(n.ganancia),
                    margen_pct=str(n.margen_pct),
                )
                for n in resultado.niveles
            ],
            evaluacion=(
                EvaluacionPrecioDTO(
                    precio=_dinero(ev.precio),
                    ganancia=_dinero(ev.ganancia),
                    margen_pct=str(ev.margen_pct),
                    bajo_piso=ev.bajo_piso,
                    bajo_margen_minimo=ev.bajo_margen_minimo,
                )
                if ev is not None
                else None
            ),
            avisos=resultado.avisos,
        )

    def _envio_para_piso(self) -> Optional[Decimal]:
        return envio_para_piso(self._ajustes.obtener_ajustes())

    # ------------------------------------------------------------------
    # Estados
    # ------------------------------------------------------------------
    def publicar(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        return self._transicion(sku, "publicar", usuario)

    def reanudar(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        return self._transicion(sku, "reanudar", usuario)

    def pausar(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        return self._transicion(sku, "pausar", usuario)

    def archivar(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        return self._transicion(sku, "archivar", usuario)

    def restaurar(self, sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        return self._transicion(sku, "restaurar", usuario)

    def _transicion(self, sku: str, accion: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        desde, destino, accion_historial = _TRANSICIONES[accion]
        actual = self._obtener_o_error(sku)
        if actual["estado"] not in desde:
            raise TransicionInvalidaError(
                f"No se puede {accion} un producto que está en estado '{actual['estado']}'."
            )

        if destino == "activo":
            actual = self._verificar_antes_de_activar(actual)

        fila = self._repo.cambiar_estado(actual["sku"], destino, usuario)
        self._repo.registrar_historial(actual["sku"], accion_historial, usuario, {"estado": [actual["estado"], destino]})

        if destino == "activo":
            self._asegurar_vigilado(actual["sku"])
        return self._a_detalle(fila)

    def _verificar_antes_de_activar(self, actual: dict) -> dict:
        """Consulta Rocketfy EN VIVO, refresca la foto guardada y exige que el
        producto cumpla lo mínimo. Si Rocketfy falla, la excepción sube (502):
        no se publica sin confirmarlo."""
        en_vivo = self._buscar_en_rocketfy(actual["sku"])
        if en_vivo is not None:
            actual = self._repo.guardar_datos_rocketfy(actual["sku"], self._datos_de_rocketfy(en_vivo))
        verificacion = verificar_producto(
            actual,
            existe_en_rocketfy=en_vivo is not None,
            stock=_entero(en_vivo.get("stock")) if en_vivo is not None else None,
            envio_para_piso=self._envio_para_piso(),
        )
        if verificacion.bloqueos:
            raise PublicacionBloqueadaError(verificacion.bloqueos)
        return actual

    def _asegurar_vigilado(self, sku: str) -> None:
        """Al activar un producto se vigila su stock (alertas en Incidencias),
        sin pisar un umbral que la persona ya hubiera puesto. Es un extra: si
        falla no debe deshacer la publicación."""
        try:
            ya_vigilados = {m["sku"] for m in self._monitoreo.listar(solo_activos=True)}
            if sku not in ya_vigilados:
                self._monitoreo.upsert(sku, UMBRAL_STOCK_AL_PUBLICAR)
        except Exception:
            logger.exception("No se pudo agregar '%s' a Vigilados al publicar (la publicación sigue)", sku)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _obtener_o_error(self, sku: str) -> dict:
        fila = self._repo.obtener((sku or "").strip())
        if fila is None:
            raise ProductoBotNoEncontradoError(f"No existe un producto con el SKU '{sku}'.")
        return fila

    def consultar_rocketfy(self, sku: str) -> Optional[dict]:
        """El producto de Rocketfy con ese SKU EXACTO (en vivo), o None si no
        existe. Lo usan otros servicios (p. ej. la redacción con IA)."""
        return self._buscar_en_rocketfy(sku)

    def _buscar_en_rocketfy(self, sku: str) -> Optional[dict]:
        """Coincidencia EXACTA de SKU (sin distinguir mayúsculas): la búsqueda
        `q` de Rocketfy también devuelve productos parecidos."""
        contenido = self._rocketfy.listar_productos(q=sku)
        objetivo = sku.strip().upper()
        for producto in contenido.get("data", []):
            if str(producto.get("sku", "")).strip().upper() == objetivo:
                return producto
        return None

    @staticmethod
    def _datos_de_rocketfy(producto: dict) -> Dict[str, Any]:
        return {
            "rocketfy_product_id": _entero(producto.get("id")),
            "costo_rocketfy": _decimal(producto.get("price"), "0.01"),
            "precio_sugerido_rocketfy": _decimal(producto.get("suggested_price"), "0.01"),
            "stock_ultimo": _entero(producto.get("stock")),
            "peso_kg": _decimal(producto.get("weight"), "0.001"),
            "imagen_url": (producto.get("image_url") or None),
        }

    @staticmethod
    def _a_resumen(fila: dict) -> ProductoBotResumenDTO:
        return ProductoBotResumenDTO(
            sku=fila["sku"],
            nombre=fila["nombre"],
            estado=fila["estado"],
            precio=_dinero(fila["precio"]),
            costo_rocketfy=_dinero(fila.get("costo_rocketfy")),
            stock_ultimo=fila.get("stock_ultimo"),
            max_unidades_por_pedido=fila["max_unidades_por_pedido"],
            imagen_url=fila.get("imagen_url"),
            publicado_en=_iso(fila.get("publicado_en")),
            actualizado_en=_iso(fila.get("actualizado_en")),
        )

    def _avisos_de_la_lista(self, fila: dict) -> List[str]:
        """Los avisos de la lista de verificación al publicar que necesitan más
        que la ficha (plan de gestión de productos, sección 9): el margen con
        los ajustes del dueño y si se probó una compra completa con Victoria.
        Son para un producto que todavía no se vende o que se está revisando: no
        bloquean nada. Si falla la consulta, la ficha se muestra igual."""
        avisos: List[str] = []
        try:
            ajustes = self._ajustes.obtener_ajustes()
            costo = _decimal(fila.get("costo_rocketfy"), "0.01")
            precio = _decimal(fila.get("precio"), "0.01")
            # Con ajustes de partida (sin confirmar) el margen sería inventado: no se avisa.
            if ajustes.confirmado and costo is not None and precio is not None and precio > 0:
                ganancia = ganancia_por_unidad(precio, costo, ajustes)
                margen = margen_pct(precio, ganancia)
                if ganancia <= 0:
                    avisos.append(f"Con este precio pierdes ${-ganancia:.2f} por unidad (con tu envío estimado).")
                elif margen < ajustes.margen_minimo_pct:
                    avisos.append(
                        f"Tu margen ({margen} %) está por debajo del mínimo que definiste ({ajustes.margen_minimo_pct} %)."
                    )

            if fila.get("estado") in ("borrador", "listo"):
                # Los borradores de la IA no se guardan, así que no se puede saber qué alertas
                # quedaron sin resolver: lo que sí se sabe es si se usó la IA para esta ficha.
                if self._repo.ultima_fecha_de(fila["sku"], "redactado_ia") is not None:
                    avisos.append(
                        "Parte de la ficha se redactó con IA: verifica que cada dato sea cierto antes de publicar "
                        "(la IA puede equivocarse)."
                    )
                simulada = self._repo.ultima_fecha_de(fila["sku"], ACCION_SIMULACION_COMPLETA)
                editada = self._repo.ultima_fecha_de(fila["sku"], "editado")
                if simulada is None:
                    avisos.append(
                        "Todavía no probaste una compra completa con Victoria: usa «Probar con Victoria» antes de publicar."
                    )
                elif editada is not None and editada > simulada:
                    avisos.append(
                        "Cambiaste la ficha después de tu última compra de prueba con Victoria: conviene repetirla."
                    )
        except Exception:
            logger.exception("No se pudieron calcular los avisos de la lista de verificación de '%s'", fila.get("sku"))
        return avisos

    def _a_detalle(self, fila: dict) -> ProductoBotDetalleDTO:
        # Sobre lo último guardado de Rocketfy, sin llamar a la red.
        verificacion = verificar_producto(fila, envio_para_piso=self._envio_para_piso())
        verificacion.avisos.extend(self._avisos_de_la_lista(fila))
        peso = fila.get("peso_kg")
        return ProductoBotDetalleDTO(
            sku=fila["sku"],
            nombre=fila["nombre"],
            estado=fila["estado"],
            precio=_dinero(fila["precio"]),
            costo_rocketfy=_dinero(fila.get("costo_rocketfy")),
            precio_sugerido_rocketfy=_dinero(fila.get("precio_sugerido_rocketfy")),
            stock_ultimo=fila.get("stock_ultimo"),
            stock_actualizado_en=_iso(fila.get("stock_actualizado_en")),
            peso_kg=f"{peso:.3f}" if peso is not None else None,
            imagen_url=fila.get("imagen_url"),
            rocketfy_product_id=fila.get("rocketfy_product_id"),
            descripcion=fila["descripcion"],
            variantes=fila.get("variantes"),
            tiempo_entrega=fila["tiempo_entrega"],
            metodos_pago=metodos_de_pago(fila.get("metodos_pago_aceptados")),
            preguntas_frecuentes=fila.get("preguntas_frecuentes"),
            temas_no_responder=fila.get("temas_no_responder"),
            max_unidades_por_pedido=fila["max_unidades_por_pedido"],
            notas_internas=fila.get("notas_internas"),
            publicado_en=_iso(fila.get("publicado_en")),
            publicado_por=fila.get("publicado_por"),
            creado_en=_iso(fila.get("creado_en")),
            actualizado_en=_iso(fila.get("actualizado_en")),
            verificacion=VerificacionDTO(bloqueos=verificacion.bloqueos, avisos=verificacion.avisos),
            precio_competencia=_dinero(fila.get("precio_competencia")),
            historial=[
                HistorialDTO(
                    accion=h["accion"], usuario=h["usuario"], cambios=h["cambios"], creado_en=_iso(h["creado_en"])
                )
                for h in self._repo.listar_historial(fila["sku"])
            ],
        )
