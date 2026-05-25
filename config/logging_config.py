import os
import logging
import logging.config
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """
    Custom structured JSON log formatter. Parses log inputs 
    to be directly ingestible by tools like Grafana Loki or Datadog.
    """
    def format(self, record):
        log_payload = {
            "timestamp": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "line_number": record.lineno
        }
        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_payload)

def setup_production_logging():
    """
    Initializes production structured and rotating file handlers.
    Creates logs/ directory safely.
    """
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {
                "()": JSONFormatter
            },
            "standard": {
                "format": "%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
            "platform_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "INFO",
                "formatter": "json",
                "filename": os.path.join(log_dir, "platform.json.log"),
                "maxBytes": 10485760,  # 10MB limit
                "backupCount": 5,
                "encoding": "utf-8"
            },
            "error_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "level": "ERROR",
                "formatter": "json",
                "filename": os.path.join(log_dir, "errors.json.log"),
                "maxBytes": 5242880,   # 5MB limit
                "backupCount": 3,
                "encoding": "utf-8"
            }
        },
        "root": {
            "level": "INFO",
            "handlers": ["console", "platform_file", "error_file"]
        }
    }

    logging.config.dictConfig(logging_config)
    logging.getLogger("CoinDCX_Orchestrator").info("Structured production logging initialized.")
