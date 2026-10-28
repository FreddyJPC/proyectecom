"""
Configuración de gunicorn para producción (Railway).

Comando de arranque (desde la carpeta backend/):

    gunicorn -c gunicorn.conf.py src.app:app

Por qué UN solo worker con varios threads:
- El proceso lleva dentro el BotWorker de Victoria (cola en memoria) y el
  scheduler de jobs (reconciliación + stock watcher). Con N workers habría
  N copias de cada uno: jobs repetidos y N consumidores de la misma cola.
- Los threads sí dan concurrencia para atender requests (el dashboard, los
  webhooks de Meta y Rocketfy) dentro de ese único proceso.
- Para escalar en el futuro: sacar BotWorker y scheduler a un servicio
  aparte (ver PROGRESS.md) y recién ahí subir los workers de la web.
"""
import os

# Railway inyecta PORT; en local cae a 8000.
bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"

workers = 1
threads = 4
worker_class = "gthread"

# Victoria puede tardar en responder (Claude + herramientas), pero eso corre
# en el BotWorker, no en la request. Las requests HTTP son cortas.
timeout = 60
graceful_timeout = 30
keepalive = 5

# Logs a stdout/stderr: Railway los recoge desde ahí.
accesslog = "-"
errorlog = "-"
