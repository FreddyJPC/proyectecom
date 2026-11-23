"""
Acceso a datos del módulo «Inmuebles» (migración 037): propiedades, su material (fotos y videos), los anuncios que hablan de
cada una, la agenda de visitas y los números de WhatsApp del negocio.

Solo SQL: las reglas (qué se puede cambiar, cuándo una visita queda confirmada, qué se le dice al cliente) viven en
`servicio.py` y `logica.py`.
"""
from typing import Any, Dict, Iterable, List, Optional

import psycopg2.errors

from src.config.database import get_connection

# Campos de la ficha que el dueño puede editar (todos menos id y fechas). Es la lista blanca del `update`: nunca se arma una
# consulta con nombres de columna que vengan de afuera.
CAMPOS_FICHA = (
    "codigo", "titulo", "tipo", "operacion", "estado", "precio", "mostrar_precio", "precio_negociable", "ciudad", "sector",
    "direccion", "referencia_llegada", "latitud", "longitud", "terreno_m2", "construccion_m2", "frente_m", "fondo_m", "pisos",
    "habitaciones", "banos", "parqueaderos", "uso", "descripcion", "caracteristicas", "servicios", "documentacion",
    "preguntas_frecuentes", "temas_no_responder", "horarios_visita", "encargado_visitas", "notas_internas",
)
_COLUMNAS_INMUEBLE = "id, " + ", ".join(CAMPOS_FICHA) + ", creado_en, actualizado_en"
_COLUMNAS_MATERIAL = "id, inmueble_id, url, storage_path, orden, creado_en, creado_por"
_COLUMNAS_VISITA = (
    "v.id, v.inmueble_id, v.conversacion_id, v.contacto_id, v.nombre_cliente, v.telefono, v.estado, v.preferencia_cliente, "
    "v.personas, v.fecha_hora, v.encargado, v.notas, v.motivo_cancelacion, v.creada_por, v.creado_en, v.actualizado_en, "
    "v.confirmada_en, v.avisado_cliente_en, i.titulo as inmueble_titulo, i.codigo as inmueble_codigo"
)
_SELECT_VISITA = f"select {_COLUMNAS_VISITA} from visitas v join inmuebles i on i.id = v.inmueble_id"
# Lo que se puede cambiar de una visita (lista blanca del `update`).
CAMPOS_VISITA = (
    "nombre_cliente", "telefono", "estado", "preferencia_cliente", "personas", "fecha_hora", "encargado", "notas",
    "motivo_cancelacion", "confirmada_en", "avisado_cliente_en",
)
ESTADOS_ABIERTOS = ("solicitada", "confirmada")


class CodigoDeInmuebleRepetidoError(Exception):
    """Ya hay otra propiedad con ese código."""


class MaterialYaRegistradoError(Exception):
    """Ese archivo ya está en la galería."""


def _filas(cur) -> List[Dict[str, Any]]:
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, f)) for f in cur.fetchall()]


def _una(cur) -> Optional[Dict[str, Any]]:
    filas = _filas(cur)
    return filas[0] if filas else None


