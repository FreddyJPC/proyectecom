-- Fase 3.2 - Registro persistente de cada tarea que el BotWorker debe
-- procesar. Antes de esta tabla, la cola vivía solo en memoria
-- (queue.Queue) -- un reinicio del proceso con tareas pendientes las
-- perdía en silencio. El campo "modo" separa dos caminos: uno
-- determinista (mensaje fijo, sin pasar por el LLM) y uno que sí invoca
-- a Victoria.

create table if not exists cola_mensajes (
    id                  bigserial primary key,
    conversacion_id     bigint not null references conversaciones (id) on delete cascade,
    mensaje_id          bigint references mensajes (id) on delete set null,
    modo                text not null,
        -- ia    -> invocar a VictoriaConversationService.procesar_turno()
        -- fijo  -> enviar texto_fijo tal cual, sin pasar por el LLM
    texto_fijo          text,
        -- Solo si modo = 'fijo'. NULL si modo = 'ia'.
    estado              text not null default 'pendiente',
        -- pendiente | procesando | completado | error
    intentos            integer not null default 0,
    error_detalle       text,
    creado_en           timestamptz not null default now(),
    procesado_en        timestamptz
);

create index if not exists cola_mensajes_estado_idx on cola_mensajes (estado, creado_en);
