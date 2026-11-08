-- Parámetros del sistema controlados desde la app (ADR-011, docs/PLAN_PARAMETRIZACION.md,
-- fase P1). Solo AGREGA dos tablas: nada de lo existente cambia, y mientras estas tablas
-- estén vacías el sistema se comporta exactamente igual que antes (cada parámetro vale
-- lo que dice la variable del servidor o, si no existe, su valor por defecto del código).
--
-- `parametros_sistema` guarda SOLO lo que se cambió desde la app: una fila por parámetro.
-- Borrar la fila = «restaurar el valor original». El catálogo (nombre, explicación,
-- tipo, rango y valor por defecto de cada parámetro) vive en el código
-- (backend/src/config/parametros/catalogo.py): la tabla solo guarda el valor, como
-- texto, y el código lo valida al leerlo y al guardarlo.
create table if not exists parametros_sistema (
    clave            text primary key,
    valor            text        not null,
    actualizado_por  text,
    actualizado_en   timestamptz not null default now()
);

-- Quién cambió qué y cuándo: es el «deshacer» del módulo. `valor_nuevo` vacío (NULL)
-- significa que se restauró el valor original; `valor_anterior` vacío, que antes no
-- había ningún valor guardado.
create table if not exists parametros_historial (
    id               bigserial primary key,
    clave            text        not null,
    valor_anterior   text,
    valor_nuevo      text,
    usuario          text,
    creado_en        timestamptz not null default now()
);

create index if not exists idx_parametros_historial_fecha
    on parametros_historial (creado_en desc, id desc);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS activado la
-- API pública de Supabase (anon/authenticated) no puede ver ni tocar estas tablas. Mismo
-- criterio que `ajustes_negocio`, `latido` y `productos_bot_historial`.
alter table parametros_sistema enable row level security;
alter table parametros_historial enable row level security;
