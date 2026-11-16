-- Anuncios de Meta: copia de lo que hay en la cuenta publicitaria, gasto diario, alertas y acciones (ADR-017, plan v2.0 §6).
--
-- El servidor LEE la cuenta publicitaria con la API de Marketing (una vez por hora) y guarda una copia aquí: así el panel muestra
-- nombre, estado, miniatura y gasto de cada anuncio, y se puede vincular un anuncio a su oferta ANTES de que llegue el primer
-- cliente. Las alertas avisan (Telegram) una sola vez por regla, objeto y día. La única acción automática posible es PAUSAR un
-- anuncio por un hecho (sin stock, oferta terminada), con su interruptor apagado de fábrica; nunca se reactiva ni se cambia un
-- presupuesto. Solo AGREGA objetos (idempotente).

create table if not exists meta_anuncios (
    id_anuncio          text primary key,
    nombre              text,
    estado              text,
        -- status que puso el anunciante: ACTIVE | PAUSED | ARCHIVED | DELETED
    estado_efectivo     text,
        -- effective_status de Meta: ACTIVE, PAUSED, CAMPAIGN_PAUSED, ADSET_PAUSED, DISAPPROVED, WITH_ISSUES, PENDING_REVIEW...
    id_conjunto         text,
    nombre_conjunto     text,
    presupuesto_diario  numeric(12, 2),
        -- del conjunto de anuncios, en la moneda de la cuenta (Meta lo da en centavos; aquí ya en dólares)
    id_campana          text,
    nombre_campana      text,
    titulo              text,
    texto               text,
    miniatura_url       text,
    leido_en            timestamptz not null default now()
);

create table if not exists meta_metricas_diarias (
    id_anuncio          text not null,
    fecha               date not null,
        -- día en la zona horaria de la cuenta publicitaria (America/Guayaquil)
    gasto               numeric(12, 2) not null default 0,
    impresiones         integer not null default 0,
    clics               integer not null default 0,
    conversaciones      integer not null default 0,
        -- conversaciones iniciadas según Meta (messaging_conversation_started_7d)
    leido_en            timestamptz not null default now(),
    primary key (id_anuncio, fecha)
);
create index if not exists idx_meta_metricas_fecha on meta_metricas_diarias (fecha);

create table if not exists meta_alertas (
    id                  bigserial primary key,
    regla               text not null,
        -- R1 producto agotado/pausado con anuncio activo, R2 oferta terminada, R3 stock bajo, R4 gasto sin ventas,
        -- R5 costo por conversación alto, R6 costo por venta mayor que la ganancia, R7 anuncio sin vincular,
        -- R8 anuncio rechazado o con problemas, R9 regateo frecuente, resumen (resumen diario)
    objeto              text not null,
        -- a qué se refiere (id del anuncio, SKU, oferta...): con la regla y el día evita repetir el aviso
    fecha               date not null default current_date,
    id_anuncio          text,
    mensaje             text not null,
    creada_en           timestamptz not null default now(),
    unique (regla, objeto, fecha)
);
create index if not exists idx_meta_alertas_creada on meta_alertas (creada_en desc);

create table if not exists meta_acciones (
    id                  bigserial primary key,
    id_anuncio          text not null,
    accion              text not null check (accion in ('pausar')),
    regla               text,
        -- la regla que la pidió (R1, R2) o «manual» si la pidió el dueño desde el panel
    motivo              text not null,
    resultado           text not null check (resultado in ('hecho', 'fallido', 'dudoso')),
    detalle             text,
    creada_por          text,
    creada_en           timestamptz not null default now()
);
create index if not exists idx_meta_acciones_creada on meta_acciones (creada_en desc);

-- La cuenta publicitaria que se lee (no es un secreto: es un número que se ve en el Administrador de anuncios).
alter table ajustes_negocio add column if not exists meta_cuenta_publicitaria text;

alter table meta_anuncios enable row level security;
alter table meta_metricas_diarias enable row level security;
alter table meta_alertas enable row level security;
alter table meta_acciones enable row level security;