class InmuebleRepository:
    @staticmethod
    def listar(estados: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        """Las propiedades con lo que hace falta para la lista del panel: su primera foto y cuántas visitas tiene abiertas."""
        filtro, params = "", []
        if estados:
            filtro, params = "where i.estado = any(%s)", [list(estados)]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    select {', '.join('i.' + c.strip() for c in _COLUMNAS_INMUEBLE.split(','))},
                        (select m.url from inmuebles_material m where m.inmueble_id = i.id order by m.orden, m.id limit 1) as portada_url,
                        (select m.storage_path from inmuebles_material m where m.inmueble_id = i.id order by m.orden, m.id limit 1) as portada_path,
                        (select count(*) from visitas v where v.inmueble_id = i.id and v.estado = 'solicitada') as visitas_por_confirmar,
                        (select count(*) from visitas v where v.inmueble_id = i.id and v.estado = 'confirmada' and v.fecha_hora >= now()) as visitas_proximas
                    from inmuebles i {filtro}
                    order by case i.estado when 'activo' then 0 when 'borrador' then 1 when 'pausado' then 2 else 3 end, i.titulo
                    """,
                    params,
                )
                return _filas(cur)

    @staticmethod
    def obtener(inmueble_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_INMUEBLE} from inmuebles where id = %s", (inmueble_id,))
                return _una(cur)

    @staticmethod
    def obtener_por_codigo(codigo: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_INMUEBLE} from inmuebles where lower(codigo) = lower(%s)", (codigo,))
                return _una(cur)

    @staticmethod
    def listar_activos() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {_COLUMNAS_INMUEBLE} from inmuebles where estado = 'activo' order by titulo")
                return _filas(cur)

    @staticmethod
    def crear(datos: Dict[str, Any]) -> Dict[str, Any]:
        campos = [c for c in CAMPOS_FICHA if c in datos]
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"insert into inmuebles ({', '.join(campos)}) values ({', '.join(['%s'] * len(campos))}) "
                        f"returning {_COLUMNAS_INMUEBLE}",
                        [datos[c] for c in campos],
                    )
                    return _una(cur)
        except psycopg2.errors.UniqueViolation as exc:
            raise CodigoDeInmuebleRepetidoError("Ya hay otra propiedad con ese código.") from exc

    @staticmethod
    def actualizar(inmueble_id: int, cambios: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        campos = [c for c in CAMPOS_FICHA if c in cambios]
        if not campos:
            return InmuebleRepository.obtener(inmueble_id)
        asignaciones = ", ".join(f"{c} = %s" for c in campos)
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"update inmuebles set {asignaciones}, actualizado_en = now() where id = %s returning {_COLUMNAS_INMUEBLE}",
                        [cambios[c] for c in campos] + [inmueble_id],
                    )
                    return _una(cur)
        except psycopg2.errors.UniqueViolation as exc:
            raise CodigoDeInmuebleRepetidoError("Ya hay otra propiedad con ese código.") from exc


class MaterialInmuebleRepository:
    @staticmethod
    def listar(inmueble_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"select {_COLUMNAS_MATERIAL} from inmuebles_material where inmueble_id = %s order by orden, id",
                    (inmueble_id,),
                )
                return _filas(cur)

    @staticmethod
    def agregar(inmueble_id: int, url: str, storage_path: str, usuario: Optional[str]) -> Dict[str, Any]:
        try:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        insert into inmuebles_material (inmueble_id, url, storage_path, orden, creado_por)
                        values (%s, %s, %s, coalesce((select max(orden) + 1 from inmuebles_material where inmueble_id = %s), 0), %s)
                        returning {_COLUMNAS_MATERIAL}
                        """,
                        (inmueble_id, url, storage_path, inmueble_id, usuario),
                    )
                    return _una(cur)
        except psycopg2.errors.UniqueViolation as exc:
            raise MaterialYaRegistradoError("Ese archivo ya está en la galería.") from exc

    @staticmethod
    def quitar(inmueble_id: int, material_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"delete from inmuebles_material where id = %s and inmueble_id = %s returning {_COLUMNAS_MATERIAL}",
                    (material_id, inmueble_id),
                )
                return _una(cur)

    @staticmethod
    def reordenar(inmueble_id: int, ids_en_orden: List[int]) -> None:
        with get_connection() as conn:
            with conn.cursor() as cur:
                for orden, material_id in enumerate(ids_en_orden):
                    cur.execute(
                        "update inmuebles_material set orden = %s where id = %s and inmueble_id = %s",
                        (orden, material_id, inmueble_id),
                    )


class AnuncioInmuebleRepository:
    @staticmethod
    def inmueble_de_anuncio(id_anuncio: Optional[str]) -> Optional[int]:
        if not id_anuncio:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select inmueble_id from inmuebles_anuncios where id_anuncio = %s", (str(id_anuncio),))
                fila = cur.fetchone()
                return fila[0] if fila else None

    @staticmethod
    def listar_de(inmueble_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select id_anuncio, inmueble_id, nombre, creado_en from inmuebles_anuncios where inmueble_id = %s "
                    "order by creado_en",
                    (inmueble_id,),
                )
                return _filas(cur)

    @staticmethod
    def vincular(id_anuncio: str, inmueble_id: int, nombre: Optional[str]) -> Dict[str, Any]:
        """Un anuncio habla de UNA propiedad: si ya estaba vinculado a otra, pasa a esta."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    insert into inmuebles_anuncios (id_anuncio, inmueble_id, nombre) values (%s, %s, %s)
                    on conflict (id_anuncio) do update set inmueble_id = excluded.inmueble_id, nombre = excluded.nombre
                    returning id_anuncio, inmueble_id, nombre, creado_en
                    """,
                    (id_anuncio, inmueble_id, nombre),
                )
                return _una(cur)

    @staticmethod
    def desvincular(id_anuncio: str, inmueble_id: int) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "delete from inmuebles_anuncios where id_anuncio = %s and inmueble_id = %s", (id_anuncio, inmueble_id)
                )
                return cur.rowcount > 0

    @staticmethod
    def es_anuncio_de_producto(id_anuncio: str) -> bool:
        """¿Ese anuncio ya está vinculado a un PRODUCTO de la tienda? (no puede hablar de una casa y de un producto a la vez)."""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("select 1 from anuncios_productos where id_anuncio = %s", (id_anuncio,))
                return cur.fetchone() is not None


