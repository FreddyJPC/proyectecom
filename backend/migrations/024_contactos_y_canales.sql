-- Cimientos multicanal (ADR-014): un CONTACTO único y permanente, y una CONVERSACIÓN por cada canal por el que escribe.
--
-- Hasta ahora la conversación era el contacto: se identificaba por el teléfono (WhatsApp) y nada más. El negocio quiere
-- vender también por Instagram y Messenger, y ahí no hay teléfono: el cliente es un identificador de la plataforma.
-- Este es el modelo estándar de un CRM (contacto 1 a N conversaciones/oportunidades):
--
--   contactos (la persona, permanente)
--     ├── conversaciones (una por canal: whatsapp | instagram | messenger; única por canal + id_externo)
--     ├── leads (cada intención de compra)
--     └── ventas (lo vendido; sobrevive a cualquier depuración de conversaciones)
--
-- Qué cambia:
--   1. `contactos`: nombre y teléfono conocidos de la persona. El teléfono es único cuando existe (así un mismo cliente
--      que escribe dos veces por WhatsApp nunca se duplica) y puede faltar (un cliente de Instagram aún no lo dio).
--   2. `conversaciones`: nuevas columnas `contacto_id`, `canal`, `id_externo` (el teléfono en WhatsApp; el identificador
--      de Meta en Instagram/Messenger) y `nombre_perfil`. Se eliminan `telefono` (ahora vive en el contacto) y
--      `fep_expira_en` (sin uso desde la migración 023).
--   3. Dos conceptos que se confundían, separados: `origen` = CÓMO llegó el cliente (anuncio | directo | …) y `canal`
--      = POR DÓNDE habla (whatsapp | instagram | messenger). `ventas.canal` guardaba el origen: pasa a `ventas.origen`
--      y `ventas.canal` es ahora el canal de mensajería. El valor `fep` (jerga de WhatsApp) pasa a `anuncio`, que vale
--      también para anuncios de Instagram y Messenger.
--   4. Protección del historial: borrar una conversación ya NO arrastra sus leads, sus llegadas por anuncio ni sus
--      solicitudes de gestión (antes `on delete cascade`): la base se niega. Solo `mensajes` y `cola_mensajes` siguen en
--      cascada, porque son lo único que se podrá depurar con el tiempo.
--
-- Los datos existentes se migran (cada conversación → un contacto y un canal 'whatsapp'); no se borra nada. Idempotente.

-- ---------------------------------------------------------------------------
-- 1. Contactos
-- ---------------------------------------------------------------------------
create table if not exists contactos (
    id              bigserial primary key,
    nombre          text,
        -- el nombre de la persona: el del perfil del canal o el último que dio al comprar
    telefono        text,
        -- teléfono conocido (en WhatsApp es el número desde el que escribe); único cuando existe
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now()
);

create unique index if not exists uq_contactos_telefono on contactos (telefono) where telefono is not null;

-- Como el resto de las tablas: seguridad por filas activada y sin políticas (solo el servidor accede, con su propio rol).
alter table contactos enable row level security;

-- ---------------------------------------------------------------------------
-- 2. Columnas nuevas (todavía sin obligar; se obliga tras migrar los datos)
-- ---------------------------------------------------------------------------
alter table conversaciones
    add column if not exists contacto_id bigint references contactos (id) on delete restrict,
    add column if not exists canal text not null default 'whatsapp',
    add column if not exists id_externo text,
    add column if not exists nombre_perfil text;

alter table leads
    add column if not exists contacto_id bigint references contactos (id) on delete restrict;

-- `ventas.canal` guardaba el ORIGEN ('fep' / 'directo'): se renombra y `canal` pasa a ser el canal de mensajería.
do $$
begin
    if exists (select 1 from information_schema.columns
               where table_schema = current_schema() and table_name = 'ventas' and column_name = 'canal')
       and not exists (select 1 from information_schema.columns
                       where table_schema = current_schema() and table_name = 'ventas' and column_name = 'origen') then
        alter table ventas rename column canal to origen;
    end if;
end $$;

alter table ventas
    add column if not exists canal text not null default 'whatsapp',
    add column if not exists contacto_id bigint references contactos (id) on delete restrict;

