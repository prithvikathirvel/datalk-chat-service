import logging
import structlog
import uuid
from contextvars import ContextVar
from typing import Any, Dict

_log_context: ContextVar[Dict[str, Any]] = ContextVar("log_context", default={})


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs to current request context"""
    current = _log_context.get()
    _log_context.set({**current, **kwargs})


def clear_context() -> None:
    """Clear request context"""
    _log_context.set({})


def get_context() -> Dict[str, Any]:
    """Get current context"""
    return _log_context.get()


def add_context(logger, method_name, event_dict):
    """Inject context into every log"""
    event_dict.update(get_context())
    return event_dict


def setup_logging(environment: str = "development"):
    """Configure structlog"""

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

    processors = [
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        add_context
    ]

    if environment=="development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()


def logging_middleware(app):
    """Attach this to FastAPI app"""

    @app.middleware("http")
    async def middleware(request, call_next):
        request_id = str(uuid.uuid4())

        bind_context(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )

        try:
            response = await call_next(request)
            return response
        finally:
            clear_context()

    return app


def llm_retry_logger(retry_state):
    if retry_state.attempt_number < 1:
        loglevel = logging.INFO
    else:
        loglevel = logging.WARNING
    logger.log(
        loglevel, 'Retrying %s: attempt %s ended with: %s',
        retry_state.fn, retry_state.attempt_number, retry_state.outcome)