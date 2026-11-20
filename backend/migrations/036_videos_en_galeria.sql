-- Entrada 0.0.163: la galería del producto también guarda VIDEOS (pedido de Freddy, 2026-11-20). Todo lo que el dueño sube
-- es «material del producto» y Victoria lo manda completo cuando el cliente pide fotos o videos.
--
-- La tabla `imagenes_producto` no cambia: el tipo (foto o video) sale de la extensión del archivo (`imagenes/logica.py`).
-- Solo cambia el bucket `productos` de Supabase Storage (creado en la 021):
--   - acepta también video MP4 y 3GP (los únicos que WhatsApp envía; un .mov del iPhone no sirve);
--   - el tamaño máximo sube de 5 MB a 16 MB (el límite de WhatsApp para un video). Las fotos se siguen reduciendo en la
--     app antes de subir, así que en la práctica pesan mucho menos.
-- Solo si existe el esquema `storage` (en Supabase sí; en la base de pruebas local no).
do $$
begin
    if exists (select 1 from information_schema.schemata where schema_name = 'storage') then
        update storage.buckets
           set file_size_limit = 16777216,
               allowed_mime_types = array['image/jpeg', 'image/png', 'video/mp4', 'video/3gpp']
         where id = 'productos';
    end if;
end
$$;
