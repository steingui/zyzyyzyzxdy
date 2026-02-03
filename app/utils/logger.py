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
            return toon.encode(record_dict)
        except Exception:
            # Fallback if encoding fails
            return str(record_dict)

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
