-- Precios, regateo, ofertas y varios productos por pedido (ADR-017, docs/PLAN_MODULO_ANUNCIOS.md v2.0).
--
-- Principio: el dueño pone las reglas, el CÓDIGO calcula el precio (una «cotización») y Victoria solo la comunica.
-- Todo lo nuevo viene APAGADO (columnas nulas, tablas vacías): sin reglas configuradas el total es exactamente el de antes.
-- Solo AGREGA objetos (idempotente); no edita ni borra datos existentes.

-- ---------------------------------------------------------------------------
-- 1. Reglas por producto («Precios y descuentos» en la ficha)
-- ---------------------------------------------------------------------------
alter table productos_bot
    add column if not exists transferencia_tipo text,
        -- precio (precio fijo por unidad) | porcentaje | monto (dólares menos por unidad); null = usa el valor del negocio
    add column if not exists transferencia_valor numeric(12, 2),
    add column if not exists regateo_tipo text,
        -- porcentaje | monto (por unidad); null = Victoria NO regatea este producto
    add column if not exists regateo_valor numeric(12, 2),
    add column if not exists envio_gratis_desde_unidades integer,
        -- solo para productos con envío aparte: desde cuántas unidades el envío es gratis
    add column if not exists envio_gratis_desde_monto numeric(12, 2);
        -- o desde qué subtotal (en dólares)

alter table productos_bot drop constraint if exists ck_productos_transferencia;
alter table productos_bot add constraint ck_productos_transferencia check (
    (transferencia_tipo is null and transferencia_valor is null)
    or (transferencia_tipo in ('precio', 'porcentaje', 'monto') and transferencia_valor is not null and transferencia_valor > 0
        and (transferencia_tipo <> 'porcentaje' or transferencia_valor < 100))
);
alter table productos_bot drop constraint if exists ck_productos_regateo;
alter table productos_bot add constraint ck_productos_regateo check (
    (regateo_tipo is null and regateo_valor is null)
    or (regateo_tipo in ('porcentaje', 'monto') and regateo_valor is not null and regateo_valor > 0
        and (regateo_tipo <> 'porcentaje' or regateo_valor < 100))
);
alter table productos_bot drop constraint if exists ck_productos_envio_gratis;
alter table productos_bot add constraint ck_productos_envio_gratis check (
    (envio_gratis_desde_unidades is null or envio_gratis_desde_unidades >= 1)
    and (envio_gratis_desde_monto is null or envio_gratis_desde_monto > 0)
);

-- Precio por cantidad: «2 por $45», «3 por $60». Precio TOTAL de esa cantidad.
create table if not exists producto_escalas (
    id              bigserial primary key,
    producto_sku    text not null references productos_bot (sku) on delete cascade,
    cantidad        integer not null check (cantidad >= 2),
    precio_total    numeric(12, 2) not null check (precio_total > 0),
    creado_en       timestamptz not null default now(),
    unique (producto_sku, cantidad)
);

-- ---------------------------------------------------------------------------
-- 2. Valor por defecto del negocio para la transferencia (Ajustes)
-- ---------------------------------------------------------------------------
alter table ajustes_negocio
    add column if not exists transferencia_tipo text,
        -- porcentaje | monto; null = no hay precio especial por transferencia
    add column if not exists transferencia_valor numeric(12, 2);

alter table ajustes_negocio drop constraint if exists ck_ajustes_transferencia;
alter table ajustes_negocio add constraint ck_ajustes_transferencia check (
    (transferencia_tipo is null and transferencia_valor is null)
    or (transferencia_tipo in ('porcentaje', 'monto') and transferencia_valor is not null and transferencia_valor > 0
        and (transferencia_tipo <> 'porcentaje' or transferencia_valor < 100))
);

