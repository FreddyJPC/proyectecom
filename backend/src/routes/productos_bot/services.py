"""
Gestión de los productos que Victoria puede vender, desde el dashboard (Fase B
del plan de gestión de productos, docs/PLAN_GESTION_PRODUCTOS.md).

Reglas que este servicio hace cumplir:
- Un producto de ROCKETFY nace SIEMPRE como borrador desde un SKU que existe
  EXACTAMENTE igual en Rocketfy (se usa el SKU tal como lo escribe Rocketfy, no
  como lo tecleó la persona): un SKU inventado fue la causa del primer fallo
  real de una venta.
- Un producto PROPIO (ADR-012) lo crea el dueño con todos sus datos y su SKU lo
  genera el sistema (`PROP-0001`…): no existe en Rocketfy, así que nada de lo que
  depende de Rocketfy (verificar el SKU, el stock en vivo, la sincronización
  horaria) se le aplica; su stock lo lleva la propia app.
- Nada llega a Victoria hasta pulsar publicar (o reanudar). Si es de Rocketfy,
  para eso se vuelve a consultar Rocketfy EN VIVO. Si Rocketfy no responde, no
  se publica a ciegas (a diferencia de la venta, que sí sigue sin saber el stock).
- `estado` y `activo` cambian juntos en un único lugar
  (ProductoBotGestionRepository.cambiar_estado).
- Todo cambio queda en el historial con el correo de quien lo hizo.
"""
import dataclasses
import html
import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from src.config.parametros import parametros
from src.config.settings import load_settings
from src.integrations.rocketfy import RECAUDO_MINIMO_CONTRAENTREGA, get_rocketfy_client
from src.integrations.rocketfy.imagenes import url_de_imagen
from src.routes.ajustes.services import AjustesService
from src.routes.categorias.repository import CategoriaRepository
from src.routes.entregas.logica import limpiar_y_validar
from src.routes.entregas.repository import EntregaRepository
from src.routes.imagenes.logica import MAXIMO_POR_PRODUCTO, RutaDeImagenInvalida, url_publica, validar_ruta
from src.routes.imagenes.repository import ImagenRepository, ImagenYaRegistradaError
from src.routes.productos.exceptions import SkuNoExisteEnRocketfyError
from src.routes.productos.repository import SkuMonitoreadoRepository
from src.routes.ventas.origen import controla_su_stock, costo_unitario, es_de_cierre_manual, flete_estimado

from .calculadora import envio_para_piso, ganancia_por_unidad, margen_en_riesgo, margen_pct, recomendar
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
    DatosDeProductoInvalidosError,
    ProductoBotNoEncontradoError,
    ProductoBotYaExisteError,
    PublicacionBloqueadaError,
    SkuInvalidoError,
    TransicionInvalidaError,
)
from .repository import ACCION_SIMULACION_COMPLETA, COLUMNAS_SOLO_DE_PRODUCTO_PROPIO, ProductoBotGestionRepository
from .verificacion import bloqueos_de_contenido, metodos_de_pago, verificar_producto

logger = logging.getLogger(__name__)

