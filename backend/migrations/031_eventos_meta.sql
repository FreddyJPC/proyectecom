-- Bandeja de salida de eventos para Meta (ADR-016, docs/PLAN_META_ADS.md, pendiente #68): el registro de cada venta que se le
-- avisó (o se le va a avisar) a Meta como compra, para que optimice los anuncios hacia quien compra.
--
-- Para qué sirve esta tabla:
--   1. NO DUPLICAR: Meta NO deduplica los eventos de mensajería. La clave única (tipo, venta) garantiza que una venta se
--      avise como máximo una vez, aunque dos procesos corran a la vez.
--   2. DESACOPLAR: la venta nunca depende de Meta. El trabajo automático detecta las ventas confirmadas y las envía aparte;
--      si Meta falla, la venta ya está guardada y el evento queda para reintentar.
--   3. VER LO QUE PASA: cuántos eventos se enviaron, cuáles fallaron y cuáles se descartaron (y por qué: p. ej. una venta de
--      anuncio sin identificador de clic).
--
-- Estados: pendiente (por enviar o por reintentar a partir de `proximo_intento_en`) · enviando (reservado antes de llamar a
-- Meta) · enviado · fallido (se agotaron los intentos) · dudoso (no se sabe si Meta lo recibió: timeout o error del servidor
-- de Meta; NO se reintenta a ciegas porque podría duplicarse) · descartado (no corresponde enviarlo, con su motivo).
--
-- Guarda una copia del `ctwa_clid` y del anuncio (no una clave a leads) y la clave a ventas se borra en cascada: es una
-- bitácora de envíos, no historial del cliente. Solo se agregan objetos nuevos; no se toca nada ya aplicado.

create table if not exists eventos_meta (
    id                  bigserial primary key,
    tipo                text not null default 'Purchase' check (tipo in ('Purchase')),
    venta_id            bigint not null references ventas (id) on delete cascade,
    id_anuncio          text,
    ctwa_clid           text,
        -- el identificador del clic en el anuncio (lo trae el cliente al escribir); sin él no se puede avisar a Meta
    valor               numeric(12, 2) not null,
    moneda              text not null default 'USD',
    ocurrido_en         timestamptz not null,
        -- cuándo se confirmó la venta: es la hora del evento que Meta recibe
    estado              text not null default 'pendiente'
                        check (estado in ('pendiente', 'enviando', 'enviado', 'fallido', 'dudoso', 'descartado')),
    motivo              text,
    intentos            integer not null default 0,
    proximo_intento_en  timestamptz,
    respuesta           text,
        -- respuesta de Meta, recortada (nunca el token)
    creado_en           timestamptz not null default now(),
    actualizado_en      timestamptz not null default now(),
    enviado_en          timestamptz
);

-- Un evento de cada tipo por venta.
create unique index if not exists uq_eventos_meta_tipo_venta on eventos_meta (tipo, venta_id);
create index if not exists idx_eventos_meta_estado on eventos_meta (estado, proximo_intento_en);
create index if not exists idx_eventos_meta_anuncio on eventos_meta (id_anuncio, creado_en desc);

alter table eventos_meta enable row level security;
