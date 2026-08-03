import logging
from logging.config import dictConfig


def configure_logging(level: str = "INFO") -> None:
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": (
                        "%(asctime)s %(levelname)s %(name)s "
                        "request_id=%(request_id)s %(message)s"
                    ),
                    "defaults": {"request_id": "-"},
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": level.upper(),
                }
            },
            "root": {"handlers": ["console"], "level": level.upper()},
        }
    )
    logging.captureWarnings(True)

