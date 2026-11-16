"""
Validación de lo que el dueño configura desde el panel (ADR-017): reglas de precio de un producto y ofertas.
Pura: recibe lo que llegó por la API y lo que ya se sabe (producto, costos, ajustes) y devuelve lo que se puede guardar, los
errores (por campo, en español) y los avisos de margen.

El piso de margen (regla 2): un precio especial que deja la venta bajo el margen mínimo NO se guarda, salvo que el dueño lo
confirme a propósito (`confirmarBajoMargen` / «vender bajo el margen» en una oferta).
"""
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from .reglas import TIPOS_REGATEO, TIPOS_TRANSFERENCIA, AjustesPiso, dinero, piso_del_pedido

MAXIMO_ESCALAS = 6
LARGO_NOMBRE = 120
LARGO_TEXTO = 1000


@dataclass
class Resultado:
    datos: Dict[str, Any] = field(default_factory=dict)
    escalas: List[Dict[str, Any]] = field(default_factory=list)
    items: List[Dict[str, Any]] = field(default_factory=list)
    errores: Dict[str, List[str]] = field(default_factory=dict)
    bajo_margen: List[str] = field(default_factory=list)

    def error(self, campo: str, mensaje: str) -> None:
        self.errores.setdefault(campo, []).append(mensaje)

    @property
    def valido(self) -> bool:
        return not self.errores


def _monto(valor) -> Optional[Decimal]:
    if valor is None or valor == "":
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise ValueError("no es un número")
    if not numero.is_finite():
        raise ValueError("no es un número")
    return dinero(numero)


def _entero(valor) -> Optional[int]:
    if valor is None or valor == "":
        return None
    if isinstance(valor, bool):
        raise ValueError("no es un número entero")
    try:
        numero = Decimal(str(valor))
    except InvalidOperation:
        raise ValueError("no es un número entero")
    if numero != numero.to_integral_value():
        raise ValueError("no es un número entero")
    return int(numero)


def _regla(r: Resultado, prefijo: str, tipo: Any, valor: Any, tipos, precio_ref: Optional[Decimal]) -> None:
    """Valida un par (tipo, valor). Sin tipo = sin regla (se borra)."""
    tipo = (tipo or None) if not isinstance(tipo, str) else (tipo.strip() or None)
    if tipo is None:
        r.datos[f"{prefijo}_tipo"] = None
        r.datos[f"{prefijo}_valor"] = None
        return
    if tipo not in tipos:
        r.error(f"{prefijo}Tipo", "Tipo no válido.")
        return
    try:
        numero = _monto(valor)
    except ValueError:
        r.error(f"{prefijo}Valor", "Escribe un número.")
        return
    if numero is None or numero <= 0:
        r.error(f"{prefijo}Valor", "Debe ser mayor que cero.")
        return
    if tipo == "porcentaje" and numero >= 100:
        r.error(f"{prefijo}Valor", "Un porcentaje debe ser menor que 100.")
        return
    if precio_ref is not None and tipo in ("precio", "monto") and numero >= precio_ref:
        mensaje = "Debe ser menor que el precio normal." if tipo == "precio" else "El descuento debe ser menor que el precio."
        r.error(f"{prefijo}Valor", mensaje)
        return
    r.datos[f"{prefijo}_tipo"] = tipo
    r.datos[f"{prefijo}_valor"] = numero


