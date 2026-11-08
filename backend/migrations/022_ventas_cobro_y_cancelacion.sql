-- ADR-012 (cierre de huecos): cobrar y cancelar una venta de un producto propio.
-- Solo AGREGA columnas nullable (nada de lo que ya existe cambia).
--
-- Dos preguntas distintas que antes no tenían respuesta:
--   «¿Ya me pagaron?»   -> ventas.cobrada_en / cobrada_por / nota_cobro. «Atendida» solo quiere decir que el
--                          dueño gestionó el pedido; el dinero puede llegar después (transferencia, entrega).
--   «¿Se cayó la venta?» -> ventas.estado = 'cancelada' (ya existía en el check) + quién, cuándo y por qué.
--                          Cancelar devuelve el stock que se descontó al cerrar la venta.
--
-- ventas_lineas.stock_descontado guarda cuántas unidades se descontaron DE VERDAD al cerrar esa línea. Así,
-- cancelar devuelve exactamente eso: si el dueño cambió después el control de stock del producto, no se
-- devuelven unidades que nunca se descontaron (ni se pierden las que sí).

alter table ventas
    add column if not exists cobrada_en         timestamptz,
    add column if not exists cobrada_por        text,
    add column if not exists nota_cobro         text,
    add column if not exists cancelada_en       timestamptz,
    add column if not exists cancelada_por      text,
    add column if not exists motivo_cancelacion text;

alter table ventas_lineas
    add column if not exists stock_descontado integer check (stock_descontado is null or stock_descontado >= 0);

-- Una venta cancelada no puede figurar como cobrada: si hay que devolver dinero, primero se deshace el cobro.
do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'ck_ventas_cancelada_no_cobrada') then
        alter table ventas
            add constraint ck_ventas_cancelada_no_cobrada check (not (estado = 'cancelada' and cobrada_en is not null));
    end if;
end
$$;

-- Para los reportes y para «lo que me falta cobrar».
create index if not exists idx_ventas_por_cobrar on ventas (cerrada_en desc) where cobrada_en is null and estado <> 'cancelada';
