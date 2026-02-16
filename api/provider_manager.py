"""
Provider Manager Module

This module implements the ProviderManager class for managing AI provider
selection, failure tracking, and cooldown logic.

Validates Requirements: 8.1, 8.3, 8.4
"""

import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ProviderManager:
    """
    Manages AI provider selection with failure tracking and cooldown logic.
    
    This class tracks provider health, implements cooldown after consecutive
    failures, and selects the best available provider based on recent performance.
    
    Attributes:
        providers: List of available provider names
        failure_counts: Dictionary tracking consecutive failures per provider
        cooldown_until: Dictionary tracking cooldown expiry timestamps per provider
        last_success: Dictionary tracking last successful use timestamp per provider
    """
    
    def __init__(self, providers: Optional[list] = None):
        """
        Initialize the ProviderManager.
        
        Args:
            providers: List of provider names. Defaults to ["g4f", "pollinations"]
        """
        self.providers = providers or ["g4f", "pollinations"]
        self.failure_counts: Dict[str, int] = {p: 0 for p in self.providers}
        self.cooldown_until: Dict[str, float] = {p: 0.0 for p in self.providers}
        self.last_success: Dict[str, float] = {p: 0.0 for p in self.providers}
        
        logger.info(f"ProviderManager initialized with providers: {self.providers}")
    
    def get_next_provider(self) -> str:
        """
        Selects the next available provider based on health status.
        
        This method:
        1. Filters out providers in cooldown
        2. Prefers providers with lower failure counts
        3. Falls back to any available provider if all are in cooldown
        
        Returns:
            str: Name of the provider to use
        """
        current_time = time.time()
        
        # Filter providers not in cooldown
        available_providers = [
            p for p in self.providers
            if current_time >= self.cooldown_until[p]
        ]
        
        if not available_providers:
            # All providers are in cooldown, use the one closest to recovery
            logger.warning("All providers in cooldown, selecting provider with shortest cooldown")
            available_providers = [
                min(self.providers, key=lambda p: self.cooldown_until[p])
            ]
        
        # Select provider with lowest failure count
        selected = min(available_providers, key=lambda p: self.failure_counts[p])
        
        logger.info(
            f"Selected provider: {selected} "
            f"(failures: {self.failure_counts[selected]}, "
            f"cooldown_until: {self.cooldown_until[selected]})"
        )
        
        return selected
    
    def record_failure(self, provider: str) -> None:
        """
        Records a provider failure and manages cooldown.
        
        This method:
        1. Increments the consecutive failure count
        2. If failures reach 3, places provider in 5-minute cooldown
        3. Logs the failure for debugging
        
        Args:
            provider: Name of the provider that failed
        """
        if provider not in self.providers:
            logger.warning(f"Attempted to record failure for unknown provider: {provider}")
            return
        
        self.failure_counts[provider] += 1
        current_time = time.time()
        
        logger.warning(
            f"Provider {provider} failure recorded. "
            f"Consecutive failures: {self.failure_counts[provider]}"
        )
        
        # Place in cooldown after 3 consecutive failures
        if self.failure_counts[provider] >= 3:
            cooldown_duration = 300  # 5 minutes in seconds
            self.cooldown_until[provider] = current_time + cooldown_duration
            
            logger.error(
                f"Provider {provider} placed in cooldown for {cooldown_duration} seconds "
                f"after {self.failure_counts[provider]} consecutive failures"
            )
    
    def record_success(self, provider: str) -> None:
        """
        Records a provider success and resets failure count.
        
        This method:
        1. Resets the consecutive failure count to 0
        2. Updates the last success timestamp
        3. Logs the success for debugging
        
        Args:
            provider: Name of the provider that succeeded
        """
        if provider not in self.providers:
            logger.warning(f"Attempted to record success for unknown provider: {provider}")
            return
        
        previous_failures = self.failure_counts[provider]
        self.failure_counts[provider] = 0
        self.last_success[provider] = time.time()
        
        if previous_failures > 0:
            logger.info(
                f"Provider {provider} success recorded. "
                f"Reset failure count from {previous_failures} to 0"
            )
        else:
            logger.debug(f"Provider {provider} success recorded")
    
    def get_provider_status(self) -> Dict[str, Dict]:
        """
        Returns the current status of all providers.
        
        Returns:
            dict: Dictionary with provider names as keys and status info as values
        """
        current_time = time.time()
        
        status = {}
        for provider in self.providers:
            in_cooldown = current_time < self.cooldown_until[provider]
            status[provider] = {
                "failure_count": self.failure_counts[provider],
                "in_cooldown": in_cooldown,
                "cooldown_remaining": max(0, self.cooldown_until[provider] - current_time),
                "last_success": self.last_success[provider]
            }
        
        return status
