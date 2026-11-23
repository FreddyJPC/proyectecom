-- Módulo «Inmuebles» (ADR-019), segunda parte de la 037. Se aplica DESPUÉS de desplegar el código que usa la clave nueva
-- `(canal, id_externo, coalesce(numero_negocio, ''))`.
--
-- Quita el índice único viejo (canal, id_externo): con él, una persona no podría tener una conversación con cada número del
-- negocio (p. ej. el de Victoria y el de una propiedad). Mientras exista no rompe nada con un solo número; por eso se quita al
-- final, cuando el código anterior (que lo necesitaba) ya no corre.
drop index if exists uq_conversaciones_canal_id_externo;
