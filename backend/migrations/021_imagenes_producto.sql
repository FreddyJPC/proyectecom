-- ADR-012 (entrega 2): fotos de los productos en un bucket de Supabase Storage.
--
-- Cada producto —de Rocketfy, propio o de cualquier proveedor— puede tener su galería de fotos. Las fotos las
-- sube el dueño desde la app (con su sesión de login: el servidor no necesita ninguna clave nueva) y quedan
-- guardadas en el bucket público `productos`. Esta tabla dice cuáles pertenecen a cada producto y en qué
-- orden; la primera es la principal. Si un producto no tiene fotos subidas, Victoria usa la de Rocketfy
-- (`productos_bot.imagen_url`); si tampoco hay, le dice al cliente que por ahora no hay imágenes.

create table if not exists imagenes_producto (
    id            bigserial primary key,
    producto_sku  text not null references productos_bot (sku) on update cascade on delete cascade,
    -- Enlace público https del archivo en el bucket (es lo que descarga Meta para enviarlo por WhatsApp).
    url           text not null check (url like 'https://%'),
    -- Ruta dentro del bucket (`<sku>/<archivo>.jpg`): permite borrar el archivo al quitar la foto.
    storage_path  text not null,
    orden         integer not null default 0,
    creado_en     timestamptz not null default now(),
    creado_por    text,
    unique (storage_path)
);

create index if not exists idx_imagenes_producto_sku on imagenes_producto (producto_sku, orden, id);

-- Sin policies: el backend entra con el rol postgres (se salta RLS); con RLS activado la API pública de
-- Supabase (clave anónima) no puede leer ni escribir esta tabla. Los archivos se protegen aparte (abajo).
alter table imagenes_producto enable row level security;

-- ---------------------------------------------------------------------------
-- El bucket. Solo si existe el esquema `storage` (en Supabase sí; en la base de pruebas local no).
--   - Público para LEER: el enlace de cada foto tiene que poder abrirlo Meta y el cliente de WhatsApp.
--   - Solo JPEG y PNG (WhatsApp no acepta otros formatos de imagen) y hasta 5 MB por archivo.
--   - Solo quien inició sesión en la app (rol `authenticated`) puede subir, reemplazar o borrar; nadie más.
-- ---------------------------------------------------------------------------
do $$
begin
    if exists (select 1 from information_schema.schemata where schema_name = 'storage') then
        insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
        values ('productos', 'productos', true, 5242880, array['image/jpeg', 'image/png'])
        on conflict (id) do update
            set public = excluded.public,
                file_size_limit = excluded.file_size_limit,
                allowed_mime_types = excluded.allowed_mime_types;

        -- Ver: el archivo se lee por su enlace público (no necesita policy), pero borrar o reemplazar un archivo
        -- exige poder verlo, así que quien inició sesión también puede ver el contenido del bucket.
        drop policy if exists "productos_ver" on storage.objects;
        create policy "productos_ver" on storage.objects
            for select to authenticated using (bucket_id = 'productos');

        drop policy if exists "productos_subir" on storage.objects;
        create policy "productos_subir" on storage.objects
            for insert to authenticated with check (bucket_id = 'productos');

        drop policy if exists "productos_reemplazar" on storage.objects;
        create policy "productos_reemplazar" on storage.objects
            for update to authenticated using (bucket_id = 'productos') with check (bucket_id = 'productos');

        drop policy if exists "productos_borrar" on storage.objects;
        create policy "productos_borrar" on storage.objects
            for delete to authenticated using (bucket_id = 'productos');
    end if;
end
$$;
