-- Seguimiento automático de leads (docs/PLAN_LEADS_CRM.md §6, pendiente #67): el registro de a quién se le escribió por
-- iniciativa propia, qué se le escribió y cuándo.
--
-- Para qué sirve esta tabla:
--   1. NO REPETIR: el sistema le escribe a un cliente como máximo UN empujón (texto libre dentro de las 24 h) y UNA plantilla
--      (fuera de las 24 h) en toda su vida. El índice único parcial lo garantiza aunque dos procesos corran a la vez.
--   2. EL TOPE DIARIO: contar cuántos seguimientos salieron hoy.
--   3. LA LÍNEA DE TIEMPO del lead: el dueño ve cuándo se le escribió al cliente y si funcionó.
--
-- El envío se hace en dos tiempos: primero se RESERVA la fila (estado `reservado`: ya cuenta para el índice único) y después se
-- envía; el resultado la deja en `enviado` o `fallido`. Si el proceso se cae entre una cosa y otra, la fila queda `reservado`
-- y ese cliente NO recibe un segundo mensaje: ante la duda, se prefiere no escribir de más. Un `fallido` no cuenta para el
-- índice único (se puede reintentar; el servicio limita cuántas veces y cada cuánto).
--
-- Las claves son `restrict`, como el resto del historial del contacto: no se puede borrar un lead, una conversación o un
-- contacto que tiene seguimientos. Solo se agregan objetos nuevos; no se toca nada ya aplicado.

create table if not exists seguimientos (
    id               bigserial primary key,
    lead_id          bigint not null references leads (id) on delete restrict,
    contacto_id      bigint not null references contactos (id) on delete restrict,
    conversacion_id  bigint not null references conversaciones (id) on delete restrict,
    canal            text not null,
    tipo             text not null check (tipo in ('empujon', 'plantilla')),
        -- empujon: texto libre (solo dentro de las 24 h); plantilla: mensaje aprobado por Meta (fuera de las 24 h)
    estado           text not null default 'reservado' check (estado in ('reservado', 'enviado', 'fallido')),
    contenido        text,
        -- lo que el cliente recibió (en la plantilla, su texto aprobado)
    plantilla        text,
        -- nombre de la plantilla de Meta (solo en tipo plantilla)
    wamid            text,
        -- identificador del mensaje en WhatsApp
    error            text,
    creado_en        timestamptz not null default now(),
    enviado_en       timestamptz
);

-- Un empujón y una plantilla por contacto en toda su vida (los fallidos no cuentan: se pueden reintentar).
create unique index if not exists uq_seguimientos_uno_por_tipo
    on seguimientos (contacto_id, tipo) where estado in ('reservado', 'enviado');

create index if not exists idx_seguimientos_lead on seguimientos (lead_id, creado_en desc, id desc);
create index if not exists idx_seguimientos_creado on seguimientos (creado_en desc);

alter table seguimientos enable row level security;
