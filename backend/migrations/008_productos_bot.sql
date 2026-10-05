-- Fase 3.2 - Base de conocimiento de ventas de Victoria. Se carga
-- manualmente por ahora (sin panel de administración todavía). NO
-- confundir con el catálogo de Rocketfy (routes/productos): ese es para
-- verificar SKU/stock real con fines logísticos, este es contenido de
-- ventas que el bot usa para conversar.

create table if not exists productos_bot (
    id                      bigserial primary key,
    sku                     text not null unique,
    nombre                  text not null,
    descripcion             text not null,
    precio                  numeric(12,2) not null,
    variantes               text,
    tiempo_entrega          text not null,
    metodos_pago_aceptados  text not null default 'contraentrega, transferencia',
    preguntas_frecuentes    text,
    temas_no_responder      text,
    activo                  boolean not null default true,
    creado_en               timestamptz not null default now(),
    actualizado_en          timestamptz not null default now()
);
