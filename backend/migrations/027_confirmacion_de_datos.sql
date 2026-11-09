-- Confirmación de los datos de envío con el cliente, antes de cerrar la venta.
--
-- Para qué sirve: antes de cerrar un pedido, Victoria le muestra al cliente un resumen (nombre, dirección, ciudad, producto,
-- total, forma de pago…) y le pide que confirme que está correcto. Solo si responde que sí se puede cerrar la venta: así un
-- dato mal entendido («kito», un número de casa equivocado) se corrige ANTES de crear el pedido, no después.
--
--   datos_confirmacion_pedida_en : cuándo Victoria pidió la confirmación (mostró el resumen).
--   datos_confirmados_en         : cuándo el cliente confirmó. La herramienta `confirmar_datos_envio` solo lo marca si el
--                                  cliente escribió DESPUÉS de que se pidió; si cambia cualquier dato del pedido, ambas
--                                  columnas vuelven a NULL y hay que confirmar de nuevo.
--
-- Solo se agregan columnas nuevas y nulables; no se toca nada ya aplicado.

alter table leads
    add column if not exists datos_confirmacion_pedida_en timestamptz,
    add column if not exists datos_confirmados_en timestamptz;
