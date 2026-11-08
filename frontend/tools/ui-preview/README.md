# ui-preview — ver y auditar la interfaz sin backend real

Herramientas **solo de desarrollo** (no se despliegan: Vercel construye únicamente
lo que está en `frontend/` según su `package.json` y esta carpeta tiene el suyo).
Sirven para mirar cada pantalla en un navegador real, en escritorio, tablet y
móvil, en claro y oscuro, y para auditar accesibilidad, **sin tocar Supabase,
Rocketfy ni WhatsApp**.

## Qué hay
| Archivo | Para qué |
|---|---|
| `server.mjs` | Servidor falso que simula el login de Supabase y la API del backend con datos realistas (pedidos, conversaciones, alertas, catálogo, métricas). |
| `shots.mjs` | Inicia sesión y saca capturas de cada pantalla (escritorio 1440 px y móvil 390 px). |
| `interact.mjs` | Capturas de interacciones: menú "Más", diálogos, panel de datos, estados de error y vacío, tablet. |
| `axe.mjs` | Auditoría de accesibilidad (WCAG 2.1 AA + buenas prácticas) en todas las pantallas y en los cuadros abiertos, claro y oscuro, **y comprobación de desborde horizontal** (nada fuera de pantalla en el móvil). **Abre cada botón ⓘ** (`InfoButton`) de cada pantalla —y los que hay dentro de otros cuadros— y audita su cuadro (`SIN_INFOS=1` los salta para ir más rápido). Debe dar `SIN VIOLACIONES`. |

## Cómo usarlas
```bash
# 1) una sola vez
cd frontend/tools/ui-preview && npm install

# 2) servidor falso (puerto 5050)
node server.mjs &

# 3) el frontend apuntando al servidor falso (en otra terminal, desde frontend/)
NEXT_PUBLIC_SUPABASE_URL=http://127.0.0.1:5050 \
NEXT_PUBLIC_SUPABASE_ANON_KEY=mock \
NEXT_PUBLIC_API_URL=http://127.0.0.1:5050 \
npx next dev -p 3100

# 4) capturas / auditoría (desde frontend/tools/ui-preview)
node shots.mjs                    # -> shots/*.png  (OUT=carpeta, ONLY=resumen,pedidos, THEME=dark, FULL=0)
node interact.mjs                 # -> shots/*.png
node axe.mjs                      # -> lista de problemas, o SIN VIOLACIONES (ONLY=/gestion,/catalogo/propio para auditar solo algunas rutas; SIN_INFOS=1 para no abrir los cuadros ⓘ; la auditoría completa tarda ~10 min)
```

Si Playwright no encuentra el navegador, indica uno con `CHROMIUM_PATH=/ruta/a/chrome`
(en las sesiones en la nube de Claude hay uno en `/opt/pw-browsers/`).

Notas:
- El login del servidor falso acepta cualquier correo y contraseña.
- Si cambias la forma de un endpoint del backend, actualiza también `server.mjs`.
- Productos propios (ADR-012): el servidor falso trae `PROP-0001` (zapatos, activo, 3 opciones de entrega, 2 fotos) y `PROP-0002`
  (camiseta, borrador, sin control de stock), categorías, «Por gestionar» (`/gestion`) y imita Supabase Storage
  (`/storage/v1/object/...`): las fotos «subidas» se sirven como imágenes de relleno. «Por gestionar» trae ventas por cobrar, cobradas y canceladas, y `/ventas/<id>/cobrar|deshacer-cobro|cancelar` cambian su estado en memoria (reinicia el servidor para volver a los datos originales).
- `parametros-catalogo.json` e `instrucciones-secciones.json` salen del backend (catálogo de Parámetros y secciones de las instrucciones de Victoria) en la forma que devuelve la API
  (así la pantalla se ve con las explicaciones y rangos reales). Si cambias `backend/src/config/parametros/catalogo.py`,
  regénéralo desde `backend/` con el entorno de pruebas activo: `python tools/exportar_para_preview.py`.
- No uses `pkill -f server.mjs` desde un comando que contenga ese mismo texto: se mata a sí mismo.
