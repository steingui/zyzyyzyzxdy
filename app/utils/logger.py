import logging
import sys
import json
from datetime import datetime
from pythonjsonlogger import jsonlogger

# Configurable Max String Length for Token Economy
MAX_STR_LENGTH = 1000
MAX_LIST_SAMPLE = 5

class LLMFriendlyFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON Formatter implementing RFC 005:
    - Structured JSON
    - Token Economy (Truncation, None removal)
    - ISO Timestamps
    """
    
    def add_fields(self, log_record, record, message_dict):
        super(LLMFriendlyFormatter, self).add_fields(log_record, record, message_dict)
        
        # Standardize timestamp
        if not log_record.get('timestamp'):
            log_record['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
            
        # Standardize Level
        if log_record.get('level'):
            log_record['level'] = log_record['level'].upper()
        else:
            log_record['level'] = record.levelname
            
        # Remove redundancy
        log_record.pop('levelname', None)
        log_record.pop('asctime', None)
        log_record.pop('exc_info', None) # Handled by jsonlogger usually, but we want clean output

        # Token Economy: Process all fields
        self._economize_tokens(log_record)

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
    
    # JSON Formatter
    formatter = LLMFriendlyFormatter(
        '%(timestamp)s %(level)s %(name)s %(message)s'
    )
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
