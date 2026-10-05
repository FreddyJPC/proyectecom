# 04 — Base de Datos

## 1. Tecnología

**PostgreSQL**, alojado en **Supabase** (el mismo proyecto de Supabase se
usa para la base de datos Y para la autenticación del dashboard —
Supabase Auth). Acceso desde el backend vía **psycopg2** con SQL crudo —
no hay ORM (SQLAlchemy, etc.) en este proyecto.

Conexión vía el **Connection Pooler de Supabase (Supavisor)**, no la
conexión directa — el host de conexión directa solo resuelve por IPv6 y
el entorno de desarrollo actual no tiene salida IPv6. La estructura de la
connection string (sin credenciales reales):

```
postgresql://<usuario>.<project_ref>:<password>@aws-0-<región>.pooler.supabase.com:5432/postgres
```

Ver `05_variables_entorno.md` para dónde vive esto (`SUPABASE_DB_URL`).

## 2. Filosofía de la base de datos (importante para el bot)

Está diseñada bajo el principio de **"persistencia mínima"** (ADR-002 en
`PROGRESS.md`): Rocketfy sigue siendo la fuente de verdad del estado real
de un pedido (dónde está el paquete, si se entregó, etc.). Nuestras
tablas existen solo para:
1. Garantizar idempotencia (no duplicar pedidos si hay un timeout).
2. Auditoría (guardar cada evento crudo que llega).
3. Coordinar jobs en background entre instancias.

**El bot de WhatsApp necesita su propio modelo de datos nuevo** —
conversaciones, leads, estado conversacional, captura de pago — que
**no existe todavía en absoluto**. Ver sección 4 más abajo, es la parte
más importante de este documento.

## 3. Esquema actual — todas las tablas que existen hoy

### `pedidos`
Mapea nuestro `id_local` (el ID que nosotros asignamos) con el
`id_rocketfy` que asigna el proveedor, y guarda el estado local.

```sql
create table pedidos (
    id_local            bigint primary key,      -- lo generamos nosotros
    id_rocketfy         bigint unique,            -- lo asigna Rocketfy al crear
    estado_local        text not null default 'pendiente_creacion',
        -- pendiente_creacion | creado | confirmado | rechazado | incompleto | error
    status_id_rocketfy  integer,                  -- último status_id conocido (cache)
    payload_creacion    jsonb not null,            -- snapshot completo de los datos con los que se creó
    mensaje_error       text,
    creado_en           timestamptz not null default now(),
    confirmado_en       timestamptz,
    actualizado_en      timestamptz not null default now()
);
```

### `webhook_events`
Auditoría cruda de cada aviso recibido de Rocketfy (retención sugerida
≥90 días).

```sql
create table webhook_events (
    id                 bigserial primary key,
    id_rocketfy        bigint not null,
    status_id          integer not null,
    payload            jsonb not null,             -- el JSON completo tal cual llegó
    recibido_en        timestamptz not null default now(),
    procesado          boolean not null default false,
    procesado_en       timestamptz,
    event_date         timestamptz,                -- fecha que reporta Rocketfy del evento
    shopify_order_id   bigint                       -- = nuestro id_local
);
-- índice único de idempotencia: (id_rocketfy, status_id, event_date)
```

### `job_locks`
Lock distribuido genérico para que los jobs en background no corran en
paralelo si hay más de una instancia del backend.

```sql
create table job_locks (
    job_name    text primary key,
    locked_at   timestamptz not null default now(),
    instancia   text
);
```

### `skus_monitoreados`
Qué productos vigila el job de stock/precio.

```sql
create table skus_monitoreados (
    sku                     text primary key,
    umbral_stock_minimo     integer not null default 5,
    activo                  boolean not null default true,
    creado_en               timestamptz not null default now()
);
```

### `stock_snapshots`
Histórico de stock/precio por SKU vigilado (una fila por corrida del job).

```sql
create table stock_snapshots (
    id              bigserial primary key,
    sku             text not null references skus_monitoreados (sku) on delete cascade,
    stock           integer not null,
    price           numeric(12, 2) not null,
    capturado_en    timestamptz not null default now()
);
```

### `alertas_stock`
Alertas persistidas (stock bajo umbral, cambio de precio) — antes solo
se logueaban, ahora quedan como eventos consultables desde el dashboard.

```sql
create table alertas_stock (
    id              bigserial primary key,
    sku             text not null references skus_monitoreados (sku) on delete cascade,
    tipo            text not null,      -- 'stock_bajo' | 'cambio_precio'
    detalle         jsonb not null,
    creado_en       timestamptz not null default now()
);
```

### Tablas que NO son nuestras
- `auth.users` y el resto del schema `auth.*` — gestionado por Supabase
  Auth internamente, para el login del dashboard. Un solo usuario
  administrador hoy (el dueño del negocio). No tiene relación con
  clientes finales / WhatsApp.
- `schema_migrations` — tabla de control interna de nuestro propio script
  de migraciones (`backend/tools/apply_migrations.py`), no tiene datos de
  negocio.

## 4. Lo que NO existe (esto es lo que le toca diseñar al bot)

**No hay ninguna tabla de conversaciones, clientes/leads, ni estado
conversacional.** Cero. El bot parte de cero en esto.

Punto de diseño importante a tener en cuenta: la tabla `pedidos` de
arriba está **específicamente moldeada para el contrato con Rocketfy**
(un pedido ya cerrado, con dirección validada contra su catálogo, listo
para despachar). **No es el lugar para guardar una conversación en
curso, un lead a medio calificar, o el estado "esperando captura de
pago".** La recomendación (a validar con el equipo) es que el bot tenga
sus propias tablas nuevas (ej. `conversaciones`, `leads` o similar) que,
recién cuando una venta se cierra de verdad, disparen una llamada a
`PedidoService.crear_y_confirmar()` (ver `03_input_output_flujo.md`) —
sin intentar reusar o reestructurar la tabla `pedidos` existente para
que también sirva de "conversación".

Hay un documento de planificación previo del bot
(`docs/BotPlanifiacion.md`) que propone un esquema de ejemplo para
"pedido" con campos como `telefono_whatsapp`, `estado_conversacion`,
`captura_pago_url`, etc. — ese esquema describe lo que el bot necesita
para SU PROPIO modelo de datos (leads/conversaciones), no debe
confundirse con la tabla `pedidos` real de arriba, que ya existe y ya
está en uso por el flujo de Rocketfy.
