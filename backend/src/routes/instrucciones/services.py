"""
Capa de la API de las instrucciones de Victoria: el flujo borrador → publicada, con las
versiones y el «volver a la original». Las reglas del texto (secciones, validación, escape de
llaves) viven en src/routes/whatsapp/instrucciones.py.
"""
from typing import Any, Dict, Mapping, Optional

from src.routes.whatsapp.instrucciones import (
    EDITABLES,
    MAXIMO_TOTAL,
    SECCIONES,
    SinBorradorError,
    caracteres_fijos,
    cuerpo_fijo,
    instrucciones_vigentes,
    secciones_originales,
    validar,
)
from src.routes.whatsapp.instrucciones_repository import InstruccionesRepository

from .dto import InstruccionesDTO, SeccionDTO, VersionDTO
from .exceptions import VersionNoExisteError


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if valor else None


def _version(fila: Optional[Dict[str, Any]]) -> Optional[VersionDTO]:
    if fila is None:
        return None
    return VersionDTO(
        id=fila["id"],
        estado=fila["estado"],
        nota=fila["nota"],
        creado_por=fila["creado_por"],
        creado_en=_iso(fila["creado_en"]) or "",
        publicada_en=_iso(fila["publicada_en"]),
    )


class InstruccionesAdminService:
    def __init__(self, repo=None, vigentes=None):
        self._repo = repo or InstruccionesRepository()
        self._vigentes = vigentes or instrucciones_vigentes

    # ------------------------------------------------------------------
    def ver(self) -> InstruccionesDTO:
        publicada = self._repo.publicada()
        borrador = self._repo.borrador()
        originales = secciones_originales()

        secciones = []
        for s in SECCIONES:
            if s.editable:
                vigente = (publicada["secciones"].get(s.id) if publicada else None) or originales[s.id]
                texto_borrador = borrador["secciones"].get(s.id) if borrador else None
                original = originales[s.id]
            else:
                original = vigente = cuerpo_fijo(s.id)
                texto_borrador = None
            secciones.append(
                SeccionDTO(
                    id=s.id, nombre=s.nombre, ayuda=s.ayuda, editable=s.editable, maximo=s.maximo,
                    original=original, vigente=vigente, borrador=texto_borrador,
                )
            )

        versiones = [_version(f) for f in self._repo.versiones(20) if f["estado"] != "borrador"]
        return InstruccionesDTO(
            secciones=secciones,
            usando="publicada" if publicada else "original",
            publicada=_version(publicada),
            borrador=_version(borrador),
            versiones=versiones,
            maximo_total=MAXIMO_TOTAL,
            caracteres_fijos=caracteres_fijos(),
        )

    # ------------------------------------------------------------------
    def guardar_borrador(self, secciones: Mapping[str, Any], nota: Optional[str], usuario: Optional[str]) -> InstruccionesDTO:
        """`InstruccionesInvalidas` si no cumple las reglas: no se guarda nada."""
        limpias = validar(secciones)
        self._repo.guardar_borrador(limpias, (nota or "").strip() or None, usuario)
        return self.ver()

    def descartar_borrador(self) -> InstruccionesDTO:
        self._repo.descartar_borrador()
        return self.ver()

    def publicar(self, nota: Optional[str], usuario: Optional[str]) -> InstruccionesDTO:
        """El borrador pasa a ser lo que usa Victoria con los clientes. Se vuelve a validar aquí:
        lo que se publica es lo que se comprueba ahora, no lo que se comprobó al guardar."""
        borrador = self._repo.borrador()
        if borrador is None:
            raise SinBorradorError("No hay un borrador para publicar.")
        validar(borrador["secciones"])
        self._repo.publicar_borrador((nota or "").strip() or None)
        self._vigentes.invalidar()
        return self.ver()

    def volver_a_la_original(self) -> InstruccionesDTO:
        """Victoria vuelve a usar el texto del código al instante. La versión que estaba publicada se archiva."""
        self._repo.volver_a_la_original()
        self._vigentes.invalidar()
        return self.ver()

    def cargar_version(self, id_version: int, usuario: Optional[str]) -> InstruccionesDTO:
        """Copia una versión anterior al borrador (reemplazando el que hubiera) para probarla y publicarla de nuevo."""
        fila = self._repo.obtener(id_version)
        if fila is None or fila["estado"] == "borrador":
            raise VersionNoExisteError(f"No existe la versión {id_version}.")
        originales = secciones_originales()
        secciones = {s.id: fila["secciones"].get(s.id, originales[s.id]) for s in EDITABLES}
        limpias = validar(secciones)
        self._repo.guardar_borrador(limpias, f"Cargada desde la versión {id_version}", usuario)
        return self.ver()
