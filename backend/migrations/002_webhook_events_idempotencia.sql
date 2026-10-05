-- Ajuste a partir de docs/Rocket-Webhooks-Guia-Integrador.md: la clave de
-- idempotencia recomendada por Rocketfy es (order_id, status_id, event_date),
-- y conviene tener shopify_order_id como columna propia (es la forma directa
-- de casar el evento con pedidos.id_local sin extraer del jsonb cada vez).

alter table webhook_events
    add column if not exists event_date timestamptz,
    add column if not exists shopify_order_id bigint;

create unique index if not exists uq_webhook_events_idempotencia
    on webhook_events (id_rocketfy, status_id, event_date);

create index if not exists idx_webhook_events_shopify_order_id
    on webhook_events (shopify_order_id);
