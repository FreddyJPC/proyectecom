-- Fase A del plan de gestión de productos (docs/PLAN_GESTION_PRODUCTOS.md):
-- ventas seguras. Solo AGREGA columnas con valor por defecto y una tabla
-- nueva; no toca ni borra datos existentes.

-- Unidades que lleva el pedido de un lead. Hasta ahora el pedido a Rocketfy
-- salía siempre con cantidad = 1 (fija en el código) aunque el total lo
-- hubiera escrito Victoria para más unidades.
alter table leads
    add column if not exists cantidad integer not null default 1 check (cantidad >= 1);

-- Máximo de unidades que Victoria acepta por pedido de este producto. Por
-- defecto 1: el precio y el margen se calculan con el flete de UNA unidad, y
-- el flete de más unidades no se puede conocer de antemano (Rocketfy no tiene
-- cotizador). Se sube producto por producto cuando se comprueba que el margen
-- aguanta.
alter table productos_bot
    add column if not exists max_unidades_por_pedido integer not null default 1
    check (max_unidades_por_pedido >= 1);

-- Cuando Rocketfy rechaza una confirmación diciendo "el importe mínimo del
-- pedido debe ser ... ($18.47)", ese monto (valor de los productos + costo
-- de envío de ESE destino) es la única pista del costo real de envío que
-- tenemos sin cotizador. Se guarda para calibrar el envío estimado de la
-- calculadora de precios (Fase C). Sin FK a productos_bot a propósito: la
-- observación vale aunque el producto se archive después.
create table if not exists rocketfy_minimos_observados (
    id          bigserial primary key,
    sku         text,
    canton      text,
    provincia   text,
    cantidad    integer,
    minimo      numeric(12, 2) not null,
    mensaje     text not null,
    creado_en   timestamptz not null default now()
);

create index if not exists idx_rocketfy_minimos_sku_fecha
    on rocketfy_minimos_observados (sku, creado_en desc);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS
-- activado la API pública de Supabase (anon/authenticated) no puede ver ni
-- tocar esta tabla. Mismo criterio que la tabla `latido`.
alter table rocketfy_minimos_observados enable row level security;
