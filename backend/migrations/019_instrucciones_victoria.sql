-- Instrucciones de Victoria editables desde la app (ADR-011, docs/PLAN_PARAMETRIZACION.md, fase P3).
-- Solo AGREGA una tabla: mientras no haya ninguna versión PUBLICADA, Victoria sigue usando
-- exactamente las instrucciones del archivo del código (backend/src/routes/whatsapp/
-- victoria_system_prompt.txt), que también es el respaldo si algo falla al leer esta tabla.
--
-- Cada fila es una versión de las secciones EDITABLES (el resto del texto, el que está atado al
-- código —herramientas, ficha del producto, estado del cliente, fecha—, no se guarda aquí).
--   borrador  : lo que se está editando y se puede probar en «Probar con Victoria»; a lo sumo uno.
--   publicada : lo que usa Victoria con los clientes reales; a lo sumo una.
--   archivada : versiones publicadas que fueron reemplazadas (quedan para volver a ellas).
-- Volver a las instrucciones originales = dejar de tener una versión publicada.
create table if not exists victoria_instrucciones_versiones (
    id           bigserial primary key,
    secciones    jsonb       not null,
    estado       text        not null check (estado in ('borrador', 'publicada', 'archivada')),
    nota         text,
    creado_por   text,
    creado_en    timestamptz not null default now(),
    publicada_en timestamptz
);

-- Las reglas «a lo sumo uno» las garantiza la base, no solo el código.
create unique index if not exists victoria_instrucciones_un_borrador
    on victoria_instrucciones_versiones (estado) where estado = 'borrador';
create unique index if not exists victoria_instrucciones_una_publicada
    on victoria_instrucciones_versiones (estado) where estado = 'publicada';

create index if not exists idx_victoria_instrucciones_fecha
    on victoria_instrucciones_versiones (creado_en desc, id desc);

-- Sin policies (mismo criterio que `ajustes_negocio` y `parametros_sistema`).
alter table victoria_instrucciones_versiones enable row level security;
