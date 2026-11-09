-- Anuncios (Click-to-WhatsApp): saber de dónde viene cada cliente y con qué anuncio.
--
-- Hasta ahora, de un anuncio solo se guardaban `id_anuncio` y `ctwa_clid` EN LA CONVERSACIÓN y solo la
-- PRIMERA vez que ese teléfono escribía: un cliente que ya existía y volvía por otro anuncio se ignoraba, y se
-- perdían el título, el texto, el enlace y la imagen del anuncio (lo que Meta manda en el objeto `referral`).
--
-- Esta migración agrega SOLO objetos nuevos (idempotente, sin tocar datos existentes):
--   1. `conversacion_anuncios`: una fila por cada mensaje que llega desde un anuncio (el historial de «toques»),
--      con todos los campos del `referral` y el objeto completo tal cual llegó (por si Meta agrega campos).
--   2. `anuncios_productos.nombre`: un nombre propio para reconocer el anuncio al vincularlo (antes de que
--      llegue el primer cliente no hay título de Meta que mostrar).
--
-- `conversaciones.fep_expira_en` queda SIN USO: era «72 h desde el primer mensaje», una regla de Meta que ya no
-- es esa (la ventana gratuita se abre cuando NOSOTROS respondemos y dura hasta 7 días). Se calcula ahora a
-- partir de los mensajes (ver `src/routes/anuncios/ventana.py`). La columna no se borra: no se edita lo aplicado.

create table if not exists conversacion_anuncios (
    id                  bigserial primary key,
    conversacion_id     bigint not null references conversaciones (id) on delete cascade,
    mensaje_id          bigint references mensajes (id) on delete set null,
    wamid               text,
        -- id del mensaje de WhatsApp que traía el anuncio (evita registrar dos veces el mismo)
    id_anuncio          text,
        -- referral.source_id: el ID del anuncio en Meta
    tipo_origen         text,
        -- referral.source_type: «ad» (anuncio) o «post» (publicación)
    url_anuncio         text,
        -- referral.source_url: el enlace al anuncio o publicación
    titulo              text,
        -- referral.headline
    texto               text,
        -- referral.body (el texto principal del anuncio)
    tipo_media          text,
        -- referral.media_type: image | video
    imagen_url          text,
    video_url           text,
    miniatura_url       text,
    ctwa_clid           text,
        -- Click-To-WhatsApp Click ID: sirve para decirle a Meta qué clics terminaron en venta
    mensaje_bienvenida  text,
        -- referral.welcome_message.text (el saludo automático que configuró el anuncio)
    referral            jsonb not null,
        -- el objeto `referral` completo tal cual llegó
    creado_en           timestamptz not null default now()
);

create index if not exists idx_conv_anuncios_conversacion on conversacion_anuncios (conversacion_id, creado_en desc);
create index if not exists idx_conv_anuncios_anuncio on conversacion_anuncios (id_anuncio, creado_en desc);
create unique index if not exists uq_conv_anuncios_wamid on conversacion_anuncios (wamid) where wamid is not null;

alter table anuncios_productos
    add column if not exists nombre text,
    add column if not exists actualizado_en timestamptz not null default now();
