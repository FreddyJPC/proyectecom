"""
Catálogo cerrado de provincias/cantones de Ecuador entregado por Rocketfy
(`docs/rocket-cantones-ecuador.csv`, copiado a `data/` para que la app no
dependa de una ruta fuera de su propio árbol de carpetas).

Existe para resolver el punto crítico de la sección 4.2 del doc del
proveedor: si el nombre de provincia/cantón no coincide con el catálogo de
Rocketfy, /orders/create responde 200 igual, pero /orders/confirm falla con
"Debe seleccionar una ciudad dentro de las opciones disponibles". Validar
ANTES de crear el pedido evita ese fallo tardío.

La comparación de Rocketfy "ignora mayúsculas y tildes, pero no corrige
nombres distintos" (doc, sección 4.2) — por eso _normalizar() solo quita
mayúsculas/tildes, no hace fuzzy matching.
"""
import csv
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rocket-cantones-ecuador.csv"


@dataclass(frozen=True)
class Canton:
    city_id: int
    canton: str
    province_id: int
    provincia: str


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_tildes.strip().upper()


class EcuadorLocationsCatalog:
    def __init__(self, csv_path: Path = DATA_PATH):
        self._cantones = self._cargar(csv_path)
        self._indice = {
            (_normalizar(c.provincia), _normalizar(c.canton)): c for c in self._cantones
        }

    @staticmethod
    def _cargar(csv_path: Path) -> List[Canton]:
        cantones = []
        with open(csv_path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                cantones.append(
                    Canton(
                        city_id=int(row["city_id"]),
                        canton=row["canton"],
                        province_id=int(row["province_id"]),
                        provincia=row["provincia"],
                    )
                )
        return cantones

    def resolver(self, provincia: str, canton: str) -> Optional[Canton]:
        """None si el par provincia/cantón no existe en el catálogo — en ese
        caso el llamador debe rechazar/corregir antes de llamar a Rocketfy,
        no dejar que falle en la confirmación."""
        return self._indice.get((_normalizar(provincia), _normalizar(canton)))

    def listar_provincias(self) -> List[str]:
        return sorted({c.provincia for c in self._cantones})

    def listar_cantones(self, provincia: str) -> List[str]:
        objetivo = _normalizar(provincia)
        return sorted(c.canton for c in self._cantones if _normalizar(c.provincia) == objetivo)

    def __len__(self) -> int:
        return len(self._cantones)


@lru_cache(maxsize=1)
def get_catalog() -> EcuadorLocationsCatalog:
    return EcuadorLocationsCatalog()