-- ---------------------------------------------------------------------------
-- 3. Ofertas: combos y promociones (lo que promete un anuncio)
-- ---------------------------------------------------------------------------
create table if not exists ofertas (
    id                      bigserial primary key,
    nombre                  text not null,
    descripcion             text,
        -- qué incluye y sus condiciones, en palabras para Victoria
    texto_anuncio           text,
        -- lo que dice el anuncio, tal cual (Victoria lo recibe)
    precio                  numeric(12, 2) not null check (precio > 0),
        -- precio TOTAL de la oferta (una vez)
    envio_incluido          boolean not null default true,
    desde                   timestamptz,
    hasta                   timestamptz,
    cupo                    integer check (cupo is null or cupo >= 1),
        -- máximo de ventas de esta oferta (null = sin límite)
    maximo_por_cliente      integer not null default 1 check (maximo_por_cliente >= 1),
        -- veces que un mismo cliente puede llevarla en un pedido
    visibilidad             text not null default 'anuncio' check (visibilidad in ('anuncio', 'publica')),
        -- anuncio: solo quien llega por sus anuncios (regla P6); publica: Victoria puede ofrecerla a cualquiera
    regateo_tipo            text,
    regateo_valor           numeric(12, 2),
        -- null = no se regatea (regla P7: el combo ya es el descuento)
    transferencia_tipo      text,
    transferencia_valor     numeric(12, 2),
        -- precio | porcentaje | monto; null = sin precio especial por transferencia
    bajo_margen_autorizado  boolean not null default false,
        -- el dueño aceptó a propósito venderla bajo su margen mínimo
    estado                  text not null default 'activa' check (estado in ('activa', 'pausada', 'archivada')),
    creada_en               timestamptz not null default now(),
    creada_por              text,
    actualizada_en          timestamptz not null default now(),
    check (hasta is null or desde is null or hasta > desde),
    check ((regateo_tipo is null and regateo_valor is null)
           or (regateo_tipo in ('porcentaje', 'monto') and regateo_valor > 0 and (regateo_tipo <> 'porcentaje' or regateo_valor < 100))),
    check ((transferencia_tipo is null and transferencia_valor is null)
           or (transferencia_tipo in ('precio', 'porcentaje', 'monto') and transferencia_valor > 0
               and (transferencia_tipo <> 'porcentaje' or transferencia_valor < 100)))
);

create table if not exists oferta_items (
    id              bigserial primary key,
    oferta_id       bigint not null references ofertas (id) on delete cascade,
    producto_sku    text not null references productos_bot (sku) on delete restrict,
    cantidad        integer not null default 1 check (cantidad >= 1),
    variante        text,
        -- variante fija de la oferta (null = la elige el cliente)
    orden           integer not null default 0
);
create index if not exists idx_oferta_items_oferta on oferta_items (oferta_id, orden, id);
create index if not exists idx_oferta_items_sku on oferta_items (producto_sku);

-- Un anuncio apunta a UN producto (como antes) o a UNA oferta (nuevo). Los vínculos existentes no cambian.
alter table anuncios_productos alter column producto_sku drop not null;
alter table anuncios_productos add column if not exists oferta_id bigint references ofertas (id) on delete restrict;
alter table anuncios_productos drop constraint if exists ck_anuncios_un_vinculo;
alter table anuncios_productos add constraint ck_anuncios_un_vinculo check ((producto_sku is null) <> (oferta_id is null));
create index if not exists idx_anuncios_productos_oferta on anuncios_productos (oferta_id);

-- ---------------------------------------------------------------------------
-- 4. El pedido en curso (lead): varias líneas y la cotización del código
-- ---------------------------------------------------------------------------
alter table leads
    add column if not exists lineas jsonb,
        -- las líneas del pedido: [{"tipo":"producto","sku":..,"cantidad":..,"variante":..} | {"tipo":"oferta","oferta_id":..,"cantidad":..}]
        -- null = pedido de un solo producto guardado en producto_sku / cantidad (como siempre)
    add column if not exists cotizacion jsonb,
        -- el desglose que calculó el código (líneas, descuentos con su motivo, envío, totales). Solo lectura para Victoria
    add column if not exists total_transferencia numeric(12, 2),
        -- el total si paga por transferencia (null = igual que contra entrega)
    add column if not exists regateo jsonb;
        -- {"acordado": "45.00", "base": "50.00", "rondas": 1, "contraoferta": "48.00"}: estado del regateo de este pedido

-- ---------------------------------------------------------------------------
-- 5. La venta guarda cuánto se descontó y por qué (para medir si conviene)
-- ---------------------------------------------------------------------------
alter table ventas
    add column if not exists subtotal_lista numeric(12, 2),
        -- lo que habría costado a precio de lista (sin ningún descuento)
    add column if not exists descuento_total numeric(12, 2) not null default 0,
    add column if not exists descuentos jsonb,
        -- [{"motivo": "regateo|escala|oferta|transferencia|envio_gratis", "monto": "5.00"}]
    add column if not exists cotizacion jsonb;

alter table ventas_lineas
    add column if not exists oferta_id bigint references ofertas (id) on delete set null,
    add column if not exists precio_lista_unitario numeric(12, 2);
create index if not exists idx_ventas_lineas_oferta on ventas_lineas (oferta_id);

-- Como el resto de las tablas: seguridad por filas activada y sin políticas (solo el servidor accede, con su propio rol).
alter table producto_escalas enable row level security;
alter table ofertas enable row level security;
alter table oferta_items enable row level security;
