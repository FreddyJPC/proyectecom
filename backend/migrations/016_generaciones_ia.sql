-- Fase D del plan de gestión de productos (docs/PLAN_GESTION_PRODUCTOS.md):
-- "Redactar con IA". Solo AGREGA una tabla y una columna; el bot de Victoria no
-- lee nada de esto, así que sigue funcionando igual.

-- Un registro por cada vez que se pidió un borrador a la IA. Sirve para dos
-- cosas: (1) el TOPE diario (cada llamada a la IA cuesta plata) y (2) saber
-- quién usó la IA, con qué modelo y cuándo. Sin FK a productos_bot a propósito:
-- el registro vale aunque el producto se archive o se borre después.
create table if not exists generaciones_ia (
    id          bigserial primary key,
    sku         text,
    usuario     text,
    tipo        text not null default 'contenido',
    modelo      text,
    -- Qué campos se pidieron (p. ej. 'nombre,descripcion'); un solo campo = "Regenerar".
    campos      text,
    -- ok       = la IA devolvió un borrador válido.
    -- invalido = la IA contestó pero no con el formato pedido (igual costó: cuenta para el tope).
    -- fallo    = el proveedor no respondió (red, clave, límite): no costó, NO cuenta para el tope.
    resultado   text not null check (resultado in ('ok', 'invalido', 'fallo')),
    creado_en   timestamptz not null default now()
);

create index if not exists idx_generaciones_ia_fecha on generaciones_ia (creado_en desc);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS
-- activado la API pública de Supabase (anon/authenticated) no puede ver ni
-- tocar esta tabla. Mismo criterio que `latido`, `productos_bot_historial` y
-- `ajustes_negocio`.
alter table generaciones_ia enable row level security;

-- Tope de borradores por día (se cuenta por día de Ecuador). La propuesta del
-- plan era 20; el dueño lo ajusta desde el cuadro de ajustes.
alter table ajustes_negocio
    add column if not exists tope_redacciones_dia integer not null default 20
        check (tope_redacciones_dia between 1 and 200);
