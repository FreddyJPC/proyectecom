from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SeccionDTO:
    id: str
    nombre: str
    ayuda: str
    editable: bool
    maximo: int
    # El texto del código (lo que rige si no hay versión publicada).
    original: str
    # El texto que rige HOY con los clientes (la versión publicada o, si no hay, el original).
    vigente: str
    # El texto del borrador, o None si no hay borrador o la sección no se edita.
    borrador: Optional[str]


@dataclass
class VersionDTO:
    id: int
    estado: str
    nota: Optional[str]
    creado_por: Optional[str]
    creado_en: str
    publicada_en: Optional[str]


@dataclass
class InstruccionesDTO:
    secciones: List[SeccionDTO]
    # «original» (el archivo del código) o «publicada» (una versión hecha desde la app).
    usando: str
    publicada: Optional[VersionDTO]
    borrador: Optional[VersionDTO]
    # Versiones publicadas alguna vez (la actual y las archivadas), de la más nueva a la más vieja.
    versiones: List[VersionDTO] = field(default_factory=list)
    maximo_total: int = 0
    # Largo de todo lo que no se edita: sumado a lo escrito en las secciones da el largo del prompt.
    caracteres_fijos: int = 0
