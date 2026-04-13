import logging
from contextvars import ContextVar, Token

from backend.app.core.config import settings

TRACE_ID_CTX: ContextVar[str] = ContextVar("trace_id", default="-")
_ORIGINAL_FACTORY = logging.getLogRecordFactory()


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = TRACE_ID_CTX.get()
        return True


def set_trace_id(trace_id: str) -> Token:
    return TRACE_ID_CTX.set(trace_id)


def reset_trace_id(token: Token) -> None:
    TRACE_ID_CTX.reset(token)


def _record_factory(*args, **kwargs) -> logging.LogRecord:
    record = _ORIGINAL_FACTORY(*args, **kwargs)
    if not hasattr(record, "trace_id"):
        record.trace_id = TRACE_ID_CTX.get()
    return record


def configure_logging(debug: bool, *, log_level: str | None = None) -> None:
    level_name = log_level or ("DEBUG" if debug else settings.log_level)
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.setLogRecordFactory(_record_factory)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(trace_id)s | %(name)s | %(message)s",
        force=True,
    )
    logging.getLogger().addFilter(TraceIdFilter())


def init_logging() -> None:
    configure_logging(settings.app_debug, log_level=settings.log_level)
