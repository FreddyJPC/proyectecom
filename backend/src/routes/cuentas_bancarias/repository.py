"""Cuentas para transferir (tabla `cuentas_bancarias`, migración 029): las cuentas del dueño que Victoria le da al cliente."""
from typing import Any, Dict, List, Optional

import psycopg2.errors

from src.config.database import get_connection

_COLUMNAS = "id, banco, tipo_cuenta, numero, titular, identificacion, activa, orden"


class CuentaYaExisteError(Exception):
    pass


def _filas(cur) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, f)) for f in cur.fetchall()]


class CuentaBancariaRepository:
    @staticmethod
    def listar(solo_activas: bool = False) -> List[Dict[str, Any]]:
        filtro = "where activa = true" if solo_activas else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from cuentas_bancarias {filtro} order by orden, id")
                return _filas(cur)

    @staticmethod
    def obtener(cuenta_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS} from cuentas_bancarias where id = %s", (cuenta_id,))
                filas = _filas(cur)
                return filas[0] if filas else None

    @staticmethod
    def crear(banco: str, tipo_cuenta: str, numero: str, titular: str, identificacion: Optional[str], activa: bool, orden: Optional[int]) -> Dict[str, Any]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Sin «orden» explícito, la cuenta nueva queda al final.
                    cur.execute(
                        f"""
                        insert into cuentas_bancarias (banco, tipo_cuenta, numero, titular, identificacion, activa, orden)
                        values (%s, %s, %s, %s, %s, %s, coalesce(%s, (select coalesce(max(orden), 0) + 1 from cuentas_bancarias)))
                        returning {_COLUMNAS}
                        """,
                        (banco, tipo_cuenta, numero, titular, identificacion, activa, orden),
                    )
                    return _filas(cur)[0]
        except psycopg2.errors.UniqueViolation as exc:
            raise CuentaYaExisteError(f"Ya existe la cuenta {numero} de {banco}.") from exc

    @staticmethod
    def actualizar(cuenta_id: int, cambios: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """`cambios` solo trae los campos que se quieren cambiar; `identificacion` puede ir en None para quitarla."""
        permitidos = ("banco", "tipo_cuenta", "numero", "titular", "identificacion", "activa", "orden")
        campos = [c for c in permitidos if c in cambios]
        if not campos:
            return CuentaBancariaRepository.obtener(cuenta_id)
        asignaciones = ", ".join(f"{c} = %s" for c in campos)
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"update cuentas_bancarias set {asignaciones}, actualizado_en = now() where id = %s returning {_COLUMNAS}",
                        (*[cambios[c] for c in campos], cuenta_id),
                    )
                    filas = _filas(cur)
                    return filas[0] if filas else None
        except psycopg2.errors.UniqueViolation as exc:
            raise CuentaYaExisteError("Ya existe una cuenta con ese banco y número.") from exc

    @staticmethod
    def borrar(cuenta_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from cuentas_bancarias where id = %s", (cuenta_id,))
                return cur.rowcount > 0
