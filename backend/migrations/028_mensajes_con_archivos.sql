-- Mensajes con archivos (fotos, audios, documentos) — docs/PLAN_IMAGENES_AUDIO.md, fase F1.
--
-- Para qué sirve: hasta ahora `mensajes` solo guardaba texto («[imagen]», «[audio]») y se perdía QUÉ archivo era. Ahora cada mensaje
-- que trae un archivo guarda su identificador en Meta, para poder bajarlo y dárselo a Victoria (que lo ve o lo escucha) y para que el
-- dueño lo vea en el panel. El archivo mismo NO se copia a otro lado: Meta lo conserva unos 30 días y se baja de allí cuando hace falta.
--
--   media_id     : identificador del archivo en Meta (se usa para descargarlo).
--   media_mime   : tipo de archivo (image/jpeg, audio/ogg, application/pdf…).
--   media_nombre : nombre del documento, si lo trae.
--   analisis     : lo que Victoria (o la transcripción) entendió del archivo, en texto: es lo que se le muestra en el historial en
--                  lugar de volver a mandarle la imagen cada vez. Para un audio es la transcripción.
--
-- Solo se agregan columnas nuevas y nulables; no se toca nada ya aplicado.

alter table mensajes
    add column if not exists media_id text,
    add column if not exists media_mime text,
    add column if not exists media_nombre text,
    add column if not exists analisis text;
