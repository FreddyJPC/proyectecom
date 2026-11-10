-- Cuentas para transferir (pendiente #76, punto 1): a qué cuenta le pide Victoria al cliente que transfiera.
--
-- Para qué sirve: un producto puede aceptar «transferencia», pero Victoria nunca inventa ni escribe a mano un número de cuenta.
-- Las cuentas del dueño viven aquí; el texto con los datos lo arma el CÓDIGO desde esta tabla (como el resumen del pedido) y
-- Victoria lo manda tal cual. Así no se equivoca de dígito, y si el dueño cambia de cuenta lo cambia en el panel
-- (Control → Cuentas para transferir), sin tocar código.
--
--   banco          : como se le muestra al cliente («Banco Pichincha»). El nombre se compara sin tildes ni «banco/cooperativa»,
--                    así «pichncha» o «banco guayaquil» se reconocen.
--   tipo_cuenta    : «Cuenta de ahorros», «Cuenta digital»…
--   numero         : el número de cuenta, como texto (puede llevar ceros a la izquierda).
--   titular        : a nombre de quién está.
--   identificacion : cédula o RUC del titular (opcional): se muestra al cliente para que verifique al beneficiario.
--   activa / orden : se puede apagar una cuenta sin borrarla; la de menor «orden» es la principal.
--
-- No lleva datos: las cuentas reales las carga el dueño desde el panel (nunca van en el repositorio).

create table if not exists cuentas_bancarias (
    id              bigserial primary key,
    banco           text        not null,
    tipo_cuenta     text        not null,
    numero          text        not null,
    titular         text        not null,
    identificacion  text,
    activa          boolean     not null default true,
    orden           integer     not null default 0,
    creado_en       timestamptz not null default now(),
    actualizado_en  timestamptz not null default now(),
    constraint cuentas_bancarias_banco_numero_uk unique (banco, numero)
);

create index if not exists idx_cuentas_bancarias_activa_orden on cuentas_bancarias (activa, orden, id);
