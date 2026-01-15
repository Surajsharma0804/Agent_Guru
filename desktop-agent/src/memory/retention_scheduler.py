"""
Retention Policy Scheduler for GURU Memory System

Implements automatic periodic execution of retention policies:
- Scheduled conversation purging (90 days)
- Periodic cleanup of expired vault items
- Configurable retention policy enforcement
- Background thread execution
- Comprehensive audit logging

Features:
- Non-blocking background execution
- Configurable schedule intervals
- Graceful shutdown handling
- Error recovery and retry logic
- Performance monitoring

Validates Requirements: 10.5
"""

import logging
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RetentionScheduleConfig:
    """Configuration for retention policy scheduling."""
    conversation_purge_interval_hours: int = 24  # Run daily
    conversation_retention_days: int = 90
    vault_cleanup_interval_hours: int = 12  # Run twice daily
    enabled: bool = True


class RetentionScheduler:
    """
    Automatic retention policy scheduler for GURU memory system.
    
    Runs retention policies on a configurable schedule in a background thread.
    Ensures old data is automatically purged according to retention policies.
    """
    
    def __init__(self, memory_service, config: Optional[RetentionScheduleConfig] = None):
        """
        Initialize retention scheduler.
        
        Args:
            memory_service: MemorySubsystemController instance
            config: Optional configuration (uses defaults if None)
        """
        self.memory_service = memory_service
        self.config = config or RetentionScheduleConfig()
        
        self._shutdown = False
        self._scheduler_thread: Optional[threading.Thread] = None
        self._last_conversation_purge: Optional[datetime] = None
        self._last_vault_cleanup: Optional[datetime] = None
        
        self._lock = threading.RLock()
    
    def start(self) -> None:
        """Start the retention scheduler in a background thread."""
        if not self.config.enabled:
            logger.info("Retention scheduler is disabled")
            return
        
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Retention scheduler is already running")
            return
        
        self._shutdown = False
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            name="RetentionScheduler",
            daemon=True
        )
        self._scheduler_thread.start()
        
        logger.info("Retention scheduler started")
    
    def stop(self) -> None:
        """Stop the retention scheduler and wait for thread to finish."""
        if not self._scheduler_thread or not self._scheduler_thread.is_alive():
            return
        
        logger.info("Stopping retention scheduler...")
        self._shutdown = True
        
        # Wait for thread to finish (with timeout)
        self._scheduler_thread.join(timeout=10.0)
        
        if self._scheduler_thread.is_alive():
            logger.warning("Retention scheduler thread did not stop gracefully")
        else:
            logger.info("Retention scheduler stopped")
    
    def _scheduler_loop(self) -> None:
        """Main scheduler loop that runs in background thread."""
        logger.info("Retention scheduler loop started")
        
        while not self._shutdown:
            try:
                # Check if conversation purge is due
                if self._should_run_conversation_purge():
                    self._run_conversation_purge()
                
                # Check if vault cleanup is due
                if self._should_run_vault_cleanup():
                    self._run_vault_cleanup()
                
                # Sleep for 1 hour before next check
                for _ in range(3600):  # Sleep in 1-second intervals for responsive shutdown
                    if self._shutdown:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in retention scheduler loop: {e}")
                # Sleep for 5 minutes before retrying
                for _ in range(300):
                    if self._shutdown:
                        break
                    time.sleep(1)
        
        logger.info("Retention scheduler loop exited")
    
    def _should_run_conversation_purge(self) -> bool:
        """Check if conversation purge should run."""
        if self._last_conversation_purge is None:
            return True
        
        hours_since_last = (datetime.now(timezone.utc) - self._last_conversation_purge).total_seconds() / 3600
        return hours_since_last >= self.config.conversation_purge_interval_hours
    
    def _should_run_vault_cleanup(self) -> bool:
        """Check if vault cleanup should run."""
        if self._last_vault_cleanup is None:
            return True
        
        hours_since_last = (datetime.now(timezone.utc) - self._last_vault_cleanup).total_seconds() / 3600
        return hours_since_last >= self.config.vault_cleanup_interval_hours
    
    def _run_conversation_purge(self) -> None:
        """Run conversation purge operation."""
        try:
            logger.info(f"Running conversation purge (retention: {self.config.conversation_retention_days} days)")
            
            start_time = time.time()
            deleted_count = self.memory_service.purge_old_conversations(
                days=self.config.conversation_retention_days
            )
            execution_time = time.time() - start_time
            
            with self._lock:
                self._last_conversation_purge = datetime.now(timezone.utc)
            
            logger.info(f"Conversation purge completed: {deleted_count} conversations deleted in {execution_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Conversation purge failed: {e}")
    
    def _run_vault_cleanup(self) -> None:
        """Run vault cleanup operation (expired items)."""
        try:
            logger.info("Running vault cleanup (expired items)")
            
            start_time = time.time()
            
            # Get vault manager and clean up expired items
            if hasattr(self.memory_service, 'vault_manager'):
                deleted_count = self.memory_service.vault_manager.cleanup_expired()
                execution_time = time.time() - start_time
                
                with self._lock:
                    self._last_vault_cleanup = datetime.now(timezone.utc)
                
                logger.info(f"Vault cleanup completed: {deleted_count} expired items deleted in {execution_time:.2f}s")
            else:
                logger.warning("Vault manager not available for cleanup")
                
        except Exception as e:
            logger.error(f"Vault cleanup failed: {e}")
    
    def force_conversation_purge(self) -> int:
        """
        Force immediate conversation purge (manual trigger).
        
        Returns:
            int: Number of conversations deleted
        """
        logger.info("Forcing immediate conversation purge")
        
        try:
            deleted_count = self.memory_service.purge_old_conversations(
                days=self.config.conversation_retention_days
            )
            
            with self._lock:
                self._last_conversation_purge = datetime.now(timezone.utc)
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"Forced conversation purge failed: {e}")
            return 0
    
    def force_vault_cleanup(self) -> int:
        """
        Force immediate vault cleanup (manual trigger).
        
        Returns:
            int: Number of vault items deleted
        """
        logger.info("Forcing immediate vault cleanup")
        
        try:
            if hasattr(self.memory_service, 'vault_manager'):
                deleted_count = self.memory_service.vault_manager.cleanup_expired()
                
                with self._lock:
                    self._last_vault_cleanup = datetime.now(timezone.utc)
                
                return deleted_count
            else:
                logger.warning("Vault manager not available for cleanup")
                return 0
                
        except Exception as e:
            logger.error(f"Forced vault cleanup failed: {e}")
            return 0
    
    def get_status(self) -> Dict[str, Any]:
        """Get scheduler status and statistics."""
        with self._lock:
            return {
                'enabled': self.config.enabled,
                'running': self._scheduler_thread is not None and self._scheduler_thread.is_alive(),
                'last_conversation_purge': self._last_conversation_purge.isoformat() if self._last_conversation_purge else None,
                'last_vault_cleanup': self._last_vault_cleanup.isoformat() if self._last_vault_cleanup else None,
                'conversation_purge_interval_hours': self.config.conversation_purge_interval_hours,
                'conversation_retention_days': self.config.conversation_retention_days,
                'vault_cleanup_interval_hours': self.config.vault_cleanup_interval_hours
            }
    
    def update_config(self, config: RetentionScheduleConfig) -> None:
        """Update scheduler configuration."""
        with self._lock:
            self.config = config
            logger.info(f"Retention scheduler configuration updated: {config}")
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.stop()
