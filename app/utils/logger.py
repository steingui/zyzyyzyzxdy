import logging
import sys
import toon
from datetime import datetime

# Configurable Max String Length for Token Economy
MAX_STR_LENGTH = 1000
MAX_LIST_SAMPLE = 5

class ToonFormatter(logging.Formatter):
    """
    Custom TOON Formatter implementing RFC 005:
    - TOON Format (Token-Oriented Object Notation)
    - Token Economy (Truncation, None removal)
    - ISO Timestamps
    """
    
    def format(self, record):
        # Build dictionary manually
        record_dict = {
            "timestamp": datetime.utcfromtimestamp(record.created).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage()
        }
        
        # Add extra fields (those passed in extra={...})
        # Exclude standard attributes
        standard_keys = [
            'args', 'asctime', 'created', 'exc_info', 'exc_text', 'filename',
            'funcName', 'levelname', 'levelno', 'lineno', 'module', 'msecs',
            'message', 'msg', 'name', 'pathname', 'process', 'processName',
            'relativeCreated', 'stack_info', 'thread', 'threadName', 'timestamp'
        ]
        
        for key, value in record.__dict__.items():
            if key not in standard_keys and not key.startswith('_'):
                record_dict[key] = value

        # Exception handling
        if record.exc_info:
             if not record.exc_text:
                 record.exc_text = self.formatException(record.exc_info)
             record_dict['exception'] = record.exc_text

        # Token Economy: Process all fields
        self._economize_tokens(record_dict)
        
        # Encode to TOON
        try:
            return toon.encode(record_dict) + '\n'
        except Exception:
            # Fallback if encoding fails
            return str(record_dict) + '\n'

    def _economize_tokens(self, data):
        """
        Recursively traverse the dict to:
        1. Remove None values
        2. Truncate long strings
        3. Sample large lists
        """
        keys_to_remove = []
        
        for key, value in data.items():
            # 1. Remove None
            if value is None:
                keys_to_remove.append(key)
                continue
                
            # 2. Truncate Strings
            if isinstance(value, str):
                if len(value) > MAX_STR_LENGTH:
                    data[key] = value[:MAX_STR_LENGTH] + f" ... (truncated {len(value)-MAX_STR_LENGTH} chars)"
            
            # 3. Handle Lists (Sampling)
            elif isinstance(value, list):
                if len(value) > MAX_LIST_SAMPLE:
                    data[key] = {
                        "total_count": len(value),
                        "sample": value[:MAX_LIST_SAMPLE],
                        "note": "List truncated for token economy"
                    }
            
            # Recursion for dicts
            elif isinstance(value, dict):
                self._economize_tokens(value)
                
        for k in keys_to_remove:
            data.pop(k)

def get_logger(name, level=logging.INFO):
    """
    Returns a configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
        
    logger.setLevel(level)
    
    # Console Handler (Stderr to avoid polluting stdout data pipes)
    handler = logging.StreamHandler(sys.stderr)
    
    # TOON Formatter
    formatter = ToonFormatter()
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    
    # Prevent propagation to avoid double logging if root logger is also configured (or not)
    logger.propagate = False
    
    return logger

def log_error_state(logger, error, context_data=None):
    """
    Helper to log exceptions with state snapshot
    """
    payload = {
        "error_type": type(error).__name__,
        "error_message": str(error),
    }
    
    if context_data:
        payload["input_dto"] = context_data
        
    logger.error("Operation failed", extra=payload, exc_info=True)


def slog(logger_instance, level, message, component, operation=None, **context):
    """
    Structured log helper for LLM-friendly output.
    
    Every log entry gets a `component` tag for filtering/routing.
    Additional context fields are passed as structured data via TOON.
    
    Usage:
        slog(logger, 'info', 'Matches discovered', component='pipeline',
             operation='discover', round=1, total_matches=10)
    
    Output (TOON):
        level: INFO
        name: scripts.run_batch
        message: Matches discovered
        component: pipeline
        operation: discover
        round: 1
        total_matches: 10
    """
    extra = {"component": component}
    if operation:
        extra["operation"] = operation
    extra.update(context)
    
    log_method = getattr(logger_instance, level.lower(), logger_instance.info)
    log_method(message, extra=extra)


def log_diagnostic(logger_instance, message, component, operation, 
                   error=None, hint=None, expected=None, actual=None, **context):
    """
    LLM Debug Packet: rich structured error context for automated diagnosis.
    
    Includes expected vs actual values and human-readable hints so an LLM
    can diagnose the issue from logs alone without reading source code.
    
    Usage:
        log_diagnostic(logger, "No finished matches found",
            component="crawler", operation="check_results",
            expected="td.result a elements > 0",
            actual="0 elements found",
            hint="Page loaded but no result links. Possible: round not started, CSS changed, anti-bot",
            url=url, selector="#fixture_games td.result a")
    """
    extra = {
        "component": component,
        "operation": operation,
    }
    
    if hint:
        extra["hint"] = hint
    if expected:
        extra["expected"] = expected
    if actual:
        extra["actual"] = actual
    
    extra.update(context)
    
    if error:
        extra["error_type"] = type(error).__name__
        extra["error_message"] = str(error)
        logger_instance.error(message, extra=extra, exc_info=True)
    else:
        logger_instance.warning(message, extra=extra)
