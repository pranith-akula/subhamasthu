"""
Structured logging configuration.
Outputs JSON in production for observability (e.g. Datadog/Railway logs).
Outputs colored text in development for readability.
"""

import sys
import logging
import json
from datetime import datetime, timezone
from typing import Any, Dict

from app.config import settings


class JSONFormatter(logging.Formatter):
    """Format logs as JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
            
        # Add extra fields if available
        if hasattr(record, "extra"):
            log_obj.update(record.extra)  # type: ignore
            
        return json.dumps(log_obj)


def configure_logging():
    """Configure root logger."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if settings.is_production else logging.DEBUG)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    
    if settings.is_production:
        # JSON formatting for production
        console_handler.setFormatter(JSONFormatter())
    else:
        # Standard formatting for development
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        
    root_logger.addHandler(console_handler)
    
    # Set levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
