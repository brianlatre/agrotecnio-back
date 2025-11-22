# app/core/logging.py
import logging
import os
import sys
from typing import Any

from loguru import logger

# Directorio donde se guardarán los logs.
# Por defecto /logs, pero puedes sobreescribir con la variable de entorno LOG_DIR.
LOG_DIR = os.getenv("LOG_DIR", "/logs")


class InterceptHandler(logging.Handler):
    """
    Redirige los logs de logging estándar a loguru.
    """
    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = logging.currentframe(), 2
        # sube en la pila hasta salir de logging/__init__.py
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(
            depth=depth,
            exception=record.exc_info,
        ).log(level, record.getMessage())


def setup_logging(
    *,
    json_logs: bool = False,
    log_file: bool = True,
) -> None:
    """
    Config global:
    - Intercepta logging estándar (uvicorn, sqlalchemy, fastapi, etc.)
    - Consola: todos los niveles
    - Ficheros:
        - app_YYYY-MM-DD.log   → INFO y WARNING
        - error_YYYY-MM-DD.log → ERROR y superiores
    """
    # Limpia handlers de logging estándar
    logging.root.handlers = []
    logging.root.setLevel(logging.INFO)

    # Intercepta todos los loggers conocidos
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastapi", "sqlalchemy"):
        logging.getLogger(name).handlers = [InterceptHandler()]
        logging.getLogger(name).propagate = False

    logger.remove()

    # Formato (texto o JSON)
    if json_logs:
        fmt = (
            '{{"time":"{time}","level":"{level}","message":{message!r},'
            '"name":"{name}","function":"{function}","line":{line}}}'
        )
    else:
        fmt = (
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        )

    # Consola: todo
    logger.add(
        sys.stdout,
        format=fmt,
        level="INFO",
        backtrace=True,
        diagnose=False,
    )

    if log_file:
        os.makedirs(LOG_DIR, exist_ok=True)

        # Ficheros diarios con fecha en el nombre
        app_log_path = os.path.join(LOG_DIR, "app_{time:YYYY-MM-DD}.log")
        error_log_path = os.path.join(LOG_DIR, "error_{time:YYYY-MM-DD}.log")

        # INFO / WARNING → app_YYYY-MM-DD.log
        logger.add(
            app_log_path,
            format=fmt,
            # A partir de INFO, pero filtramos para que no se dupliquen los errores
            level="INFO",
            filter=lambda record: record["level"].no < 40,  # < ERROR (40)
            rotation="00:00",          # rotación diaria a medianoche
            retention="7 days",        # guarda 7 días
            compression="zip",
            enqueue=True,
        )

        # Solo errores y críticos → error_YYYY-MM-DD.log
        logger.add(
            error_log_path,
            format=fmt,
            level="ERROR",             # solo ERROR y CRITICAL
            rotation="00:00",          # rotación diaria
            retention="30 days",       # errores los dejamos más tiempo
            compression="zip",
            enqueue=True,
        )


def get_logger(**binds: Any):
    """
    Helper para obtener un logger con contexto extra.
    Ej: logger = get_logger(endpoint="simulation_next_day")
    """
    return logger.bind(**binds)
