-- Fase 3.2 - Vincula el id_anuncio (objeto referral de Meta cuando el
-- cliente viene de un anuncio FEP) con el producto correspondiente de
-- productos_bot, para que VictoriaConversationService sepa de qué
-- producto hablar sin que el cliente tenga que decirlo.

create table if not exists anuncios_productos (
    id_anuncio      text primary key,
    producto_sku    text not null references productos_bot (sku),
    creado_en       timestamptz not null default now()
);
