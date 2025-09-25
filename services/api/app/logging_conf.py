import logging, logging.config

def setup_logging():
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"std": {"format": "%(levelname)s %(asctime)s %(name)s: %(message)s"}},
        "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "std"}},
        "root": {"level": "INFO", "handlers": ["console"]},
    }
    logging.config.dictConfig(LOGGING)
