"""
throttle.py - Adaptive throttling for web scraping
"""
import time
from collections import deque
import logging

logger = logging.getLogger(__name__)

class AdaptiveThrottle:
    """
    Implements adaptive rate limiting based on server response times.
    
    Logic:
    - Maintains a history of recent delays.
    - If response time is high, increases wait time.
    - If response time is low, decreases wait time (down to min_delay).
    """
    def __init__(self, min_delay: float = 0.5, max_delay: float = 5.0, history_size: int = 10):
        self.delays = deque(maxlen=history_size)
        self.min_delay = min_delay
        self.max_delay = max_delay
    
    def wait(self, response_time: float):
        """
        Calculates and executes sleep time based on the last response duration.
        
        Args:
            response_time (float): Time taken for the last request/operation in seconds.
        """
        # Calculate target delay: proportional to response time
        # Heuristic: wait 1.5x the response time to be polite, clamped to [min, max]
        target_delay = max(self.min_delay, min(response_time * 1.5, self.max_delay))
        
        logger.debug(f"Adaptive Throttle: response_time={response_time:.2f}s, sleeping for {target_delay:.2f}s")
        
        time.sleep(target_delay)
        self.delays.append(target_delay)

    def get_avg_delay(self) -> float:
        """Returns the average delay over the recent history."""
        if not self.delays:
            return 0.0
        return sum(self.delays) / len(self.delays)
