-- Fase 2 - Etapa 3 (Incidencias y Alertas): StockWatcherService detectaba
-- "stock bajo" y "cambio de precio" desde el principio (Etapa 5 de Fase 1),
-- pero solo lo mandaba al log -- nadie fuera de la terminal del servidor
-- podía verlo. Esta tabla persiste esas alertas como eventos consultables,
-- igual que webhook_events ya hace con los avisos de Rocketfy.

create table if not exists alertas_stock (
    id              bigserial primary key,
    sku             text not null references skus_monitoreados (sku) on delete cascade,
    tipo            text not null,
        -- 'stock_bajo' | 'cambio_precio'
    detalle         jsonb not null,
        -- stock_bajo: {"stock": N, "umbral": N}
        -- cambio_precio: {"precioAnterior": "X.XX", "precioActual": "Y.YY"}
    creado_en       timestamptz not null default now()
);

create index if not exists idx_alertas_stock_sku_fecha
    on alertas_stock (sku, creado_en desc);
create index if not exists idx_alertas_stock_creado_en
    on alertas_stock (creado_en desc);
