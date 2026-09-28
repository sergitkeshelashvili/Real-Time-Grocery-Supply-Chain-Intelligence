import json, logging, sys
from datetime import datetime, timezone

class JsonFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "service": getattr(record, "service", "app"), "level": record.levelname, "event": getattr(record, "event", "log"), "message": record.getMessage()})

def get_logger(service):
    logger = logging.getLogger(service)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logging.LoggerAdapter(logger, {"service": service})
