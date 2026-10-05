-- Migración inicial — memoria operativa mínima de la integración Rocketfy.
-- NO es una base de negocio/CRM: Rocketfy sigue siendo la fuente de verdad
-- del estado del pedido, catálogo y precios. Estas tablas existen solo para
-- garantizar idempotencia, auditoría y coordinación de jobs (ver ADR-002 y
-- ADR-006 en PROGRESS.md).

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- pedidos: mapping id_local (nuestro "id"/"shopify_order_id") <-> id_rocketfy.
-- Se escribe el id_rocketfy INMEDIATAMENTE al recibirlo de /orders/create,
-- antes de cualquier otro paso, para poder detectar reintentos duplicados.
-- ---------------------------------------------------------------------------
create table if not exists pedidos (
    id_local            bigint primary key,
    id_rocketfy         bigint unique,
    estado_local        text not null default 'pendiente_creacion',
        -- pendiente_creacion | creado | confirmado | rechazado | incompleto | error
    status_id_rocketfy  integer,
        -- último status_id oficial de Rocketfy conocido (cache, no fuente de verdad)
    payload_creacion    jsonb not null,
    mensaje_error       text,
    creado_en           timestamptz not null default now(),
    confirmado_en       timestamptz,
    actualizado_en      timestamptz not null default now()
);

create index if not exists idx_pedidos_id_rocketfy on pedidos (id_rocketfy);
create index if not exists idx_pedidos_estado_local on pedidos (estado_local);

-- ---------------------------------------------------------------------------
-- webhook_events: auditoría cruda de cada evento recibido de Rocketfy.
-- Retención recomendada por el proveedor: al menos 90 días.
-- ---------------------------------------------------------------------------
create table if not exists webhook_events (
    id              bigserial primary key,
    id_rocketfy     bigint not null,
    status_id       integer not null,
    payload         jsonb not null,
    recibido_en     timestamptz not null default now(),
    procesado       boolean not null default false,
    procesado_en    timestamptz
);

create index if not exists idx_webhook_events_id_rocketfy on webhook_events (id_rocketfy);
create index if not exists idx_webhook_events_procesado on webhook_events (procesado) where not procesado;

-- ---------------------------------------------------------------------------
-- job_locks: coordinación de jobs en background (reconciliación, stock_watcher)
-- para que no corran en paralelo si hay más de una instancia del backend.
-- Mismo patrón que WEBSERVICES/src/cronTask/despacho_dia_actual.py (st_cron_lock).
-- ---------------------------------------------------------------------------
create table if not exists job_locks (
    job_name    text primary key,
    locked_at   timestamptz not null default now(),
    instancia   text
);

-- ---------------------------------------------------------------------------
-- skus_monitoreados: configuración de qué SKUs se vigilan para el
-- requerimiento 4 (pausar campañas si el stock cae bajo el umbral).
-- ---------------------------------------------------------------------------
create table if not exists skus_monitoreados (
    sku                     text primary key,
    umbral_stock_minimo     integer not null default 5,
    activo                  boolean not null default true,
    creado_en               timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- stock_snapshots: histórico de stock/precio por SKU vigilado, para detectar
-- cruce de umbral y cambios de precio (requerimientos 4 y 7).
-- ---------------------------------------------------------------------------
create table if not exists stock_snapshots (
    id              bigserial primary key,
    sku             text not null references skus_monitoreados (sku) on delete cascade,
    stock           integer not null,
    price           numeric(12, 2) not null,
    capturado_en    timestamptz not null default now()
);

create index if not exists idx_stock_snapshots_sku_fecha
    on stock_snapshots (sku, capturado_en desc);
