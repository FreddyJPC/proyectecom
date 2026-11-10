-- Recordatorios al dueño cuando un chat que Victoria le pasó sigue sin atender (pendiente #76, punto 4).
--
-- Para qué sirve: hoy, al pasar un chat a una persona, el sistema avisa UNA vez por Telegram. Si ese aviso se pierde, el cliente
-- espera sin que nadie lo sepa. Un trabajo automático vuelve a avisar mientras el chat siga sin abrir (ver jobs/recordatorios).
--
--   pendiente_desde        : cuándo quedó esperando al dueño (al escalar o pasar a «en gestión»). NULL = no hay nada pendiente
--                            (las conversaciones que ya estaban escaladas antes de esta migración no generan recordatorios).
--   recordatorios_enviados : cuántos recordatorios se han mandado desde entonces (el aviso original no cuenta).
--   ultimo_recordatorio_en : cuándo salió el último.
--
-- «Atendido» = el dueño abrió el chat (`vista_en`, que ya existía) o el chat dejó de estar en sus manos. Solo se agregan columnas
-- nuevas y nulables; no se toca nada ya aplicado.

alter table conversaciones
    add column if not exists pendiente_desde timestamptz,
    add column if not exists recordatorios_enviados integer not null default 0,
    add column if not exists ultimo_recordatorio_en timestamptz;