class VisitaRepository:
    @staticmethod
    def listar(
        desde=None,
        hasta=None,
        estados: Optional[Iterable[str]] = None,
        inmueble_id: Optional[int] = None,
        sin_fecha: bool = True,
    ) -> List[Dict[str, Any]]:
        """La agenda. `desde`/`hasta` filtran por la fecha confirmada; las visitas todavía sin fecha (pedidas) se incluyen si
        `sin_fecha` (las que el dueño tiene que confirmar no pueden quedar fuera de la vista)."""
        condiciones, params = [], []
        if estados:
            condiciones.append("v.estado = any(%s)")
            params.append(list(estados))
        if inmueble_id:
            condiciones.append("v.inmueble_id = %s")
            params.append(inmueble_id)
        rango = []
        if desde is not None:
            rango.append("v.fecha_hora >= %s")
            params.append(desde)
        if hasta is not None:
            rango.append("v.fecha_hora < %s")
            params.append(hasta)
        if rango:
            con_fecha = " and ".join(rango)
            condiciones.append(f"(({con_fecha}) or v.fecha_hora is null)" if sin_fecha else f"({con_fecha})")
        where = f"where {' and '.join(condiciones)}" if condiciones else ""
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_VISITA} {where} order by v.fecha_hora asc nulls first, v.creado_en asc",
                    params,
                )
                return _filas(cur)

    @staticmethod
    def obtener(visita_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_VISITA} where v.id = %s", (visita_id,))
                return _una(cur)

    @staticmethod
    def de_conversacion(conversacion_id: int) -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"{_SELECT_VISITA} where v.conversacion_id = %s order by v.creado_en desc", (conversacion_id,))
                return _filas(cur)

    @staticmethod
    def abierta_de(conversacion_id: int, inmueble_id: int) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"{_SELECT_VISITA} where v.conversacion_id = %s and v.inmueble_id = %s and v.estado = any(%s)",
                    (conversacion_id, inmueble_id, list(ESTADOS_ABIERTOS)),
                )
                return _una(cur)

    @staticmethod
    def crear(datos: Dict[str, Any]) -> Dict[str, Any]:
        campos = [
            c for c in (
                "inmueble_id", "conversacion_id", "contacto_id", "nombre_cliente", "telefono", "estado", "preferencia_cliente",
                "personas", "fecha_hora", "encargado", "notas", "creada_por", "confirmada_en",
            ) if c in datos
        ]
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"insert into visitas ({', '.join(campos)}) values ({', '.join(['%s'] * len(campos))}) returning id",
                    [datos[c] for c in campos],
                )
                visita_id = cur.fetchone()[0]
                cur.execute(f"{_SELECT_VISITA} where v.id = %s", (visita_id,))
                return _una(cur)

    @staticmethod
    def actualizar(visita_id: int, cambios: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        campos = [c for c in CAMPOS_VISITA if c in cambios]
        with get_connection() as conn:
            with conn.cursor() as cur:
                if campos:
                    asignaciones = ", ".join(f"{c} = %s" for c in campos)
                    cur.execute(
                        f"update visitas set {asignaciones}, actualizado_en = now() where id = %s",
                        [cambios[c] for c in campos] + [visita_id],
                    )
                cur.execute(f"{_SELECT_VISITA} where v.id = %s", (visita_id,))
                return _una(cur)

    @staticmethod
    def contar_por_estado() -> Dict[str, int]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select
                        count(*) filter (where estado = 'solicitada') as por_confirmar,
                        count(*) filter (where estado = 'confirmada' and fecha_hora >= now()) as proximas,
                        count(*) filter (where estado = 'confirmada' and fecha_hora >= date_trunc('day', now() at time zone 'America/Guayaquil') at time zone 'America/Guayaquil'
                                         and fecha_hora < (date_trunc('day', now() at time zone 'America/Guayaquil') + interval '1 day') at time zone 'America/Guayaquil') as hoy
                    from visitas
                    """
                )
                fila = cur.fetchone()
                return {"por_confirmar": fila[0], "proximas": fila[1], "hoy": fila[2]}


class NumeroWhatsappRepository:
    _COLUMNAS = "phone_number_id, nombre, telefono_visible, asistente, activo, creado_en, actualizado_en"

    @staticmethod
    def listar() -> List[Dict[str, Any]]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"select {NumeroWhatsappRepository._COLUMNAS} from numeros_whatsapp order by creado_en")
                return _filas(cur)

    @staticmethod
    def asistente_de(phone_number_id: Optional[str]) -> Optional[str]:
        """Qué asistente atiende ese número del negocio (None = no está registrado: se atiende como siempre, con Victoria)."""
        if not phone_number_id:
            return None
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "select asistente from numeros_whatsapp where phone_number_id = %s and activo = true", (phone_number_id,)
                )
                fila = cur.fetchone()
                return fila[0] if fila else None

    @staticmethod
    def guardar(phone_number_id: str, nombre: str, telefono_visible: Optional[str], asistente: str, activo: bool) -> Dict[str, Any]:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    insert into numeros_whatsapp (phone_number_id, nombre, telefono_visible, asistente, activo)
                    values (%s, %s, %s, %s, %s)
                    on conflict (phone_number_id) do update set
                        nombre = excluded.nombre, telefono_visible = excluded.telefono_visible, asistente = excluded.asistente,
                        activo = excluded.activo, actualizado_en = now()
                    returning {NumeroWhatsappRepository._COLUMNAS}
                    """,
                    (phone_number_id, nombre, telefono_visible, asistente, activo),
                )
                return _una(cur)

    @staticmethod
    def quitar(phone_number_id: str) -> bool:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("delete from numeros_whatsapp where phone_number_id = %s", (phone_number_id,))
                return cur.rowcount > 0