# Ventana de «pedidos por producto» en la lista y estados que muestran la insignia de margen.
DIAS_DE_PEDIDOS_EN_LA_LISTA = 30
ESTADOS_CON_INSIGNIA_DE_MARGEN = ("listo", "activo", "pausado", "agotado")
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
    def __init__(
        self, client=None, repo=None, monitoreo_repo=None, ajustes_service=None, entregas_repo=None, categorias_repo=None,
        imagenes_repo=None,
    ):
        self._client = client
        self._repo = repo or ProductoBotGestionRepository()
        self._monitoreo = monitoreo_repo or SkuMonitoreadoRepository()
        self._ajustes = ajustes_service or AjustesService()
        self._entregas = entregas_repo or EntregaRepository()
        self._categorias = categorias_repo or CategoriaRepository()
        self._imagenes = imagenes_repo or ImagenRepository()

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
        filas = self._repo.listar(incluir_archivados)
        pedidos = self._pedidos_por_sku()
        ajustes = self._ajustes_para_el_margen()
        return [
            self._a_resumen(
                fila,
                pedidos_30d=pedidos.get(str(fila["sku"]).upper(), 0),
                con_margen_en_riesgo=self._tiene_margen_en_riesgo(fila, ajustes),
            )
            for fila in filas
        ]

    def _pedidos_por_sku(self) -> Dict[str, int]:
        """Un dato extra de la lista: si falla la consulta, la lista se muestra igual."""
        try:
            return self._repo.contar_pedidos_por_sku(DIAS_DE_PEDIDOS_EN_LA_LISTA)
        except Exception:
            logger.exception("No se pudieron contar los pedidos por producto (la lista sigue)")
            return {}

    def _ajustes_para_el_margen(self):
        try:
            return self._ajustes.obtener_ajustes()
        except Exception:
            logger.exception("No se pudieron leer los ajustes para el margen (la lista sigue)")
            return None

    @classmethod
    def _tiene_margen_en_riesgo(cls, fila: dict, ajustes) -> bool:
        """Solo para productos que ya se venden o se pueden reanudar: un borrador
        todavía está en preparación (su margen sale en la lista de verificación)."""
        if ajustes is None or fila["estado"] not in ESTADOS_CON_INSIGNIA_DE_MARGEN:
            return False
        precio = _decimal(fila.get("precio"), "0.01")
        return margen_en_riesgo(precio, costo_unitario(fila), cls._ajustes_del_producto(fila, ajustes)) is not None

    @staticmethod
    def _ajustes_del_producto(fila: dict, ajustes):
        """Los ajustes de precios con el flete de ESTE producto en lugar del general (ADR-012): el flete
        que el dueño anotó para el producto, o el general si el envío va incluido en el precio, o cero si
        el envío se cobra aparte. Si el dueño anotó el flete del producto, cuenta como confirmado."""
        flete = flete_estimado(fila, ajustes.envio_estimado)
        propio = _decimal(fila.get("costo_flete_estimado"), "0.01") is not None
        return dataclasses.replace(ajustes, envio_estimado=flete, confirmado=ajustes.confirmado or propio)

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

    def crear_propio(self, datos: Dict[str, Any], entregas: List[Dict[str, Any]], usuario: Optional[str]) -> ProductoBotDetalleDTO:
        """Un producto PROPIO (ADR-012): lo crea el dueño con todos sus datos. Nace como borrador y
        Victoria no lo ve hasta que se publique. El SKU lo genera el sistema (`PROP-0001`…)."""
        limpias, errores = limpiar_y_validar(entregas)
        errores += self._errores_de_categoria(datos.get("categoria_id"))
        if errores:
            raise DatosDeProductoInvalidosError(errores)
        fila = self._repo.crear_propio(datos, limpias)
        self._repo.registrar_historial(fila["sku"], "creado", usuario, {"desde": "propio"})
        return self._a_detalle(fila)

    def _errores_de_categoria(self, categoria_id: Optional[int]) -> List[str]:
        if categoria_id is None:
            return []
        categoria = self._categorias.obtener(categoria_id)
        if categoria is None or not categoria["activo"]:
            return ["Esa categoría no existe o está desactivada."]
        return []

    def _exigir_que_no_empeore(self, actual: dict, nuevo: dict, entregas_antes: int, entregas_despues: int) -> None:
        """Un producto que Victoria está vendiendo no puede quedar peor por una edición. Se bloquea solo
        lo que la edición EMPEORA: si ya tenía un problema de antes, otras ediciones no quedan bloqueadas."""
        antes = set(bloqueos_de_contenido(actual, self._envio_para_piso(actual), entregas_antes))
        despues = bloqueos_de_contenido(nuevo, self._envio_para_piso(nuevo), entregas_despues)
        empeora = [b for b in despues if b not in antes]
        if empeora:
            raise PublicacionBloqueadaError(empeora)

    def _cantidad_de_entregas_activas(self, sku: str) -> int:
        return len(self._entregas.listar(sku, solo_activas=True))

    def editar(self, sku: str, cambios: Dict[str, Any], usuario: Optional[str]) -> ProductoBotDetalleDTO:
        actual = self._obtener_o_error(sku)
        if actual["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede editar: restáuralo primero.")

        propio = es_de_cierre_manual(actual)
        solo_propios = sorted(set(cambios) & COLUMNAS_SOLO_DE_PRODUCTO_PROPIO)
        if solo_propios and not propio:
            raise DatosDeProductoInvalidosError(
                ["El costo y el stock de un producto de Rocketfy vienen de Rocketfy: solo los productos propios se editan a mano."]
            )
        if "categoria_id" in cambios:
            errores = self._errores_de_categoria(cambios["categoria_id"])
            if errores:
                raise DatosDeProductoInvalidosError(errores)

        nuevos = {campo: valor for campo, valor in cambios.items() if actual.get(campo) != valor}
        if not nuevos:
            return self._a_detalle(actual)

        combinado = {**actual, **nuevos}
        if propio and combinado.get("controla_stock") and combinado.get("stock_ultimo") is None:
            raise DatosDeProductoInvalidosError(["Indica cuántas unidades tienes, o desactiva el control de stock."])

        if actual["estado"] == "activo":
            entregas = self._cantidad_de_entregas_activas(actual["sku"])
            self._exigir_que_no_empeore(actual, combinado, entregas, entregas)

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
        if es_de_cierre_manual(actual):
            raise TransicionInvalidaError("Un producto propio no está en Rocketfy: sus datos los editas tú.")
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
        ajustes = self._ajustes_del_producto(fila, self._ajustes.obtener_ajustes())
        costo = costo_unitario(fila)
        sugerido = _decimal(fila.get("precio_sugerido_rocketfy"), "0.01")
        if competencia is None:
            competencia = _decimal(fila.get("precio_competencia"), "0.01")

        resultado = recomendar(
            costo, sugerido, ajustes, precio_evaluado=precio, precio_competencia=competencia,
            recaudo_minimo=Decimal("0.00") if es_de_cierre_manual(fila) else RECAUDO_MINIMO_CONTRAENTREGA,
        )
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

    def _envio_para_piso(self, fila: dict) -> Optional[Decimal]:
        """El envío que cuenta para BLOQUEAR una publicación de ESTE producto (ver `envio_para_piso`)."""
        return envio_para_piso(self._ajustes_del_producto(fila, self._ajustes.obtener_ajustes()))

    # ------------------------------------------------------------------
    # Envío por producto (ADR-012)
    # ------------------------------------------------------------------
    def guardar_entregas(self, sku: str, entregas: List[Dict[str, Any]], usuario: Optional[str]) -> ProductoBotDetalleDTO:
        """Reemplaza TODAS las opciones de entrega del producto por estas. Si el producto está a la venta y
        cobra el envío aparte, no puede quedarse sin ninguna."""
        actual = self._obtener_o_error(sku)
        if actual["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede editar: restáuralo primero.")
        limpias, errores = limpiar_y_validar(entregas)
        if errores:
            raise DatosDeProductoInvalidosError(errores)
        if actual["estado"] == "activo":
            antes = self._cantidad_de_entregas_activas(actual["sku"])
            despues = len([o for o in limpias if o["activo"]])
            self._exigir_que_no_empeore(actual, actual, antes, despues)
        self._entregas.reemplazar(actual["sku"], limpias)
        self._repo.registrar_historial(actual["sku"], "editado", usuario, {"entregas": [len(limpias), "opciones"]})
        return self._a_detalle(self._repo.obtener(actual["sku"]))

    # ------------------------------------------------------------------
    # Fotos (ADR-012, entrega 2)
    # ------------------------------------------------------------------
    def registrar_imagen(self, sku: str, ruta: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        """La app ya subió el archivo al bucket; aquí se anota en la galería del producto. La URL la arma el
        servidor a partir de la ruta: no se acepta una escrita por el cliente."""
        actual = self._obtener_o_error(sku)
        if actual["estado"] == "archivado":
            raise TransicionInvalidaError("Un producto archivado no se puede editar: restáuralo primero.")
        try:
            ruta = validar_ruta(actual["sku"], ruta)
        except RutaDeImagenInvalida as exc:
            raise DatosDeProductoInvalidosError([str(exc)]) from exc
        if len(self._imagenes.listar(actual["sku"])) >= MAXIMO_POR_PRODUCTO:
            raise DatosDeProductoInvalidosError([f"Máximo {MAXIMO_POR_PRODUCTO} fotos por producto: quita alguna antes de subir otra."])
        try:
            self._imagenes.agregar(actual["sku"], url_publica(load_settings().supabase_url, ruta), ruta, usuario)
        except ImagenYaRegistradaError as exc:
            raise DatosDeProductoInvalidosError([str(exc)]) from exc
        self._repo.registrar_historial(actual["sku"], "editado", usuario, {"fotos": ["+1"]})
        return self._a_detalle(self._repo.obtener(actual["sku"]))

    def quitar_imagen(self, sku: str, imagen_id: int, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        actual = self._obtener_o_error(sku)
        if self._imagenes.quitar(actual["sku"], imagen_id) is None:
            raise ProductoBotNoEncontradoError("Esa foto no existe en este producto.")
        self._repo.registrar_historial(actual["sku"], "editado", usuario, {"fotos": ["-1"]})
        return self._a_detalle(self._repo.obtener(actual["sku"]))

    def ordenar_imagenes(self, sku: str, ids: List[int], usuario: Optional[str]) -> ProductoBotDetalleDTO:
        """Deja las fotos en este orden (la primera es la principal). Tiene que incluir EXACTAMENTE las que hay."""
        actual = self._obtener_o_error(sku)
        existentes = {i["id"] for i in self._imagenes.listar(actual["sku"])}
        if len(ids) != len(set(ids)) or set(ids) != existentes:
            raise DatosDeProductoInvalidosError(["El orden debe incluir todas las fotos del producto, una sola vez cada una."])
        self._imagenes.reordenar(actual["sku"], ids)
        return self._a_detalle(self._repo.obtener(actual["sku"]))

    def copiar_entregas(self, sku: str, desde_sku: str, usuario: Optional[str]) -> ProductoBotDetalleDTO:
        """Copia el envío de otro producto (para no repetir los mismos datos en cada ficha)."""
        origen = self._obtener_o_error(desde_sku)
        copiadas = [
            {k: v for k, v in o.items() if k not in ("id", "producto_sku", "orden")}
            for o in self._entregas.listar(origen["sku"])
        ]
        return self.guardar_entregas(sku, copiadas, usuario)

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

        if destino == "activo" and not es_de_cierre_manual(actual):
            self._asegurar_vigilado(actual["sku"])
        return self._a_detalle(fila)

    def _verificar_antes_de_activar(self, actual: dict) -> dict:
        """Si es de Rocketfy, consulta Rocketfy EN VIVO, refresca la foto guardada y exige que el
        producto cumpla lo mínimo. Si Rocketfy falla, la excepción sube (502):
        no se publica sin confirmarlo. Un producto propio no se consulta a Rocketfy: se verifica con lo
        que tiene guardado (precio, stock propio, envío definido…)."""
        entregas = self._cantidad_de_entregas_activas(actual["sku"])
        if es_de_cierre_manual(actual):
            verificacion = verificar_producto(
                actual,
                envio_para_piso=self._envio_para_piso(actual),
                umbral_stock_bajo=parametros.valor("stock.umbral_bajo"),
                entregas_activas=entregas,
            )
            if verificacion.bloqueos:
                raise PublicacionBloqueadaError(verificacion.bloqueos)
            return actual
        en_vivo = self._buscar_en_rocketfy(actual["sku"])
        if en_vivo is not None:
            actual = self._repo.guardar_datos_rocketfy(actual["sku"], self._datos_de_rocketfy(en_vivo))
        verificacion = verificar_producto(
            actual,
            existe_en_rocketfy=en_vivo is not None,
            stock=_entero(en_vivo.get("stock")) if en_vivo is not None else None,
            envio_para_piso=self._envio_para_piso(actual),
            umbral_stock_bajo=parametros.valor("stock.umbral_bajo"),
            entregas_activas=entregas,
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
                self._monitoreo.upsert(sku, parametros.valor("stock.umbral_bajo"))
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
            "imagen_url": url_de_imagen(producto.get("image_url")),
        }

    @staticmethod
    def _a_resumen(fila: dict, pedidos_30d: int = 0, con_margen_en_riesgo: bool = False) -> ProductoBotResumenDTO:
        return ProductoBotResumenDTO(
            sku=fila["sku"],
            nombre=fila["nombre"],
            estado=fila["estado"],
            precio=_dinero(fila["precio"]),
            costo_rocketfy=_dinero(fila.get("costo_rocketfy")),
            stock_ultimo=fila.get("stock_ultimo"),
            max_unidades_por_pedido=fila["max_unidades_por_pedido"],
            imagen_url=url_de_imagen(fila.get("imagen_url")),
            publicado_en=_iso(fila.get("publicado_en")),
            actualizado_en=_iso(fila.get("actualizado_en")),
            pedidos_30d=pedidos_30d,
            margen_en_riesgo=con_margen_en_riesgo,
            proveedor=fila.get("proveedor_clave") or "rocketfy",
            proveedor_nombre=fila.get("proveedor_nombre") or "Rocketfy",
            categoria=fila.get("categoria_nombre"),
            controla_stock=controla_su_stock(fila) if es_de_cierre_manual(fila) else True,
            envio_incluido=bool(fila.get("envio_incluido", True)),
        )

    def _avisos_de_la_lista(self, fila: dict) -> List[str]:
        """Los avisos de la lista de verificación al publicar que necesitan más
        que la ficha (plan de gestión de productos, sección 9): el margen con
        los ajustes del dueño y si se probó una compra completa con Victoria.
        Son para un producto que todavía no se vende o que se está revisando: no
        bloquean nada. Si falla la consulta, la ficha se muestra igual."""
        avisos: List[str] = []
        try:
            ajustes = self._ajustes_del_producto(fila, self._ajustes.obtener_ajustes())
            costo = costo_unitario(fila)
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
        entregas = self._entregas.listar(fila["sku"])
        verificacion = verificar_producto(
            fila,
            envio_para_piso=self._envio_para_piso(fila),
            umbral_stock_bajo=parametros.valor("stock.umbral_bajo"),
            entregas_activas=len([e for e in entregas if e["activo"]]),
        )
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
            imagen_url=url_de_imagen(fila.get("imagen_url")),
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
            proveedor=fila.get("proveedor_clave") or "rocketfy",
            proveedor_nombre=fila.get("proveedor_nombre") or "Rocketfy",
            categoria_id=fila.get("categoria_id"),
            categoria=fila.get("categoria_nombre"),
            costo_propio=_dinero(fila.get("costo_propio")),
            controla_stock=controla_su_stock(fila) if es_de_cierre_manual(fila) else True,
            envio_incluido=bool(fila.get("envio_incluido", True)),
            costo_flete_estimado=_dinero(fila.get("costo_flete_estimado")),
            entregas=[self._entrega_a_dto(e) for e in entregas],
            imagenes=[
                {"id": i["id"], "url": i["url"], "storage_path": i["storage_path"], "orden": i["orden"]}
                for i in self._imagenes.listar(fila["sku"])
            ],
        )

    @staticmethod
    def _entrega_a_dto(entrega: dict) -> dict:
        return {
            "id": entrega["id"],
            "nombre": entrega["nombre"],
            "tipo": entrega["tipo"],
            "costo_cliente": _dinero(entrega["costo_cliente"]),
            "costo_negocio": _dinero(entrega.get("costo_negocio")),
            "cantones": list(entrega.get("cantones") or []),
            "provincias": list(entrega.get("provincias") or []),
            "resto_del_pais": bool(entrega.get("resto_del_pais")),
            "direccion_retiro": entrega.get("direccion_retiro"),
            "tiempo_entrega": entrega.get("tiempo_entrega"),
            "activo": bool(entrega.get("activo", True)),
        }
