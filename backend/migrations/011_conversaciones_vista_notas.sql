-- Módulo de Conversaciones (dashboard) - columnas e índices nuevos.

ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS vista_en timestamptz;
    -- NULL mientras nadie ha abierto el detalle de una escalada nueva.
    -- Se limpia a NULL cada vez que la conversación vuelve a escalar
    -- (ver tools.py::_handle_escalar_a_humano), así una segunda escalada
    -- se vuelve a marcar como "sin revisar" aunque una anterior ya se
    -- hubiera visto.

ALTER TABLE conversaciones ADD COLUMN IF NOT EXISTS notas_internas text;
    -- Notas privadas del dueño del negocio. NUNCA se envían al cliente,
    -- ni entran al contexto de Victoria. Son solo para uso humano interno.

CREATE INDEX IF NOT EXISTS conversaciones_estado_actualizada_idx ON conversaciones(estado, actualizada_en);
CREATE INDEX IF NOT EXISTS leads_nombre_cliente_idx ON leads(lower(nombre_cliente));
