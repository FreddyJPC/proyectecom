from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass
class OpcionDTO:
    valor: str
    etiqueta: str
    nota: str


@dataclass
class ParametroDTO:
    clave: str
    nombre: str
    para_que_sirve: str
    tipo: str
    # Valor que rige hoy y de dónde sale: «app» (lo guardaste aquí), «servidor» (variable
    # de Railway) u «original» (el del código).
    valor: Any
    origen: str
    # Valor que valdría sin nada guardado en la app (variable del servidor o código).
    valor_original: Any
    valor_app: Optional[Any]
    # Nombre y valor de la variable del servidor equivalente, si existe y es válida.
    variable_servidor: Optional[str]
    valor_servidor: Optional[Any]
    minimo: Optional[int]
    maximo: Optional[int]
    largo_maximo: Optional[int]
    unidad: str
    aplica: str
    sensible: bool
    aviso: str
    opciones: List[OpcionDTO] = field(default_factory=list)
    avisos: List[str] = field(default_factory=list)
    actualizado_por: Optional[str] = None
    actualizado_en: Optional[str] = None


@dataclass
class GrupoDTO:
    clave: str
    nombre: str
    descripcion: str
    parametros: List[ParametroDTO]


@dataclass
class ParametrosRespuestaDTO:
    grupos: List[GrupoDTO]


@dataclass
class CambioDTO:
    clave: str
    nombre: str
    valor_anterior: Optional[str]
    valor_nuevo: Optional[str]
    usuario: Optional[str]
    creado_en: str
