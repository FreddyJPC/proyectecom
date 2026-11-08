-- ADR-012: productos propios (no Rocketfy), envío por producto, ventas medibles y
-- cola de gestión. Solo AGREGA tablas y columnas con valor por defecto: todo lo que
-- ya existe sigue siendo un producto de Rocketfy y se comporta exactamente igual.
--
-- Qué se agrega y para qué:
--   proveedores            de dónde viene cada producto y CÓMO se cierra su venta
--                          (`cierre`: 'rocketfy' crea el pedido solo; 'manual' lo
--                          gestiona el dueño). Un proveedor nuevo = una fila.
--   categorias_producto    tipo de producto (calzado, ropa…) para medir qué deja más.
--   productos_bot          + proveedor, categoría, costo propio, control de stock,
--                          envío incluido y flete estimado por producto.
--   producto_entregas      opciones de entrega de cada producto (envío o retiro, con
--                          su costo para el cliente y lo que le cuesta al negocio).
--   leads                  + entrega elegida, subtotal y costo de envío.
--   ventas / ventas_lineas una fila por venta cerrada de CUALQUIER proveedor, con
--                          precio y costo CONGELADOS al momento de vender (los
--                          precios cambian: sin esto no se puede calcular la ganancia).
--   solicitudes_gestion    cada aviso al dueño («quiere ver el producto», «pedido
--                          cerrado»…), guardado en la base: Telegram es best-effort
--                          y puede fallar, esta tabla no.

-- ---------------------------------------------------------------------------
-- Proveedores
-- ---------------------------------------------------------------------------
create table if not exists proveedores (
    id          bigserial primary key,
    clave       text not null unique,
    nombre      text not null,
    cierre      text not null check (cierre in ('rocketfy', 'manual')),
    activo      boolean not null default true,
    creado_en   timestamptz not null default now()
);

insert into proveedores (id, clave, nombre, cierre) values
    (1, 'rocketfy', 'Rocketfy', 'rocketfy'),
    (2, 'propio', 'Producto propio', 'manual')
on conflict (id) do nothing;

select setval(pg_get_serial_sequence('proveedores', 'id'), greatest((select max(id) from proveedores), 2));

-- ---------------------------------------------------------------------------
-- Categorías
-- ---------------------------------------------------------------------------
create table if not exists categorias_producto (
    id          bigserial primary key,
    nombre      text not null check (length(btrim(nombre)) > 0),
    activo      boolean not null default true,
    creado_en   timestamptz not null default now()
);

create unique index if not exists uq_categorias_producto_nombre on categorias_producto (lower(btrim(nombre)));

-- ---------------------------------------------------------------------------
-- Productos
-- ---------------------------------------------------------------------------
alter table productos_bot
    add column if not exists proveedor_id bigint not null default 1 references proveedores (id),
    add column if not exists categoria_id bigint references categorias_producto (id),
    -- Lo que le cuesta el producto al dueño (solo productos propios; los de Rocketfy usan costo_rocketfy).
    add column if not exists costo_propio numeric(12, 2) check (costo_propio is null or costo_propio >= 0),
    -- Solo productos propios: true = se lleva la cuenta en `stock_ultimo` y se descuenta al vender;
    -- false = siempre disponible. Los de Rocketfy ignoran esta columna (su stock lo da Rocketfy).
    add column if not exists controla_stock boolean not null default true,
    -- true = el precio ya trae el envío; false = se cobra aparte según `producto_entregas`.
    add column if not exists envio_incluido boolean not null default true,
    -- Lo que cuesta el flete de ESTE producto (estimado). Si es null se usa el envío estimado general.
    add column if not exists costo_flete_estimado numeric(12, 2)
        check (costo_flete_estimado is null or costo_flete_estimado >= 0);

create index if not exists idx_productos_bot_proveedor on productos_bot (proveedor_id);
create index if not exists idx_productos_bot_categoria on productos_bot (categoria_id);

-- Numeración de los SKU de productos propios (PROP-0001, PROP-0002…).
create sequence if not exists productos_propios_seq;

