"""
Regenera los datos de la vista previa de la interfaz (frontend/tools/ui-preview) a partir del
código del backend, para que las pantallas se vean con los textos, rangos y secciones reales:

  parametros-catalogo.json       el catálogo de Parámetros (src/config/parametros/catalogo.py) en la
                                 forma exacta que devuelve la API.
  instrucciones-secciones.json   las secciones de las instrucciones de Victoria (src/routes/whatsapp/
                                 instrucciones.py) con el texto original de cada una.

Solo es una herramienta de desarrollo: no toca la base ni la red.

Uso (desde backend/, con las variables dummy de CLAUDE.md §5 cargadas):
    python tools/exportar_para_preview.py
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.parametros import ParametrosService  # noqa: E402
from src.routes.instrucciones.schemas import SeccionSchema  # noqa: E402
from src.routes.instrucciones.services import InstruccionesAdminService  # noqa: E402
from src.routes.parametros.schemas import respuesta_schema  # noqa: E402
from src.routes.parametros.services import ParametrosAdminService  # noqa: E402

DESTINO = Path(__file__).resolve().parent.parent.parent / "frontend" / "tools" / "ui-preview"


class _ParametrosSinNadaGuardado:
    """Repositorio de mentira: ningún valor guardado, así todo sale con su valor original."""

    def listar(self):
        return {}

    def historial(self, limite=50):
        return []


class _InstruccionesSinNadaGuardado:
    """Repositorio de mentira: ni borrador ni versión publicada, rige el texto original."""

    def publicada(self):
        return None

    def borrador(self):
        return None

    def versiones(self, limite=20):
        return []


def _escribir(nombre: str, datos) -> None:
    ruta = DESTINO / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{ruta}")


def main() -> None:
    servicio = ParametrosService(repo=_ParametrosSinNadaGuardado(), entorno={})
    parametros = respuesta_schema.dump(asdict(ParametrosAdminService(servicio).listar()))
    _escribir("parametros-catalogo.json", parametros)

    instrucciones = InstruccionesAdminService(repo=_InstruccionesSinNadaGuardado()).ver()
    secciones = SeccionSchema(many=True).dump([asdict(s) for s in instrucciones.secciones])
    _escribir(
        "instrucciones-secciones.json",
        {"secciones": secciones, "maximoTotal": instrucciones.maximo_total, "caracteresFijos": instrucciones.caracteres_fijos},
    )


if __name__ == "__main__":
    main()
