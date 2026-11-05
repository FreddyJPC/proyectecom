-- Fase C del plan de gestión de productos (docs/PLAN_GESTION_PRODUCTOS.md):
-- la calculadora de precio. Solo AGREGA una tabla y una columna; el bot de
-- Victoria no lee nada de esto, así que sigue funcionando igual.

-- Los números del negocio con los que la calculadora recomienda precios. Es UNA
-- sola fila (id = 1, impuesto por el CHECK): son ajustes del dueño, no una lista.
--
-- Los porcentajes se guardan como porcentaje (25.00 = 25 %), no como fracción,
-- para que lo que se ve en la pantalla y lo que está aquí sea lo mismo.
-- "Margen" = ganancia / precio de venta (no recargo sobre el costo).
--
-- La fila nace con valores de PARTIDA (los de la propuesta del plan) y
-- `confirmado_en` vacío: mientras el dueño no los guarde una vez, la app avisa
-- que son de partida y NO los usa para bloquear publicaciones.
create table if not exists ajustes_negocio (
    id                    smallint primary key default 1 check (id = 1),
    margen_minimo_pct     numeric(5, 2)  not null default 25.00
                              check (margen_minimo_pct >= 0 and margen_minimo_pct < 100),
    margen_objetivo_pct   numeric(5, 2)  not null default 35.00
                              check (margen_objetivo_pct >= 0 and margen_objetivo_pct < 100),
    envio_estimado        numeric(12, 2) not null default 5.00
                              check (envio_estimado >= 0),
    otros_costos_fijos    numeric(12, 2) not null default 0.00
                              check (otros_costos_fijos >= 0),
    otros_costos_pct      numeric(5, 2)  not null default 0.00
                              check (otros_costos_pct >= 0 and otros_costos_pct < 100),
    redondeo              text           not null default 'terminado_99'
                              check (redondeo in ('ninguno', 'terminado_99')),
    confirmado_en         timestamptz,
    actualizado_por       text,
    actualizado_en        timestamptz    not null default now(),
    -- El objetivo no puede ser menor que el mínimo, y margen + otros costos
    -- porcentuales no pueden llegar al 100 % (no habría precio que alcance).
    constraint ajustes_negocio_objetivo_no_menor_que_minimo
        check (margen_objetivo_pct >= margen_minimo_pct),
    constraint ajustes_negocio_porcentajes_alcanzables
        check (margen_objetivo_pct + otros_costos_pct < 100)
);

insert into ajustes_negocio (id) values (1) on conflict (id) do nothing;

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS
-- activado la API pública de Supabase (anon/authenticated) no puede ver ni
-- tocar esta tabla. Mismo criterio que `latido` y `productos_bot_historial`.
alter table ajustes_negocio enable row level security;

-- Precio de la competencia que el dueño mira y anota a mano (la app NO lo
-- inventa ni lo busca). Solo sirve para comparar; Victoria no lo lee.
alter table productos_bot add column if not exists precio_competencia numeric(12, 2);