-- ---------------------------------------------------------------------------
-- 3. Migrar los datos existentes
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (select 1 from information_schema.columns
               where table_schema = current_schema() and table_name = 'conversaciones' and column_name = 'telefono') then
        -- Un contacto por cada teléfono que ya escribió.
        insert into contactos (telefono, creado_en)
        select c.telefono, min(c.creada_en)
        from conversaciones c
        where c.contacto_id is null and c.telefono is not null
        group by c.telefono
        on conflict (telefono) where telefono is not null do nothing;

        update conversaciones c
        set contacto_id = ct.id, id_externo = c.telefono, canal = 'whatsapp'
        from contactos ct
        where c.contacto_id is null and ct.telefono = c.telefono;
    end if;
end $$;

-- El nombre del contacto: el último que se le conoció a algún lead suyo.
update contactos ct
set nombre = x.nombre_cliente
from (
    select distinct on (c.contacto_id) c.contacto_id, l.nombre_cliente
    from leads l join conversaciones c on c.id = l.conversacion_id
    where l.nombre_cliente is not null and btrim(l.nombre_cliente) <> ''
    order by c.contacto_id, l.actualizado_en desc
) x
where ct.id = x.contacto_id and ct.nombre is null;

update leads l
set contacto_id = c.contacto_id
from conversaciones c
where c.id = l.conversacion_id and l.contacto_id is null;

update ventas v
set contacto_id = c.contacto_id
from conversaciones c
where c.id = v.conversacion_id and v.contacto_id is null;

-- Una venta cuya conversación ya no existe se liga al contacto de su teléfono (se crea si hace falta).
insert into contactos (telefono, nombre)
select distinct on (v.telefono) v.telefono, v.cliente_nombre
from ventas v
where v.contacto_id is null and v.telefono is not null
order by v.telefono, v.cerrada_en desc
on conflict (telefono) where telefono is not null do nothing;

update ventas v
set contacto_id = ct.id
from contactos ct
where v.contacto_id is null and ct.telefono = v.telefono;

-- 'fep' era jerga de WhatsApp; 'anuncio' sirve para cualquier canal.
update conversaciones set origen = 'anuncio' where origen = 'fep';
update ventas set origen = 'anuncio' where origen = 'fep';

-- ---------------------------------------------------------------------------
-- 4. Reglas e índices
-- ---------------------------------------------------------------------------
alter table conversaciones alter column contacto_id set not null;
alter table conversaciones alter column id_externo set not null;
alter table leads alter column contacto_id set not null;

-- Toda venta nueva trae su contacto; solo se exige si los datos antiguos quedaron completos.
do $$
begin
    if not exists (select 1 from ventas where contacto_id is null) then
        alter table ventas alter column contacto_id set not null;
    end if;
end $$;

alter table conversaciones drop constraint if exists ck_conversaciones_canal;
alter table conversaciones
    add constraint ck_conversaciones_canal check (canal in ('whatsapp', 'instagram', 'messenger'));
alter table ventas drop constraint if exists ck_ventas_canal;
alter table ventas
    add constraint ck_ventas_canal check (canal in ('whatsapp', 'instagram', 'messenger'));

create unique index if not exists uq_conversaciones_canal_id_externo on conversaciones (canal, id_externo);
create index if not exists idx_conversaciones_contacto on conversaciones (contacto_id);
create index if not exists idx_leads_contacto on leads (contacto_id, creado_en desc);
create index if not exists idx_ventas_contacto on ventas (contacto_id, cerrada_en desc);

-- ---------------------------------------------------------------------------
-- 5. Lo que ya no se usa
-- ---------------------------------------------------------------------------
alter table conversaciones drop constraint if exists conversaciones_telefono_key;
drop index if exists idx_conversaciones_telefono;
alter table conversaciones drop column if exists telefono;
alter table conversaciones drop column if exists fep_expira_en;

-- ---------------------------------------------------------------------------
-- 6. Proteger el historial: no se puede borrar una conversación que tiene leads, anuncios o solicitudes
-- ---------------------------------------------------------------------------
alter table leads drop constraint if exists leads_conversacion_id_fkey;
alter table leads
    add constraint leads_conversacion_id_fkey foreign key (conversacion_id) references conversaciones (id) on delete restrict;

alter table conversacion_anuncios drop constraint if exists conversacion_anuncios_conversacion_id_fkey;
alter table conversacion_anuncios
    add constraint conversacion_anuncios_conversacion_id_fkey
    foreign key (conversacion_id) references conversaciones (id) on delete restrict;

alter table solicitudes_gestion drop constraint if exists solicitudes_gestion_conversacion_id_fkey;
alter table solicitudes_gestion
    add constraint solicitudes_gestion_conversacion_id_fkey
    foreign key (conversacion_id) references conversaciones (id) on delete restrict;
