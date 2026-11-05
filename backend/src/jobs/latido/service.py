"""
Latido de la base de datos: una escritura + una lectura chicas, cada pocas
horas, para que el proyecto de Supabase (plan gratuito) siempre tenga
actividad y no se pause por inactividad (7 días con poca actividad).

Dos decisiones deliberadas:
- SIN lock en job_locks (a diferencia de reconciliación/stock): el latido es
  idempotente e inofensivo si dos corridas se solapan, y tomar el lock
  añadiría dos escrituras más por nada.
- El resultado queda también EN MEMORIA (estado_latido) para que /health lo
  muestre sin consultar la base. /health no debe tocar la DB: Railway lo usa
  como healthcheck y, si la DB cae, un /health que dependiera de ella
  marcaría el servicio como caído y lo reiniciaría en bucle (ver #25).
"""
import logging
from datetime import datetime, timezone
from threading import Lock
from typing import Optional

from .repository import LatidoRepository

logger = logging.getLogger(__name__)

# Estado del último intento en este proceso. Se pierde al reiniciar (normal:
# el job corre ~30 s después de cada arranque, ver app.start_scheduler()).
_lock = Lock()
_ultimo_ok: Optional[datetime] = None
_fallos_seguidos = 0


def estado_latido() -> dict:
    """Para /health. `ultimo_ok` es None hasta que el primer latido del
    proceso funciona; `fallos_seguidos` > 0 significa que la base no está
    respondiendo (o el latido está fallando)."""
    with _lock:
        return {
            "ultimo_ok": _ultimo_ok.isoformat() if _ultimo_ok else None,
            "fallos_seguidos": _fallos_seguidos,
        }


def reiniciar_estado() -> None:
    """Solo para tests: deja el estado como en un proceso recién arrancado."""
    global _ultimo_ok, _fallos_seguidos
    with _lock:
        _ultimo_ok = None
        _fallos_seguidos = 0


class LatidoService:
    def __init__(self, repo: Optional[LatidoRepository] = None):
        self._repo = repo or LatidoRepository()

    def ejecutar(self) -> bool:
        """True si el latido se registró. Nunca lanza: si la base está
        caída solo se loguea y se cuenta el fallo; el siguiente intento es
        en la próxima corrida."""
        global _ultimo_ok, _fallos_seguidos
        try:
            _, contador = self._repo.registrar_latido()
        except Exception:
            with _lock:
                _fallos_seguidos += 1
                fallos = _fallos_seguidos
            logger.exception("Latido de la base de datos falló (%d seguidos)", fallos)
            return False

        with _lock:
            _ultimo_ok = datetime.now(timezone.utc)
            _fallos_seguidos = 0
        logger.info("Latido de la base de datos registrado (n.º %s)", contador)
        return True
