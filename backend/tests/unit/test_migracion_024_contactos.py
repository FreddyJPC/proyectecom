"""
Migración 024 (contactos y canales, ADR-014): convierte los datos existentes sin perder nada y se puede volver a correr.

Se ejecuta sobre un esquema desechable que reproduce la forma ANTERIOR de las tablas, dentro de una transacción que
siempre se deshace: no toca las tablas reales de la base de pruebas.
"""
import os
from pathlib import Path

import psycopg2
import psycopg2.errors
import pytest

MIGRACION = Path(__file__).resolve().parents[2] / "migrations" / "024_contactos_y_canales.sql"

FORMA_ANTERIOR = """
create schema t024;
set local search_path = t024;
create table conversaciones (
    id bigserial primary key, telefono text not null unique, origen text not null default 'directo',
    fep_expira_en timestamptz, id_anuncio text, ctwa_clid text, estado text not null default 'activa',
    creada_en timestamptz not null default now(), actualizada_en timestamptz not null default now()
);
create table mensajes (id bigserial primary key);
create table leads (
    id bigserial primary key, conversacion_id bigint not null references conversaciones (id) on delete cascade,
    nombre_cliente text, telefono text, creado_en timestamptz not null default now(),
    actualizado_en timestamptz not null default now()
);
create table ventas (
    id bigserial primary key, lead_id bigint, conversacion_id bigint references conversaciones (id) on delete set null,
    canal text not null default 'directo', id_anuncio text, telefono text, cliente_nombre text,
    cerrada_en timestamptz not null default now()
);
create table conversacion_anuncios (
    id bigserial primary key, conversacion_id bigint not null references conversaciones (id) on delete cascade
);
create table solicitudes_gestion (
    id bigserial primary key, conversacion_id bigint not null references conversaciones (id) on delete cascade
);
insert into conversaciones (telefono, origen, id_anuncio) values ('593900000001', 'fep', 'ad-1'), ('593900000002', 'directo', null);
insert into leads (conversacion_id, telefono, nombre_cliente)
    select id, telefono, 'José Prueba' from conversaciones where telefono = '593900000001';
insert into ventas (lead_id, conversacion_id, canal, id_anuncio, telefono, cliente_nombre)
    select l.id, l.conversacion_id, 'fep', 'ad-1', '593900000001', 'José Prueba' from leads l;
insert into ventas (canal, telefono, cliente_nombre) values ('directo', '593900000009', 'Venta huérfana');
"""


@pytest.fixture
def cursor():
    conn = psycopg2.connect(os.environ["SUPABASE_DB_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute(FORMA_ANTERIOR)
            yield cur
    finally:
        conn.rollback()  # el esquema desechable nunca se confirma
        conn.close()


def _aplicar(cur):
    cur.execute(MIGRACION.read_text(encoding="utf-8"))


def test_cada_conversacion_pasa_a_tener_su_contacto_y_su_canal(cursor):
    _aplicar(cursor)
    cursor.execute(
        "select c.canal, c.id_externo, c.origen, ct.telefono, ct.nombre "
        "from conversaciones c join contactos ct on ct.id = c.contacto_id order by c.id"
    )
    assert cursor.fetchall() == [
        ("whatsapp", "593900000001", "anuncio", "593900000001", "José Prueba"),  # 'fep' ahora es 'anuncio'; el nombre sale del lead
        ("whatsapp", "593900000002", "directo", "593900000002", None),
    ]


def test_los_leads_y_las_ventas_quedan_ligados_a_su_contacto(cursor):
    _aplicar(cursor)
    cursor.execute("select l.contacto_id = c.contacto_id from leads l join conversaciones c on c.id = l.conversacion_id")
    assert cursor.fetchall() == [(True,)]
    cursor.execute("select v.origen, v.canal, v.id_anuncio, ct.telefono from ventas v join contactos ct on ct.id = v.contacto_id order by v.id")
    assert cursor.fetchall() == [
        ("anuncio", "whatsapp", "ad-1", "593900000001"),  # el origen de siempre; el canal nuevo es el de mensajería
        ("directo", "whatsapp", None, "593900000009"),  # una venta sin conversación se liga al contacto de su teléfono
    ]


def test_ya_no_existen_las_columnas_que_se_retiraron(cursor):
    _aplicar(cursor)
    cursor.execute(
        "select column_name from information_schema.columns "
        "where table_schema = 't024' and table_name = 'conversaciones' and column_name in ('telefono', 'fep_expira_en')"
    )
    assert cursor.fetchall() == []


def test_la_base_se_niega_a_borrar_una_conversacion_con_historial(cursor):
    _aplicar(cursor)
    cursor.execute("savepoint antes")
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        cursor.execute("delete from conversaciones where id_externo = '593900000001'")  # tiene un lead
    cursor.execute("rollback to savepoint antes")
    cursor.execute("select count(*) from leads")
    assert cursor.fetchone() == (1,)


def test_no_acepta_un_canal_desconocido_ni_dos_conversaciones_iguales_en_un_canal(cursor):
    _aplicar(cursor)
    cursor.execute("select contacto_id from conversaciones limit 1")
    contacto_id = cursor.fetchone()[0]
    cursor.execute("savepoint s1")
    with pytest.raises(psycopg2.errors.CheckViolation):
        cursor.execute(
            "insert into conversaciones (contacto_id, canal, id_externo) values (%s, 'telegram', 'x')", (contacto_id,)
        )
    cursor.execute("rollback to savepoint s1")
    cursor.execute("savepoint s2")
    with pytest.raises(psycopg2.errors.UniqueViolation):
        cursor.execute(
            "insert into conversaciones (contacto_id, canal, id_externo) values (%s, 'whatsapp', '593900000002')", (contacto_id,)
        )
    cursor.execute("rollback to savepoint s2")
    # El MISMO identificador en otro canal es otra conversación (otra persona en otra plataforma): sí se acepta.
    cursor.execute("insert into conversaciones (contacto_id, canal, id_externo) values (%s, 'instagram', '593900000002')", (contacto_id,))


def test_volver_a_correrla_no_cambia_nada_ni_falla(cursor):
    _aplicar(cursor)
    cursor.execute("select count(*) from contactos")
    antes = cursor.fetchone()
    _aplicar(cursor)
    cursor.execute("select count(*) from contactos")
    assert cursor.fetchone() == antes == (3,)
