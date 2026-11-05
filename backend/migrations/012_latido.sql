-- Latido de la base de datos (heartbeat).
--
-- Por qué existe: en el plan gratuito, Supabase pausa el proyecto si en 7
-- días ve "poca actividad de base de datos" (docs: "unas pocas consultas de
-- usuario por día suelen bastar", sin garantía). Los jobs de reconciliación
-- y stock ya generan actividad, pero este latido la hace explícita y
-- medible: un job propio (src/jobs/latido) actualiza esta fila cada 6 h.
--
-- Es una tabla de UNA sola fila (id = 1, forzado por el check): nunca
-- crece, así que no ocupa espacio ni hace falta limpiarla.
create table if not exists latido (
    id            smallint primary key default 1 check (id = 1),
    ultimo_latido timestamptz not null default now(),
    contador      bigint not null default 0   -- cuántos latidos van (sirve para verificar que sube)
);

insert into latido (id) values (1) on conflict (id) do nothing;

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS
-- activado la API pública de Supabase (anon/authenticated) no puede ver ni
-- tocar esta tabla.
alter table latido enable row level security;
