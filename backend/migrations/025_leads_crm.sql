-- Leads (CRM), fase F1 (docs/PLAN_LEADS_CRM.md): temperatura, historial, «no contactar» en el contacto y atribución por lead.
--
-- Qué agrega (solo objetos y columnas nuevas; los leads existentes se rellenan por reglas, sin perder nada):
--   1. `leads.temperatura` (caliente | tibio | frío | perdido | ganado) con su motivo, quién la puso (IA, regla o dueño), cuándo
--      y, si la fijó el dueño, hasta cuándo no la pisa el enfriamiento automático. `perdido` y `ganado` son finales.
--   2. `leads.motivo_perdida` (catálogo corto, para saber POR QUÉ se pierde) y `leads.cerrado_en`.
--   3. Atribución POR LEAD (`origen`, `id_anuncio`, `ctwa_clid`): cada intención de compra recuerda con qué anuncio nació. Antes
--      la venta copiaba el origen de la CONVERSACIÓN, que una vez «anuncio» no volvía nunca a «directo».
--   4. `lead_historial`: cada cambio de temperatura (de → a, quién, motivo, cuándo).
--   5. `contactos.no_contactar` (+ motivo, cuándo, quién): del contacto, no del lead ni del canal; bloquea todo mensaje que
--      enviemos por iniciativa propia.
--   6. Un contacto puede tener VARIOS leads con el tiempo pero solo UNO ABIERTO a la vez (índice único parcial): «José, audífonos
--      en octubre» y «José, zapatos en noviembre» son dos leads de un mismo contacto.

alter table contactos
    add column if not exists no_contactar boolean not null default false,
    add column if not exists no_contactar_motivo text,
    add column if not exists no_contactar_en timestamptz,
    add column if not exists no_contactar_por text;
        -- no_contactar_por: ia | dueno

alter table leads
    add column if not exists temperatura text not null default 'tibio',
    add column if not exists temperatura_motivo text,
    add column if not exists temperatura_origen text not null default 'regla',
    add column if not exists temperatura_en timestamptz not null default now(),
    add column if not exists temperatura_fijada_hasta timestamptz,
    add column if not exists motivo_perdida text,
    add column if not exists cerrado_en timestamptz,
    add column if not exists origen text not null default 'directo',
    add column if not exists id_anuncio text,
    add column if not exists ctwa_clid text;

alter table leads drop constraint if exists ck_leads_temperatura;
alter table leads add constraint ck_leads_temperatura
    check (temperatura in ('caliente', 'tibio', 'frio', 'perdido', 'ganado'));
alter table leads drop constraint if exists ck_leads_temperatura_origen;
alter table leads add constraint ck_leads_temperatura_origen check (temperatura_origen in ('ia', 'regla', 'dueno'));
alter table leads drop constraint if exists ck_leads_motivo_perdida;
alter table leads add constraint ck_leads_motivo_perdida
    check (motivo_perdida is null or motivo_perdida in
           ('precio', 'sin_respuesta', 'compro_en_otro_lado', 'sin_cobertura', 'sin_stock', 'no_le_interesa', 'otro'));

create table if not exists lead_historial (
    id          bigserial primary key,
    lead_id     bigint not null references leads (id) on delete restrict,
    de          text,
    a           text not null,
    origen      text not null check (origen in ('ia', 'regla', 'dueno')),
    motivo      text,
    usuario     text,
    creado_en   timestamptz not null default now()
);

create index if not exists idx_lead_historial_lead on lead_historial (lead_id, creado_en desc, id desc);
alter table lead_historial enable row level security;

-- Relleno de los leads que ya existían: por reglas sobre hechos (la venta cerrada es «ganado», la cancelada «perdido»; el
-- resto «tibio»), con el origen y el anuncio que tenía su conversación. Se salta los que ya tienen historial (idempotente).
update leads l set
    temperatura = case when l.estado in ('despachado', 'por_gestionar') then 'ganado'
                       when l.estado = 'cancelado' then 'perdido' else 'tibio' end,
    temperatura_origen = 'regla',
    temperatura_motivo = case when l.estado in ('despachado', 'por_gestionar') then 'Venta cerrada'
                              when l.estado = 'cancelado' then 'Venta cancelada'
                              else 'Lead anterior al seguimiento de leads' end,
    temperatura_en = l.actualizado_en,
    motivo_perdida = case when l.estado = 'cancelado' then 'otro' else null end,
    cerrado_en = case when l.estado in ('despachado', 'por_gestionar', 'cancelado') then l.actualizado_en else null end,
    origen = c.origen,
    id_anuncio = c.id_anuncio,
    ctwa_clid = c.ctwa_clid
from conversaciones c
where c.id = l.conversacion_id
  and not exists (select 1 from lead_historial h where h.lead_id = l.id);

insert into lead_historial (lead_id, de, a, origen, motivo, creado_en)
select l.id, null, l.temperatura, 'regla', l.temperatura_motivo, l.temperatura_en
from leads l
where not exists (select 1 from lead_historial h where h.lead_id = l.id);

-- Un solo lead abierto por contacto. Los cerrados (perdido/ganado) no cuentan: se acumulan con el tiempo.
create unique index if not exists uq_leads_un_abierto_por_contacto
    on leads (contacto_id) where temperatura in ('caliente', 'tibio', 'frio');

create index if not exists idx_leads_temperatura on leads (temperatura, actualizado_en desc);
create index if not exists idx_leads_origen on leads (origen, id_anuncio);
