"""
Ayudantes para las pruebas que usan la base de datos real (la desechable de pruebas, nunca la de producción).

Desde la migración 024 la base se NIEGA a borrar una conversación que tiene leads, llegadas por anuncio o solicitudes de
gestión (antes lo hacía en cascada): es la protección del historial del contacto. Las pruebas, que sí necesitan limpiar
lo que crean, borran en el orden correcto con `borrar_conversaciones_de_prueba`.
"""
from src.config.database import get_connection


def borrar_conversaciones_de_prueba(*ids_externos: str, canal: str = "whatsapp") -> None:
    """Borra las conversaciones de esos clientes (por su identificador en el canal) con todo lo que cuelga de ellas:
    ventas, solicitudes, llegadas por anuncio, leads, mensajes y cola; y sus contactos si quedan sin conversaciones."""
    if not ids_externos:
        return
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select id, contacto_id from conversaciones where canal = %s and id_externo = any(%s)",
                (canal, list(ids_externos)),
            )
            filas = cur.fetchall()
            conversaciones = [f[0] for f in filas]
            contactos = sorted({f[1] for f in filas})
            if conversaciones:
                cur.execute("delete from solicitudes_gestion where conversacion_id = any(%s)", (conversaciones,))
                cur.execute(
                    "delete from ventas where conversacion_id = any(%s) or contacto_id = any(%s)", (conversaciones, contactos)
                )
                cur.execute("delete from conversacion_anuncios where conversacion_id = any(%s)", (conversaciones,))
                cur.execute(
                    "delete from lead_historial where lead_id in (select id from leads where conversacion_id = any(%s))",
                    (conversaciones,),
                )
                cur.execute("delete from leads where conversacion_id = any(%s)", (conversaciones,))
                cur.execute("delete from conversaciones where id = any(%s)", (conversaciones,))
            if contactos:
                cur.execute(
                    "delete from contactos ct where ct.id = any(%s) "
                    "and not exists (select 1 from conversaciones c where c.contacto_id = ct.id)",
                    (contactos,),
                )
            # Contactos de prueba creados solo por teléfono (sin conversación): p. ej. ventas históricas.
            cur.execute(
                "delete from ventas where telefono = any(%s) and contacto_id in (select id from contactos where telefono = any(%s))",
                (list(ids_externos), list(ids_externos)),
            )
            cur.execute(
                "delete from contactos ct where ct.telefono = any(%s) "
                "and not exists (select 1 from conversaciones c where c.contacto_id = ct.id) "
                "and not exists (select 1 from leads l where l.contacto_id = ct.id) "
                "and not exists (select 1 from ventas v where v.contacto_id = ct.id)",
                (list(ids_externos),),
            )