def validar_reglas_producto(entrada: Dict[str, Any], producto: Dict[str, Any], costo: Optional[Decimal], ajustes: Optional[AjustesPiso]) -> Resultado:
    """Reglas de «Precios y descuentos» de un producto. `producto` trae al menos precio, envio_incluido y max_unidades_por_pedido."""
    r = Resultado()
    precio = dinero(producto["precio"])
    _regla(r, "transferencia", entrada.get("transferenciaTipo"), entrada.get("transferenciaValor"), TIPOS_TRANSFERENCIA, precio)
    _regla(r, "regateo", entrada.get("regateoTipo"), entrada.get("regateoValor"), TIPOS_REGATEO, precio)

    try:
        unidades = _entero(entrada.get("envioGratisDesdeUnidades"))
        if unidades is not None and unidades < 1:
            r.error("envioGratisDesdeUnidades", "Debe ser 1 o más.")
        r.datos["envio_gratis_desde_unidades"] = unidades
    except ValueError:
        r.error("envioGratisDesdeUnidades", "Escribe un número entero.")
    try:
        monto = _monto(entrada.get("envioGratisDesdeMonto"))
        if monto is not None and monto <= 0:
            r.error("envioGratisDesdeMonto", "Debe ser mayor que cero.")
        r.datos["envio_gratis_desde_monto"] = monto
    except ValueError:
        r.error("envioGratisDesdeMonto", "Escribe un número.")
    if producto.get("envio_incluido", True) and (r.datos.get("envio_gratis_desde_unidades") or r.datos.get("envio_gratis_desde_monto")):
        r.error("envioGratis", "Este producto ya incluye el envío en el precio: el envío gratis no aplica.")

    escalas = entrada.get("escalas") or []
    if not isinstance(escalas, list) or len(escalas) > MAXIMO_ESCALAS:
        r.error("escalas", f"Hasta {MAXIMO_ESCALAS} precios por cantidad.")
        escalas = []
    vistas = set()
    maximo = int(producto.get("max_unidades_por_pedido") or 1)
    for i, escala in enumerate(escalas):
        try:
            cantidad = _entero((escala or {}).get("cantidad"))
            total = _monto((escala or {}).get("precioTotal"))
        except ValueError:
            r.error(f"escalas.{i}", "Cantidad y precio deben ser números.")
            continue
        if cantidad is None or cantidad < 2:
            r.error(f"escalas.{i}", "La cantidad debe ser 2 o más.")
            continue
        if cantidad in vistas:
            r.error(f"escalas.{i}", f"Ya hay un precio para {cantidad} unidades.")
            continue
        if cantidad > maximo:
            r.error(f"escalas.{i}", f"El máximo por pedido de este producto es {maximo}: sube el máximo o quita esta cantidad.")
            continue
        if total is None or total <= 0:
            r.error(f"escalas.{i}", "El precio debe ser mayor que cero.")
            continue
        if total >= precio * cantidad:
            r.error(f"escalas.{i}", f"Debe ser menor que {cantidad} × ${precio:.2f} = ${precio * cantidad:.2f}; si no, no es una rebaja.")
            continue
        vistas.add(cantidad)
        r.escalas.append({"cantidad": cantidad, "precio_total": total})
        piso = piso_del_pedido([costo * cantidad if costo is not None else None], ajustes)
        if piso is not None and total < piso:
            r.bajo_margen.append(f"{cantidad} por ${total:.2f} queda bajo tu margen mínimo (mínimo ${piso:.2f}).")
    r.escalas.sort(key=lambda e: e["cantidad"])

    piso_unidad = piso_del_pedido([costo], ajustes)
    if piso_unidad is not None and r.valido:
        tipo, valor = r.datos.get("transferencia_tipo"), r.datos.get("transferencia_valor")
        if tipo:
            con_transferencia = valor if tipo == "precio" else (precio - valor if tipo == "monto" else dinero(precio * (100 - valor) / 100))
            if con_transferencia < piso_unidad:
                r.bajo_margen.append(
                    f"El precio por transferencia (${con_transferencia:.2f}) queda bajo tu margen mínimo (mínimo ${piso_unidad:.2f})."
                )
    return r


