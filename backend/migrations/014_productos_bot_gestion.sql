-- Fase B del plan de gestión de productos (docs/PLAN_GESTION_PRODUCTOS.md):
-- "Mis productos" en el dashboard. Solo AGREGA columnas y una tabla; el código
-- anterior (el bot de Victoria) sigue funcionando igual con esta migración
-- aplicada, porque no selecciona ninguna de las columnas nuevas.

-- Estado del producto en su ciclo de vida (borrador -> activo -> pausado ...).
-- `activo` (la columna que ya lee Victoria) se mantiene, y una restricción
-- obliga a que SIEMPRE valga lo mismo que `estado = 'activo'`: así no pueden
-- contradecirse ni por un error de código ni por un UPDATE manual.
--
-- El valor por defecto es 'activo' A PROPÓSITO: es lo que hacía el script
-- tools/cargar_producto_bot.py (insertaba con activo = true). La app, en
-- cambio, crea los productos con estado = 'borrador' y activo = false.
alter table productos_bot add column if not exists estado text;

update productos_bot
   set estado = case when activo then 'activo' else 'pausado' end
 where estado is null;

alter table productos_bot alter column estado set default 'activo';
alter table productos_bot alter column estado set not null;

-- Lo último que se supo de Rocketfy sobre este producto (se refresca al crear
-- el borrador, con "Actualizar desde Rocketfy" y al publicar).
alter table productos_bot add column if not exists rocketfy_product_id bigint;
alter table productos_bot add column if not exists costo_rocketfy numeric(12, 2);
alter table productos_bot add column if not exists precio_sugerido_rocketfy numeric(12, 2);
alter table productos_bot add column if not exists stock_ultimo integer;
alter table productos_bot add column if not exists stock_actualizado_en timestamptz;
alter table productos_bot add column if not exists peso_kg numeric(8, 3);
alter table productos_bot add column if not exists imagen_url text;

-- Notas privadas del dueño sobre el producto. NUNCA entran al contexto de
-- Victoria ni se envían al cliente.
alter table productos_bot add column if not exists notas_internas text;

alter table productos_bot add column if not exists publicado_en timestamptz;
alter table productos_bot add column if not exists publicado_por text;

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'productos_bot_estado_valido') then
        alter table productos_bot add constraint productos_bot_estado_valido
            check (estado in ('borrador', 'listo', 'activo', 'pausado', 'agotado', 'archivado'));
    end if;
    if not exists (select 1 from pg_constraint where conname = 'productos_bot_estado_coherente_con_activo') then
        alter table productos_bot add constraint productos_bot_estado_coherente_con_activo
            check ((estado = 'activo') = activo);
    end if;
end
$$;

create index if not exists idx_productos_bot_estado on productos_bot (estado);

-- Quién cambió qué y cuándo. Sin FK a productos_bot a propósito: el historial
-- de un producto sobrevive aunque algún día se borre.
create table if not exists productos_bot_historial (
    id          bigserial primary key,
    sku         text not null,
    accion      text not null,
        -- creado | editado | publicado | reanudado | pausado | archivado
        -- | restaurado | actualizado_rocketfy
    usuario     text,
    cambios     jsonb,
    creado_en   timestamptz not null default now()
);

create index if not exists idx_productos_bot_historial_sku_fecha
    on productos_bot_historial (sku, creado_en desc);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS
-- activado la API pública de Supabase (anon/authenticated) no puede ver ni
-- tocar esta tabla. Mismo criterio que `latido`.
alter table productos_bot_historial enable row level security;
