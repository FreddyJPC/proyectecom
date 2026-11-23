-- Módulo «Inmuebles» (docs/PLAN_INMUEBLE.md, bitácora docs/BITACORA_INMUEBLES.md). Pedido de Freddy, 2026-11-23.
--
-- Para qué: que los mensajes de los anuncios de propiedades (hoy, la casa en venta en Guayaquil) los atienda un asistente
-- APARTE de Victoria: informa con la ficha de la propiedad, manda la ubicación y las fotos y toma pedidos de visita, sin vender
-- ni negociar. Pensado para un portafolio: muchas propiedades, cada una con su ficha, su material y sus anuncios.
--
-- Qué agrega:
--   1. `inmuebles`: la ficha de cada propiedad (lo que el asistente puede decir).
--   2. `inmuebles_material`: fotos y videos de cada propiedad (mismo bucket `productos` de Storage, carpeta `i<id>`).
--   3. `inmuebles_anuncios`: qué anuncio de Meta habla de qué propiedad (el cliente que llega por él va al asistente de inmuebles).
--   4. `visitas`: la agenda. El asistente solo REGISTRA el pedido de visita; el dueño la confirma a mano.
--   5. `numeros_whatsapp`: los números del negocio en la API y qué asistente atiende cada uno (hoy uno solo: el de Victoria).
--   6. `conversaciones`: quién la atiende (`asistente`), de qué propiedad se habla (`inmueble_id`) y por qué número del negocio
--      llegó (`numero_negocio`; null = el número principal, el de Victoria). Una persona que le escribe a dos números del
--      negocio tiene dos conversaciones (una por número): por eso cambia la clave única.
--
-- Todo es nuevo o con valor por defecto: las conversaciones que ya existen quedan igual (asistente «ventas», número principal).

-- 1. Ficha de la propiedad ------------------------------------------------------------------------------------------------
create table if not exists inmuebles (
    id                   bigserial primary key,
    codigo               text not null unique,              -- corto y fijo, p. ej. «CASA-GYE-01»; lo usa el asistente
    titulo               text not null,
    tipo                 text not null default 'casa',
    operacion            text not null default 'venta',
    estado               text not null default 'borrador',
    -- Precio: el dinero nunca es float. Si se dice o no, y si es negociable, lo decide el dueño por propiedad.
    precio               numeric(12, 2),
    mostrar_precio       boolean not null default false,
    precio_negociable    boolean,                           -- null = el asistente no opina: lo deja al dueño
    ciudad               text,
    sector               text,
    direccion            text,
    referencia_llegada   text,                              -- cómo llegar, puntos de referencia
    latitud              numeric(9, 6),
    longitud             numeric(9, 6),
    terreno_m2           numeric(10, 2),
    construccion_m2      numeric(10, 2),
    frente_m             numeric(8, 2),
    fondo_m              numeric(8, 2),
    pisos                integer,
    habitaciones         integer,
    banos                numeric(4, 1),                     -- 2.5 = dos baños y medio
    parqueaderos         integer,
    uso                  text,                              -- residencial | comercial | mixto
    descripcion          text,
    caracteristicas      text,                              -- lista libre: patio, cisterna, terraza…
    servicios            text,                              -- agua, luz, alcantarillado, internet…
    documentacion        text,                              -- escrituras, impuestos al día…
    preguntas_frecuentes text,
    temas_no_responder   text,
    horarios_visita      text,                              -- cuándo se puede visitar (el asistente lo propone, nunca confirma)
    encargado_visitas    text,                              -- quién enseña la propiedad (interno, no se le dice al cliente)
    notas_internas       text,
    creado_en            timestamptz not null default now(),
    actualizado_en       timestamptz not null default now(),
    constraint ck_inmuebles_tipo check (tipo in ('casa', 'departamento', 'terreno', 'local', 'oficina', 'bodega', 'otro')),
    constraint ck_inmuebles_operacion check (operacion in ('venta', 'alquiler')),
    constraint ck_inmuebles_estado check (estado in ('borrador', 'activo', 'pausado', 'vendido', 'archivado')),
    constraint ck_inmuebles_uso check (uso is null or uso in ('residencial', 'comercial', 'mixto')),
    constraint ck_inmuebles_precio check (precio is null or precio >= 0),
    constraint ck_inmuebles_coordenadas check (
        (latitud is null and longitud is null)
        or (latitud between -90 and 90 and longitud between -180 and 180)
    )
);

-- 2. Fotos y videos -------------------------------------------------------------------------------------------------------
create table if not exists inmuebles_material (
    id           bigserial primary key,
    inmueble_id  bigint not null references inmuebles (id) on delete cascade,
    url          text not null,
    storage_path text not null unique,
    orden        integer not null default 0,
    creado_en    timestamptz not null default now(),
    creado_por   text
);
create index if not exists ix_inmuebles_material_inmueble on inmuebles_material (inmueble_id, orden);

