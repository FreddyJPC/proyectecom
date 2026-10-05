"""
Aplica los archivos .sql de backend/migrations/ contra SUPABASE_DB_URL,
en orden por nombre de archivo, registrando cada uno aplicado en
schema_migrations para no volver a correrlo.

Uso:
    .venv/bin/python tools/apply_migrations.py
"""
import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = BACKEND_DIR / "migrations"

load_dotenv(BACKEND_DIR / ".env")

DB_URL = os.getenv("SUPABASE_DB_URL")
if not DB_URL:
    sys.exit("SUPABASE_DB_URL no está definido en backend/.env")


def main():
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                create table if not exists schema_migrations (
                    filename    text primary key,
                    aplicada_en timestamptz not null default now()
                )
            """)
            conn.commit()

            cur.execute("select filename from schema_migrations")
            ya_aplicadas = {row[0] for row in cur.fetchall()}

        archivos = sorted(p for p in MIGRATIONS_DIR.glob("*.sql"))
        if not archivos:
            print("No hay archivos .sql en migrations/.")
            return

        for archivo in archivos:
            if archivo.name in ya_aplicadas:
                print(f"[SKIP] {archivo.name} (ya aplicada)")
                continue

            sql = archivo.read_text()
            with conn.cursor() as cur:
                try:
                    cur.execute(sql)
                    cur.execute(
                        "insert into schema_migrations (filename) values (%s)",
                        (archivo.name,),
                    )
                    conn.commit()
                    print(f"[OK]   {archivo.name}")
                except Exception as exc:
                    conn.rollback()
                    print(f"[FAIL] {archivo.name}: {exc}")
                    raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
