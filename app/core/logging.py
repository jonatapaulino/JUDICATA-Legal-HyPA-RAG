"""
Structured logging configuration using structlog.
Provides JSON-formatted logs for production and human-readable logs for development.

Author: Delvek da S. V. de Sousa
Copyright (c) 2025 Delvek da S. V. de Sousa
"""
import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def add_trace_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add trace_id to log context if available.
    This allows tracking requests across the entire pipeline.
    """
    # Trace ID will be set by middleware in main.py
    if "trace_id" not in event_dict:
        event_dict["trace_id"] = "none"
    return event_dict


def add_app_context(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Add application-level context to all logs."""
    event_dict["environment"] = settings.environment
    event_dict["service"] = "judicial-backend"
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog with appropriate processors for the environment.

    Production: JSON logs for machine parsing
    Development: Colored console logs for human reading
    """

    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        add_trace_id,
        add_app_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
    ]

    # Environment-specific processors
    if settings.is_production or settings.log_format == "json":
        # Production: JSON output
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]
    else:
        # Development: Human-readable colored output
        processors = shared_processors + [
            structlog.processors.ExceptionPrettyPrinter(),
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level),
        stream=sys.stdout,
    )

    # Set log levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name (typically __name__ of the module)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


class LoggerMixin:
    """
    Mixin class that provides a logger attribute to any class.

    Usage:
        class MyClass(LoggerMixin):
            def my_method(self):
                self.logger.info("doing something")
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        """Get logger for this class."""
        return get_logger(self.__class__.__name__)
