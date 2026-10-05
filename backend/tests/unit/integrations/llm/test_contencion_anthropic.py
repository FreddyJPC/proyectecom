"""
Regla dura del proyecto (Fase 3.2): ningún archivo fuera de
anthropic_provider.py puede importar el SDK `anthropic`. Este test barre
TODO src/ (no solo routes/whatsapp/ y los 3 archivos de integrations/llm/
mencionados en el encargo) porque la regla en sí es general -- si el SDK
se filtra a cualquier otro archivo, esto debe fallar sin importar dónde.
"""
import re
from pathlib import Path

import src

SRC_DIR = Path(src.__file__).resolve().parent
ARCHIVO_PERMITIDO = (SRC_DIR / "integrations" / "llm" / "providers" / "anthropic_provider.py").resolve()

_PATRON_IMPORT_ANTHROPIC = re.compile(r"^\s*(import anthropic\b|from anthropic\b)", re.MULTILINE)


def test_ningun_archivo_fuera_del_adapter_importa_el_sdk_de_anthropic():
    ofensores = []
    for archivo in SRC_DIR.rglob("*.py"):
        if archivo.resolve() == ARCHIVO_PERMITIDO:
            continue
        contenido = archivo.read_text(encoding="utf-8")
        if _PATRON_IMPORT_ANTHROPIC.search(contenido):
            ofensores.append(str(archivo.relative_to(SRC_DIR)))

    assert not ofensores, (
        "Estos archivos importan el SDK de anthropic fuera del adapter permitido "
        f"(integrations/llm/providers/anthropic_provider.py): {ofensores}"
    )
