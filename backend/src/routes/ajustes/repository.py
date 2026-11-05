from typing import Any, Dict, List, Optional

import psycopg2.errors

from src.config.database import get_connection

from .exceptions import AjustesInvalidosError

_COLUMNAS = (
    "margen_minimo_pct, margen_objetivo_pct, envio_estimado, otros_costos_fijos, "
    "otros_costos_pct, redondeo, tope_redacciones_dia, tope_pruebas_dia, confirmado_en, actualizado_por, actualizado_en"
)

# Únicas columnas que se pueden guardar (lista blanca: ningún nombre de
# columna llega desde el cliente).
COLUMNAS_GUARDABLES = (
    "margen_minimo_pct",
    "margen_objetivo_pct",
    "envio_estimado",
    "otros_costos_fijos",
    "otros_costos_pct",
    "redondeo",
)

# Ajustes que pueden venir o no en el PUT (si faltan, se conserva el valor guardado):
# así un frontend viejo, que no los conoce, no los pisa ni falla.
COLUMNAS_OPCIONALES = ("tope_redacciones_dia", "tope_pruebas_dia")


def _fila(cur) -> Optional[Dict[str, Any]]:
    row = cur.fetchone()
    if row is None:
        return None
    return dict(zip([d[0] for d in cur.description], row))


class AjustesNegocioRepository:
    @staticmethod
    def obtener() -> Dict[str, Any]:
        """La fila única de ajustes. Si alguien la borrara, se vuelve a crear
        con los valores de partida (los de la tabla)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from ajustes_negocio where id = 1")
                fila = _fila(cur)
                if fila is None:
                    cur.execute("insert into ajustes_negocio (id) values (1) on conflict (id) do nothing")
                    cur.execute(f"select {_COLUMNAS} from ajustes_negocio where id = 1")
                    fila = _fila(cur)
                return fila

    @staticmethod
    def guardar(datos: Dict[str, Any], usuario: Optional[str]) -> Dict[str, Any]:
        """Guarda los seis ajustes de precios (más los opcionales que vengan) y
        marca que el dueño ya los confirmó (la primera vez; después se conserva
        esa fecha)."""
        faltan = [c for c in COLUMNAS_GUARDABLES if c not in datos]
        sobran = [c for c in datos if c not in COLUMNAS_GUARDABLES and c not in COLUMNAS_OPCIONALES]
        if faltan or sobran:
            raise ValueError(f"Columnas inválidas. Faltan: {faltan}; sobran: {sobran}")

        columnas = list(COLUMNAS_GUARDABLES) + [c for c in COLUMNAS_OPCIONALES if c in datos]
        asignaciones = ", ".join(f"{c} = %s" for c in columnas)
        valores = [datos[c] for c in columnas]
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("insert into ajustes_negocio (id) values (1) on conflict (id) do nothing")
                    cur.execute(
                        f"""
                        update ajustes_negocio
                           set {asignaciones},
                               confirmado_en = coalesce(confirmado_en, now()),
                               actualizado_por = %s,
                               actualizado_en = now()
                         where id = 1
                        returning {_COLUMNAS}
                        """,
                        (*valores, usuario),
                    )
                    return _fila(cur)
        except psycopg2.errors.CheckViolation as exc:
            raise AjustesInvalidosError(["Los ajustes no cumplen las reglas de la base de datos."]) from exc

    @staticmethod
    def listar_minimos_con_costo(limite: int = 100) -> List[Dict[str, Any]]:
        """Rechazos de Rocketfy por importe mínimo (Fase A) de los productos
        cuyo costo se conoce, los más recientes primero."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select o.sku, o.cantidad, o.minimo, o.creado_en, p.costo_rocketfy
                      from rocketfy_minimos_observados o
                      join productos_bot p on p.sku = o.sku
                     where p.costo_rocketfy is not null
                       and o.cantidad is not null and o.cantidad >= 1
                     order by o.creado_en desc
                     limit %s
                    """,
                    (limite,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]
