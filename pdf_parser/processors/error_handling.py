import json
import logging
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    INVALID_INPUT = "INVALID_INPUT"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    EXTRACTION_ERROR = "EXTRACTION_ERROR"
    NORMALIZATION_ERROR = "NORMALIZATION_ERROR"
    MAPPING_ERROR = "MAPPING_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EXPORT_ERROR = "EXPORT_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    FILE_IO_ERROR = "FILE_IO_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class PipelineError(Exception):
    """Represents a classified pipeline failure with structured context."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        recoverable: bool = False,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.recoverable = recoverable
        self.context = context or {}
        self.cause = cause

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the error for logging and programmatic handling."""
        return {
            "code": self.code.value,
            "message": self.message,
            "recoverable": self.recoverable,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
        }


def configure_logger(name: str) -> logging.Logger:
    """Creates a process-safe logger configured for JSON-like message payloads."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(logger: logging.Logger, level: int, event: str, **context: Any) -> None:
    """Emits a structured event log message as a single JSON payload."""
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
