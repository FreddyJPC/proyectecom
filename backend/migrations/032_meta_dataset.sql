-- Guarda el identificador del dataset de Meta (ADR-016) que crea el botón «Preparar Meta» del panel.
--
-- Para qué sirve: para avisarle a Meta una compra hay que enviarla a un «dataset» (el buzón de Meta asociado a la cuenta de WhatsApp).
-- El botón lo crea (o recupera si ya existe) con el token del servidor y guarda aquí su número. No es un secreto: es solo un
-- identificador. La variable del servidor `META_DATASET_ID`, si existe, tiene prioridad (respaldo manual).
--
-- Solo agrega una columna nueva y opcional; no toca nada ya aplicado.

alter table ajustes_negocio
    add column if not exists meta_dataset_id text;
