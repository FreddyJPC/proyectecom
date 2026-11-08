"""
Capa de la API de Parámetros: convierte lo que decide el servicio de
`src/config/parametros` (quien sabe qué vale cada cosa) en lo que muestra la pantalla.
"""
from typing import Any, List, Optional

from src.config.parametros import CATALOGO, GRUPOS, Resolucion, definicion, parametros
from src.config.parametros.catalogo import ParametroDesconocidoError

from .dto import CambioDTO, GrupoDTO, OpcionDTO, ParametroDTO, ParametrosRespuestaDTO


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


def _a_dto(res: Resolucion) -> ParametroDTO:
    p = res.parametro
    # «Original» = lo que valdría si no hubiera nada guardado en la app.
    valor_original: Any = res.valor_servidor if res.valor_servidor is not None else p.defecto
    return ParametroDTO(
        clave=p.clave,
        nombre=p.nombre,
        para_que_sirve=p.para_que_sirve,
        tipo=p.tipo,
        valor=res.valor,
        origen=res.origen,
        valor_original=valor_original,
        valor_app=res.valor_app,
        variable_servidor=p.variable_servidor,
        valor_servidor=res.valor_servidor,
        minimo=p.minimo,
        maximo=p.maximo,
        largo_maximo=p.largo_maximo,
        unidad=p.unidad,
        aplica=p.aplica,
        sensible=p.sensible,
        aviso=p.aviso,
        opciones=[OpcionDTO(o.valor, o.etiqueta, o.nota) for o in p.opciones],
        avisos=list(res.avisos),
        actualizado_por=res.actualizado_por,
        actualizado_en=_iso(res.actualizado_en),
    )


class ParametrosAdminService:
    def __init__(self, servicio=None):
        self._servicio = servicio or parametros

    def listar(self) -> ParametrosRespuestaDTO:
        por_clave = {r.parametro.clave: r for r in self._servicio.listar()}
        return ParametrosRespuestaDTO(
            grupos=[
                GrupoDTO(
                    clave=g.clave,
                    nombre=g.nombre,
                    descripcion=g.descripcion,
                    parametros=[_a_dto(por_clave[p.clave]) for p in CATALOGO if p.grupo == g.clave],
                )
                for g in GRUPOS
            ]
        )

    def guardar(self, clave: str, valor: Any, usuario: Optional[str]) -> ParametroDTO:
        return _a_dto(self._servicio.guardar(clave, valor, usuario))

    def restaurar(self, clave: str, usuario: Optional[str]) -> ParametroDTO:
        return _a_dto(self._servicio.restaurar(clave, usuario))

    def historial(self, limite: int = 50) -> List[CambioDTO]:
        cambios = []
        for fila in self._servicio.historial(limite):
            try:
                nombre = definicion(fila["clave"]).nombre
            except ParametroDesconocidoError:
                nombre = fila["clave"]  # un parámetro que ya no existe en el catálogo
            cambios.append(
                CambioDTO(
                    clave=fila["clave"],
                    nombre=nombre,
                    valor_anterior=fila["valor_anterior"],
                    valor_nuevo=fila["valor_nuevo"],
                    usuario=fila["usuario"],
                    creado_en=_iso(fila["creado_en"]) or "",
                )
            )
        return cambios
