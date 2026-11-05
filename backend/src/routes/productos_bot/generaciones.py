"""
Registro de usos de la IA (tabla `generaciones_ia`, migración 016): sirve para
el tope diario y para saber quién usó la IA, con qué modelo y cuándo.
"""
from typing import List, Optional

from src.config.database import get_connection

TIPO_CONTENIDO = "contenido"
# Mensajes de «Probar con Victoria» (Fase E): comparten la tabla pero tienen su propio tope.
TIPO_SIMULACION = "simulacion"
RESULTADOS = ("ok", "invalido", "fallo")
# Los únicos resultados que costaron plata (la IA sí contestó): son los que
# cuentan para el tope. Un "fallo" (el proveedor no respondió) no cuenta.
RESULTADOS_QUE_CUENTAN = ("ok", "invalido")

# El "día" del tope es el día de ECUADOR, no el de UTC: a las 20:00 de Quito ya
# es el día siguiente en UTC y el contador se reiniciaría a media tarde.
ZONA_DEL_NEGOCIO = "America/Guayaquil"


class GeneracionesIARepository:
    @staticmethod
    def contar_hoy(tipo: str = TIPO_CONTENIDO) -> int:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select count(*) from generaciones_ia
                     where tipo = %s
                       and resultado = any(%s)
                       and (creado_en at time zone %s)::date = (now() at time zone %s)::date
                    """,
                    (tipo, list(RESULTADOS_QUE_CUENTAN), ZONA_DEL_NEGOCIO, ZONA_DEL_NEGOCIO),
                )
                return int(cur.fetchone()[0])

    @staticmethod
    def registrar(
        sku: Optional[str],
        usuario: Optional[str],
        modelo: Optional[str],
        resultado: str,
        campos: List[str],
        tipo: str = TIPO_CONTENIDO,
    ) -> None:
        if resultado not in RESULTADOS:
            raise ValueError(f"Resultado inválido: {resultado}")
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into generaciones_ia (sku, usuario, tipo, modelo, campos, resultado)
                    values (%s, %s, %s, %s, %s, %s)
                    """,
                    (sku, usuario, tipo, modelo, ",".join(campos), resultado),
                )
