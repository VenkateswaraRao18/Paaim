"""Logging configuration for production PAAIM system."""

import logging
import logging.config
import sys
import json
from typing import Any, Dict
from pythonjsonlogger import jsonlogger


class JSONFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter for structured logging."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add standard fields
        log_record["timestamp"] = record.created
        log_record["level"] = record.levelname
        log_record["logger"] = record.name
        log_record["module"] = record.module

        # Add trace ID if available (for distributed tracing)
        if hasattr(record, "trace_id"):
            log_record["trace_id"] = record.trace_id


def setup_logging(level: str = "INFO", json_output: bool = True) -> None:
    """
    Configure logging for PAAIM system.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: Output JSON format (production) vs plain text (development)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_output:
        # Production: JSON output to stdout
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            JSONFormatter(
                "%(timestamp)s %(level)s %(logger)s %(message)s"
            )
        )
    else:
        # Development: Plain text with colors
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)

    handler.setLevel(log_level)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce verbosity of third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger
    """
    return logging.getLogger(name)


# Log event types for standardized tracking
class LogEventType:
    """Standardized log event types for PAAIM."""

    # Orchestration events
    ORCHESTRATION_START = "orchestration_start"
    ORCHESTRATION_COMPLETE = "orchestration_complete"
    ORCHESTRATION_ERROR = "orchestration_error"

    # Agent events
    AGENT_ANALYSIS = "agent_analysis"
    AGENT_ERROR = "agent_error"

    # Policy events
    POLICY_EVALUATION = "policy_evaluation"
    POLICY_VIOLATION = "policy_violation"

    # Decision Twin events
    TWIN_SIMULATION = "twin_simulation"
    TWIN_ERROR = "twin_error"

    # Red Team events
    RED_TEAM_CHALLENGE = "red_team_challenge"
    RED_TEAM_ERROR = "red_team_error"

    # Approval events
    APPROVAL_ROUTED = "approval_routed"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"

    # Connector events
    CONNECTOR_CONNECTED = "connector_connected"
    CONNECTOR_DISCONNECTED = "connector_disconnected"
    CONNECTOR_ERROR = "connector_error"
    CONNECTOR_HEALTH_CHECK = "connector_health_check"

    # Database events
    DATABASE_QUERY = "database_query"
    DATABASE_ERROR = "database_error"

    # API events
    API_REQUEST = "api_request"
    API_RESPONSE = "api_response"
    API_ERROR = "api_error"


def log_event(
    logger: logging.Logger,
    event_type: str,
    message: str,
    **kwargs,
) -> None:
    """
    Log a structured event.

    Args:
        logger: Logger instance
        event_type: Type of event (from LogEventType)
        message: Human-readable message
        **kwargs: Additional fields for JSON output
    """
    log_data = {
        "event_type": event_type,
        "message": message,
        **kwargs,
    }

    # Determine log level based on event type
    if "error" in event_type.lower():
        logger.error(json.dumps(log_data))
    elif "warning" in event_type.lower():
        logger.warning(json.dumps(log_data))
    else:
        logger.info(json.dumps(log_data))
