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
| `axe.mjs` | Auditoría de accesibilidad (WCAG 2.1 AA + buenas prácticas) en todas las pantallas, claro y oscuro. Debe dar `SIN VIOLACIONES`. |

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
node axe.mjs                      # -> lista de problemas, o SIN VIOLACIONES
```

Si Playwright no encuentra el navegador, indica uno con `CHROMIUM_PATH=/ruta/a/chrome`
(en las sesiones en la nube de Claude hay uno en `/opt/pw-browsers/`).

Notas:
- El login del servidor falso acepta cualquier correo y contraseña.
- Si cambias la forma de un endpoint del backend, actualiza también `server.mjs`.
- No uses `pkill -f server.mjs` desde un comando que contenga ese mismo texto: se mata a sí mismo.
