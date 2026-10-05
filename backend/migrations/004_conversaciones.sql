-- Fase 3 - Bot de WhatsApp (Victoria). Una fila por número de teléfono
-- que escribe -- el mismo cliente reutiliza esta fila en su próximo
-- mensaje, no se crea una nueva. Independiente de `pedidos` (Fase 1):
-- esa tabla es el contrato con Rocketfy, esta es el estado de la charla.

create table if not exists conversaciones (
    id                  bigserial primary key,
    telefono            text not null unique,
    origen              text not null default 'directo',
        -- fep            -> llegó desde anuncio Click-to-WhatsApp (ventana gratuita de 72h)
        -- web_formulario -> llenó el formulario en la landing page
        -- directo        -> escribió directamente al número sin anuncio
    fep_expira_en       timestamptz,
        -- solo si origen = 'fep'. now() + interval '72 hours' al detectarlo
    id_anuncio          text,
        -- source_id del objeto referral que manda Meta en el webhook
    ctwa_clid           text,
        -- Click-To-WhatsApp Click ID, para tracking de conversiones en Meta Ads
    estado              text not null default 'activa',
        -- activa | esperando_pago | escalada | cerrada | fria
    creada_en           timestamptz not null default now(),
    actualizada_en      timestamptz not null default now()
);

create index if not exists idx_conversaciones_telefono on conversaciones (telefono);
create index if not exists idx_conversaciones_estado on conversaciones (estado);
