-- Fase E del plan de gestión de productos (docs/PLAN_GESTION_PRODUCTOS.md):
-- "Probar con Victoria". Solo AGREGA una columna con valor de partida; el bot
-- real no lee nada de esto, así que sigue funcionando igual.

-- Mensajes de prueba permitidos por día (se cuenta por día de Ecuador). Cada
-- mensaje de prueba llama a la IA igual que uno real (y a veces varias veces,
-- porque Victoria usa herramientas), así que cuesta plata: de ahí el tope. Se
-- registran en `generaciones_ia` (migración 016) con tipo 'simulacion'; esa
-- tabla no restringe `tipo`, por eso no hace falta tocarla.
alter table ajustes_negocio
    add column if not exists tope_pruebas_dia integer not null default 100
        check (tope_pruebas_dia between 1 and 1000);
