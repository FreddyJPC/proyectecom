"""
Regenera `frontend/tools/ui-preview/parametros-catalogo.json`: el catálogo de Parámetros
(src/config/parametros/catalogo.py) en la forma exacta que devuelve la API, para que la
vista previa de la interfaz (frontend/tools/ui-preview) se vea con las explicaciones, los
rangos y los textos reales. Solo es una herramienta de desarrollo: no toca la base ni la red.

Uso (desde backend/, con las variables dummy de CLAUDE.md §5 cargadas):
    python tools/exportar_parametros_preview.py
"""
import json
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.parametros import ParametrosService  # noqa: E402
from src.routes.parametros.schemas import respuesta_schema  # noqa: E402
from src.routes.parametros.services import ParametrosAdminService  # noqa: E402

DESTINO = Path(__file__).resolve().parent.parent.parent / "frontend" / "tools" / "ui-preview" / "parametros-catalogo.json"


class _SinNadaGuardado:
    """Repositorio de mentira: ningún valor guardado, así todo sale con su valor original."""

    def listar(self):
        return {}

    def historial(self, limite=50):
        return []


def main() -> None:
    servicio = ParametrosService(repo=_SinNadaGuardado(), entorno={})
    datos = respuesta_schema.dump(asdict(ParametrosAdminService(servicio).listar()))
    DESTINO.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{DESTINO}: {len(datos['grupos'])} grupos, {sum(len(g['parametros']) for g in datos['grupos'])} parámetros")


if __name__ == "__main__":
    main()
