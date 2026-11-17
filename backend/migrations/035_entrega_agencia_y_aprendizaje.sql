-- Entrega en agencia (versión 1) y «Aprendizaje de Victoria» (docs/PLAN_ENTREGA_EN_AGENCIA.md §0, entrada 0.0.140).
--
-- 1) Datos de envío más completos en el lead: si el cliente quiere retirar en una AGENCIA de Servientrega (Victoria anota lo
--    que dijo, tal cual, y el dueño define la agencia exacta en el panel) o recibir en su DOMICILIO; la REFERENCIA de la
--    dirección y las INDICACIONES para el repartidor, que ahora sí se mandan a Rocketfy (`address_2`, `carrier_observations`).
-- 2) `victoria_aprendizaje`: cada vez que Victoria se traba, no entiende, pasa la conversación a un asesor o algo falla, queda
--    una fila con el porqué y el contexto. El dueño la revisa en el panel y anota qué se hizo para mejorar a Victoria.
--
-- Solo AGREGA columnas y una tabla (idempotente): el código anterior las ignora.

alter table leads
    add column if not exists tipo_entrega          text,
        -- null = todavía no se eligió | 'domicilio' | 'agencia'
    add column if not exists agencia_indicada      text,
        -- lo que dijo el cliente sobre la agencia, TAL CUAL («una por el centro», «la de Urdesa»); no es una dirección validada
    add column if not exists agencia_definida_en   timestamptz,
        -- cuándo el dueño escribió la agencia exacta en «Datos de envío»; sin esto no se cierra una venta con retiro en agencia
    add column if not exists agencia_definida_por  text,
    add column if not exists referencia            text,
        -- referencia de la dirección («frente al parque», «casa esquinera verde») -> Rocketfy `address_2`
    add column if not exists indicaciones_entrega  text;
        -- indicaciones para el repartidor -> Rocketfy `carrier_observations` (p. ej. «RETIRO EN AGENCIA SERVIENTREGA …»)

alter table leads drop constraint if exists ck_leads_tipo_entrega;
alter table leads add constraint ck_leads_tipo_entrega check (tipo_entrega is null or tipo_entrega in ('domicilio', 'agencia'));

create table if not exists victoria_aprendizaje (
    id               bigserial primary key,
    creado_en        timestamptz not null default now(),
    conversacion_id  bigint references conversaciones (id),
    lead_id          bigint references leads (id),
    contacto_id      bigint references contactos (id),
    tipo             text not null,
        -- qué pasó (lista cerrada, ver el check): sirve para agrupar y medir
    origen           text not null,
        -- 'victoria' (ella lo decidió) | 'sistema' (una regla del código) | 'dueno' (el dueño tuvo que meterse)
    motivo           text not null,
        -- el porqué en palabras (de Victoria o del código)
    mensaje_cliente  text,
        -- lo último que escribió el cliente antes de que pasara (copia: los mensajes se pueden depurar)
    etapa            text,
        -- en qué paso de la venta estaba: producto | datos | entrega | pago | confirmacion | cierre | postventa
    producto_sku     text,
    contexto         jsonb not null default '{}'::jsonb,
        -- extracto de la conversación (últimos mensajes), herramienta y datos útiles para entender el caso
    estado           text not null default 'pendiente',
        -- 'pendiente' | 'revisado' | 'resuelto' (se mejoró algo) | 'descartado' (no había nada que mejorar)
    categoria        text,
        -- la que pone el dueño al revisar (texto libre corto: «falta en la ficha», «pregunta de envío»…)
    accion           text,
        -- qué se hizo: 'instrucciones' | 'ficha' | 'parametro' | 'sistema' | 'ninguna'
    nota             text,
    revisado_por     text,
    revisado_en      timestamptz,
    constraint ck_aprendizaje_tipo check (tipo in (
        'no_entendio', 'sin_respuesta', 'fuera_de_reglas', 'pidio_asesor', 'cliente_molesto', 'problema_pago',
        'problema_entrega', 'agencia_por_definir', 'gestion', 'cierre_frenado', 'error_proveedor', 'error_sistema',
        'dueno_intervino', 'otro'
    )),
    constraint ck_aprendizaje_origen check (origen in ('victoria', 'sistema', 'dueno')),
    constraint ck_aprendizaje_estado check (estado in ('pendiente', 'revisado', 'resuelto', 'descartado')),
    constraint ck_aprendizaje_accion check (accion is null or accion in ('instrucciones', 'ficha', 'parametro', 'sistema', 'ninguna'))
);

create index if not exists ix_aprendizaje_estado on victoria_aprendizaje (estado, creado_en desc);
create index if not exists ix_aprendizaje_tipo on victoria_aprendizaje (tipo, creado_en desc);
create index if not exists ix_aprendizaje_conversacion on victoria_aprendizaje (conversacion_id);

-- Mismo criterio que el resto de tablas del panel: RLS activo y sin políticas (solo el backend, con su conexión directa, la usa).
alter table victoria_aprendizaje enable row level security;
