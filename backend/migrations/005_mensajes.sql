-- Fase 3 - Bot de WhatsApp (Victoria). Cada turno de la conversación:
-- mensajes del cliente, respuestas del bot, e intervenciones manuales del
-- dueño cuando toma la conversación (rol='humano').

create table if not exists mensajes (
    id                  bigserial primary key,
    conversacion_id     bigint not null references conversaciones (id) on delete cascade,
    rol                 text not null,
        -- cliente | bot | humano
    contenido           text not null,
    tipo                text not null default 'texto',
        -- texto | imagen | audio
    wamid               text,
        -- ID de mensaje asignado por WhatsApp (formato wamid.xxx). Se usa
        -- para idempotencia: el mismo wamid no se procesa dos veces aunque
        -- Meta reenvíe el webhook duplicado. Los mensajes que manda el bot
        -- no siempre tienen wamid (no siempre se guarda la confirmación).
    creado_en           timestamptz not null default now()
);

-- Idempotencia: un mismo wamid no puede repetirse. Postgres ya permite
-- múltiples NULL en un índice único (NULL nunca choca con NULL), así que
-- el filtro WHERE wamid IS NOT NULL no es necesario por corrección -- es
-- una optimización: los mensajes del bot no siempre tienen wamid, y así
-- el índice no los indexa de balde.
create unique index if not exists mensajes_wamid_unique
    on mensajes (wamid) where wamid is not null;

create index if not exists idx_mensajes_conversacion_fecha
    on mensajes (conversacion_id, creado_en);
