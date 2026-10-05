-- Fase 3 - Bot de WhatsApp (Victoria). Datos de venta que el bot va
-- recopilando durante la conversación -- se llena progresivamente. Solo
-- cuando estado = 'listo_para_despacho' se llama a
-- PedidoService.crear_y_confirmar() y se completan id_pedido_local /
-- id_pedido_rocketfy. Esta tabla NUNCA reemplaza ni se fusiona con
-- `pedidos` (Fase 1) -- son a propósito dos tablas separadas: `pedidos`
-- es el contrato ya cerrado con Rocketfy, `leads` es la venta en curso.

create table if not exists leads (
    id                      bigserial primary key,
    conversacion_id         bigint not null references conversaciones (id) on delete cascade,

    -- Datos del cliente (se van llenando durante la conversación)
    nombre_cliente          text,
    telefono                text,
    direccion               text,
    canton                  text,
    provincia               text,

    -- Datos del producto
    producto_sku            text,
    producto_nombre         text,
    total                   numeric(12, 2),  -- Decimal en Python, nunca float (directriz 5)

    -- Pago
    metodo_pago             text,
        -- contraentrega | transferencia
    estado_pago             text default 'pendiente',
        -- pendiente | confirmado
    captura_pago_url        text,

    -- Estado del lead en el embudo de ventas
    estado                  text not null default 'recopilando_datos',
        -- recopilando_datos   -> bot recopilando nombre, dirección, producto
        -- esperando_pago      -> bot esperando captura de transferencia
        -- listo_para_despacho -> pago confirmado, listo para llamar a PedidoService
        -- despachado          -> PedidoService ejecutado exitosamente

    -- Referencias al pedido en Rocketfy (se llenan solo al cerrar la venta)
    id_pedido_local         bigint,   -- referencia a pedidos.id_local
    id_pedido_rocketfy      bigint,   -- referencia a pedidos.id_rocketfy

    creado_en               timestamptz not null default now(),
    actualizado_en          timestamptz not null default now()
);

create index if not exists idx_leads_conversacion on leads (conversacion_id);
create index if not exists idx_leads_estado on leads (estado);
