import time
import logging
from typing import Dict

logger = logging.getLogger("chatbot")

class CircuitBreaker:
    def __init__(self, name: str, fail_threshold: int = 3, recovery_timeout: int = 60):
        self.name = name
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "CLOSED" # CLOSED, OPEN, HALF_OPEN

    def can_execute(self) -> bool:
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info(f"Circuit Breaker '{self.name}' entering HALF_OPEN state.")
                return True
            return False
        return True

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        logger.debug(f"Circuit Breaker '{self.name}' recorded success and is CLOSED.")

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.fail_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit Breaker '{self.name}' is now OPEN due to {self.failure_count} failures.")

# Dictionary om breakers per provider bij te houden
breakers: Dict[str, CircuitBreaker] = {}

def get_breaker(provider_name: str) -> CircuitBreaker:
    if provider_name not in breakers:
        breakers[provider_name] = CircuitBreaker(provider_name)
    return breakers[provider_name]