-- 3. Anuncio de Meta -> propiedad ------------------------------------------------------------------------------------------
create table if not exists inmuebles_anuncios (
    id_anuncio   text primary key,
    inmueble_id  bigint not null references inmuebles (id) on delete cascade,
    nombre       text,
    creado_en    timestamptz not null default now()
);

-- 5. Números del negocio ---------------------------------------------------------------------------------------------------
create table if not exists numeros_whatsapp (
    phone_number_id  text primary key,                      -- el id que Meta pone en cada mensaje (metadata.phone_number_id)
    nombre           text not null,
    telefono_visible text,
    asistente        text not null default 'ventas',
    activo           boolean not null default true,
    creado_en        timestamptz not null default now(),
    actualizado_en   timestamptz not null default now(),
    constraint ck_numeros_whatsapp_asistente check (asistente in ('ventas', 'inmuebles'))
);

-- 6. Conversaciones: quién atiende, de qué propiedad y por qué número -------------------------------------------------------
alter table conversaciones add column if not exists asistente text not null default 'ventas';
alter table conversaciones add column if not exists inmueble_id bigint references inmuebles (id) on delete restrict;
alter table conversaciones add column if not exists numero_negocio text;
alter table conversaciones drop constraint if exists ck_conversaciones_asistente;
alter table conversaciones
    add constraint ck_conversaciones_asistente check (asistente in ('ventas', 'inmuebles'));
create index if not exists ix_conversaciones_asistente on conversaciones (asistente);

-- Clave única: (canal, cliente, número del negocio). El número principal se guarda como null: con coalesce, todas las
-- conversaciones que ya existen conservan exactamente la misma clave que antes.
-- El índice viejo (canal, id_externo) se quita en la 038, DESPUÉS de desplegar el código nuevo: el código anterior usa
-- `on conflict (canal, id_externo)` y fallaría si desapareciera mientras sigue corriendo.
create unique index if not exists uq_conversaciones_canal_id_externo_numero
    on conversaciones (canal, id_externo, (coalesce(numero_negocio, '')));

-- 4. Agenda de visitas -----------------------------------------------------------------------------------------------------
create table if not exists visitas (
    id                  bigserial primary key,
    inmueble_id         bigint not null references inmuebles (id) on delete restrict,
    conversacion_id     bigint references conversaciones (id) on delete restrict,
    contacto_id         bigint references contactos (id) on delete restrict,
    nombre_cliente      text,
    telefono            text,
    estado              text not null default 'solicitada',
    preferencia_cliente text,                               -- lo que pidió el cliente, en sus palabras («sábado en la tarde»)
    personas            integer,
    fecha_hora          timestamptz,                        -- la que confirmó el dueño
    encargado           text,                               -- quién la enseña
    notas               text,
    motivo_cancelacion  text,
    creada_por          text not null default 'asistente',
    creado_en           timestamptz not null default now(),
    actualizado_en      timestamptz not null default now(),
    confirmada_en       timestamptz,
    avisado_cliente_en  timestamptz,
    constraint ck_visitas_estado check (estado in ('solicitada', 'confirmada', 'realizada', 'no_asistio', 'cancelada')),
    constraint ck_visitas_creada_por check (creada_por in ('asistente', 'dueno')),
    constraint ck_visitas_personas check (personas is null or personas between 1 and 50),
    -- Una visita confirmada tiene día y hora: es lo que se le avisa al cliente.
    constraint ck_visitas_confirmada_con_fecha check (estado not in ('confirmada', 'realizada', 'no_asistio') or fecha_hora is not null)
);
create index if not exists ix_visitas_fecha on visitas (fecha_hora);
create index if not exists ix_visitas_estado on visitas (estado);
create index if not exists ix_visitas_conversacion on visitas (conversacion_id);
-- Una sola visita ABIERTA (pedida o confirmada) por conversación y propiedad: si el cliente cambia de idea, se actualiza.
create unique index if not exists uq_visitas_abierta_por_conversacion
    on visitas (conversacion_id, inmueble_id) where estado in ('solicitada', 'confirmada') and conversacion_id is not null;

-- Como en las demás tablas (031 a 035): seguridad por filas activa y sin políticas. Solo el backend (que entra con el rol del
-- servidor) las lee y escribe; la llave pública del navegador no ve nada.
alter table inmuebles enable row level security;
alter table inmuebles_material enable row level security;
alter table inmuebles_anuncios enable row level security;
alter table visitas enable row level security;
alter table numeros_whatsapp enable row level security;
