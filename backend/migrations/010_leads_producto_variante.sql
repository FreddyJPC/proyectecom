-- Fase 3.2 (ajuste posterior) - variante/color elegido por el cliente,
-- si el producto tiene (ver productos_bot.variantes). Nunca es un dato
-- requerido para cerrar_venta -- puramente informativo, se agrega al
-- nombre de la línea que se manda a Rocketfy cuando está presente
-- (CrearPedidoInputDTO.lineas no tiene campo propio para variante).

alter table leads add column if not exists producto_variante text;