-- ---------------------------------------------------------------------------
-- Opciones de entrega por producto
-- ---------------------------------------------------------------------------
create table if not exists producto_entregas (
    id              bigserial primary key,
    producto_sku    text not null references productos_bot (sku) on update cascade on delete cascade,
    nombre          text not null check (length(btrim(nombre)) > 0),
    tipo            text not null check (tipo in ('envio', 'retiro')),
    -- Lo que paga el cliente por esta opción (0 = gratis).
    costo_cliente   numeric(12, 2) not null default 0 check (costo_cliente >= 0),
    -- Lo que le cuesta al negocio (opcional: alimenta la ganancia real de cada venta).
    costo_negocio   numeric(12, 2) check (costo_negocio is null or costo_negocio >= 0),
    -- A quién aplica un envío: estos cantones, estas provincias o, con resto_del_pais, todo destino
    -- que no cubra otra opción de envío con cantones/provincias. Un retiro aplica a cualquiera.
    cantones        text[] not null default '{}',
    provincias      text[] not null default '{}',
    resto_del_pais  boolean not null default false,
    direccion_retiro text,
    tiempo_entrega  text,
    activo          boolean not null default true,
    orden           integer not null default 0,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

create index if not exists idx_producto_entregas_sku on producto_entregas (producto_sku, orden, id);

-- ---------------------------------------------------------------------------
-- Leads: entrega elegida y desglose del total
-- ---------------------------------------------------------------------------
alter table leads
    add column if not exists subtotal numeric(12, 2),
    add column if not exists entrega_opcion_id bigint,
    add column if not exists entrega_nombre text,
    add column if not exists entrega_tipo text,
    add column if not exists costo_envio numeric(12, 2) not null default 0;

-- ---------------------------------------------------------------------------
-- Ventas
-- ---------------------------------------------------------------------------
create table if not exists ventas (
    id                  bigserial primary key,
    lead_id             bigint unique references leads (id) on delete set null,
    conversacion_id     bigint references conversaciones (id) on delete set null,
    proveedor_id        bigint not null references proveedores (id),
    canal               text not null default 'directo',
    id_anuncio          text,
    estado              text not null check (estado in ('por_gestionar', 'gestionada', 'despachada', 'cancelada')),
    metodo_pago         text,
    cliente_nombre      text,
    telefono            text,
    direccion           text,
    canton              text,
    provincia           text,
    entrega_tipo        text,
    entrega_nombre      text,
    subtotal            numeric(12, 2) not null,
    costo_envio_cliente numeric(12, 2) not null default 0,
    total               numeric(12, 2) not null,
    costo_productos     numeric(12, 2),
    costo_envio_negocio numeric(12, 2),
    id_pedido_local     bigint,
    id_pedido_rocketfy  bigint,
    cerrada_en          timestamptz not null default now(),
    gestionada_en       timestamptz,
    gestionada_por      text
);

create index if not exists idx_ventas_cerrada on ventas (cerrada_en desc);
create index if not exists idx_ventas_proveedor on ventas (proveedor_id, cerrada_en desc);
create index if not exists idx_ventas_estado on ventas (estado);

create table if not exists ventas_lineas (
    id                  bigserial primary key,
    venta_id            bigint not null references ventas (id) on delete cascade,
    producto_sku        text not null,
    producto_nombre     text not null,
    variante            text,
    categoria_id        bigint references categorias_producto (id) on delete set null,
    categoria_nombre    text,
    cantidad            integer not null check (cantidad >= 1),
    precio_unitario     numeric(12, 2) not null,
    costo_unitario      numeric(12, 2)
);

create index if not exists idx_ventas_lineas_venta on ventas_lineas (venta_id);
create index if not exists idx_ventas_lineas_sku on ventas_lineas (producto_sku);
create index if not exists idx_ventas_lineas_categoria on ventas_lineas (categoria_id);

-- ---------------------------------------------------------------------------
-- Solicitudes de gestión («Por gestionar»)
-- ---------------------------------------------------------------------------
create table if not exists solicitudes_gestion (
    id              bigserial primary key,
    conversacion_id bigint not null references conversaciones (id) on delete cascade,
    lead_id         bigint references leads (id) on delete set null,
    venta_id        bigint references ventas (id) on delete set null,
    -- quiere_comprar | quiere_pagar | pide_envio | quiere_ver_producto | quiere_negociar |
    -- sin_cobertura | pedido_cerrado | otro (la lista vive en el código para poder crecer).
    tipo            text not null,
    detalle         text,
    estado          text not null default 'pendiente' check (estado in ('pendiente', 'atendida')),
    nota_atencion   text,
    atendida_por    text,
    creada_en       timestamptz not null default now(),
    actualizada_en  timestamptz not null default now(),
    atendida_en     timestamptz
);

-- Una sola solicitud PENDIENTE por conversación: la primera intención la crea y las siguientes
-- la completan (p. ej. «quiere comprar» se convierte en «pedido cerrado» con todos los datos).
create unique index if not exists uq_solicitud_pendiente_por_conversacion
    on solicitudes_gestion (conversacion_id) where estado = 'pendiente';
create index if not exists idx_solicitudes_estado on solicitudes_gestion (estado, creada_en desc);

-- ---------------------------------------------------------------------------
-- Las ventas ya despachadas por Rocketfy pasan a la tabla nueva (idempotente).
-- ---------------------------------------------------------------------------
insert into ventas (
    lead_id, conversacion_id, proveedor_id, canal, id_anuncio, estado, metodo_pago,
    cliente_nombre, telefono, direccion, canton, provincia,
    subtotal, costo_envio_cliente, total, costo_productos,
    id_pedido_local, id_pedido_rocketfy, cerrada_en
)
select l.id, l.conversacion_id, 1, coalesce(c.origen, 'directo'), c.id_anuncio, 'despachada', l.metodo_pago,
       l.nombre_cliente, l.telefono, l.direccion, l.canton, l.provincia,
       coalesce(l.total, 0), 0, coalesce(l.total, 0),
       case when pb.costo_rocketfy is not null then pb.costo_rocketfy * l.cantidad end,
       l.id_pedido_local, l.id_pedido_rocketfy, l.actualizado_en
  from leads l
  left join conversaciones c on c.id = l.conversacion_id
  left join productos_bot pb on pb.sku = l.producto_sku
 where l.estado = 'despachado'
   and l.producto_sku is not null
   and not exists (select 1 from ventas v where v.lead_id = l.id);

insert into ventas_lineas (venta_id, producto_sku, producto_nombre, variante, cantidad, precio_unitario, costo_unitario)
select v.id, l.producto_sku, coalesce(l.producto_nombre, l.producto_sku), l.producto_variante, l.cantidad,
       round(coalesce(l.total, 0) / l.cantidad, 2), pb.costo_rocketfy
  from ventas v
  join leads l on l.id = v.lead_id
  left join productos_bot pb on pb.sku = l.producto_sku
 where not exists (select 1 from ventas_lineas vl where vl.venta_id = v.id);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS activado la
-- API pública de Supabase (clave anónima) no puede leer ni escribir estas tablas.
alter table proveedores enable row level security;
alter table categorias_producto enable row level security;
alter table producto_entregas enable row level security;
alter table ventas enable row level security;
alter table ventas_lineas enable row level security;
alter table solicitudes_gestion enable row level security;
