"""
Logging estructurado en JSON, con correlación por order_id/shopify_order_id
vía `extra={"order_id": ...}` en las llamadas de logging. Mejora sobre el
proyecto de ejemplo (texto plano) porque este backend depende de llamadas
salientes a un tercero y necesitamos trazar incidencias por pedido.
"""
import json
import logging
import sys

CORRELATION_FIELDS = ("order_id", "shopify_order_id", "id_rocketfy")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field in CORRELATION_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(app=None, level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    if app is not None:
        app.logger.handlers = [handler]
        app.logger.setLevel(level)