def validar_oferta(
    entrada: Dict[str, Any],
    productos: Dict[str, Dict[str, Any]],
    costos: Dict[str, Optional[Decimal]],
    ajustes: Optional[AjustesPiso],
    es_nueva: bool,
) -> Resultado:
    """Una oferta (combo o promo). `productos`: filas de los SKU que aparecen en los ítems (con `proveedor_cierre`)."""
    r = Resultado()
    nombre = str(entrada.get("nombre") or "").strip()
    if es_nueva or "nombre" in entrada:
        if not nombre:
            r.error("nombre", "Ponle un nombre a la oferta.")
        r.datos["nombre"] = nombre[:LARGO_NOMBRE]
    for clave, campo in (("descripcion", "descripcion"), ("textoAnuncio", "texto_anuncio")):
        if clave in entrada:
            texto = str(entrada.get(clave) or "").strip()
            if len(texto) > LARGO_TEXTO:
                r.error(clave, f"Máximo {LARGO_TEXTO} caracteres.")
            r.datos[campo] = texto or None
    if es_nueva or "precio" in entrada:
        try:
            precio = _monto(entrada.get("precio"))
        except ValueError:
            precio = None
        if precio is None or precio <= 0:
            r.error("precio", "Escribe el precio total de la oferta.")
        else:
            r.datos["precio"] = precio
    for clave, campo in (("envioIncluido", "envio_incluido"), ("bajoMargenAutorizado", "bajo_margen_autorizado")):
        if clave in entrada:
            r.datos[campo] = bool(entrada.get(clave))
    if "visibilidad" in entrada:
        if entrada["visibilidad"] not in ("anuncio", "publica"):
            r.error("visibilidad", "Elige quién puede ver la oferta.")
        else:
            r.datos["visibilidad"] = entrada["visibilidad"]
    if "estado" in entrada:
        if entrada["estado"] not in ("activa", "pausada", "archivada"):
            r.error("estado", "Estado no válido.")
        else:
            r.datos["estado"] = entrada["estado"]
    for clave, campo, minimo in (("cupo", "cupo", 1), ("maximoPorCliente", "maximo_por_cliente", 1)):
        if clave in entrada:
            try:
                valor = _entero(entrada.get(clave))
            except ValueError:
                r.error(clave, "Escribe un número entero.")
                continue
            if valor is not None and valor < minimo:
                r.error(clave, f"Debe ser {minimo} o más.")
            if campo == "maximo_por_cliente" and valor is None:
                valor = 1
            r.datos[campo] = valor
    for clave in ("desde", "hasta"):
        if clave in entrada:
            texto = entrada.get(clave)
            if texto in (None, ""):
                r.datos[clave] = None
                continue
            try:
                fecha = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
            except ValueError:
                r.error(clave, "Fecha no válida.")
                continue
            if fecha.tzinfo is None:
                r.error(clave, "La fecha debe llevar zona horaria.")
                continue
            r.datos[clave] = fecha
    if r.datos.get("desde") and r.datos.get("hasta") and r.datos["hasta"] <= r.datos["desde"]:
        r.error("hasta", "La fecha de fin debe ser posterior a la de inicio.")

    precio_ref = r.datos.get("precio")
    if "regateoTipo" in entrada or es_nueva:
        _regla(r, "regateo", entrada.get("regateoTipo"), entrada.get("regateoValor"), TIPOS_REGATEO, precio_ref)
    if "transferenciaTipo" in entrada or es_nueva:
        _regla(r, "transferencia", entrada.get("transferenciaTipo"), entrada.get("transferenciaValor"), TIPOS_TRANSFERENCIA, precio_ref)

    if es_nueva or "items" in entrada:
        items = entrada.get("items") or []
        if not isinstance(items, list) or not items:
            r.error("items", "Agrega al menos un producto a la oferta.")
            items = []
        for i, item in enumerate(items):
            sku = str((item or {}).get("productoSku") or "").strip()
            try:
                cantidad = _entero((item or {}).get("cantidad")) or 1
            except ValueError:
                r.error(f"items.{i}", "La cantidad debe ser un número entero.")
                continue
            if sku not in productos:
                r.error(f"items.{i}", f"El producto {sku or '(vacío)'} no existe.")
                continue
            if cantidad < 1:
                r.error(f"items.{i}", "La cantidad debe ser 1 o más.")
                continue
            variante = str((item or {}).get("variante") or "").strip() or None
            r.items.append({"producto_sku": sku, "cantidad": cantidad, "variante": variante})
        cierres = {productos[i["producto_sku"]].get("proveedor_cierre") or "rocketfy" for i in r.items}
        if len(cierres) > 1:
            r.error("items", "Una oferta no puede juntar productos de Rocketfy con productos propios (regla P5).")
        if r.items and precio_ref is not None:
            lista = sum((dinero(productos[i["producto_sku"]]["precio"]) * i["cantidad"] for i in r.items), Decimal("0"))
            if r.datos.get("precio") is not None and precio_ref > lista:
                r.error("precio", f"Es más caro que comprar los productos por separado (${lista:.2f}).")
            piso = piso_del_pedido(
                [(costos.get(i["producto_sku"]) * i["cantidad"]) if costos.get(i["producto_sku"]) is not None else None for i in r.items],
                ajustes,
            )
            if piso is not None and precio_ref < piso and not r.datos.get("bajo_margen_autorizado"):
                r.bajo_margen.append(f"El precio de la oferta (${precio_ref:.2f}) queda bajo tu margen mínimo (mínimo ${piso:.2f}).")
    return r
