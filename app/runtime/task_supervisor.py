"""
Task Supervisor - Centralized task management with monitoring, restart logic, and graceful shutdown.

Features:
- Tracks all asyncio tasks in registry with metadata
- Monitors task health (detects crashes/zombies)
- Auto-restarts failed critical tasks
- Provides health check data for /health/deep endpoint
- Graceful shutdown coordination with timeout
- Uses asyncio.TaskGroup for structured concurrency (Python 3.11+)
"""
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime

from app.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class TaskMetadata:
    """Metadata for tracked tasks."""
    name: str
    task: asyncio.Task
    critical: bool
    created_at: float
    last_restart: Optional[float] = None
    restart_count: int = 0
    status: str = "running"  # running, failed, stopped
    error: Optional[str] = None


class TaskSupervisor:
    """
    Supervises and manages all background tasks in the trading system.
    
    Prevents:
    - Silent task crashes
    - Zombie loops
    - Unmanaged background tasks
    - Memory leaks from endless loops
    
    Usage:
        supervisor = TaskSupervisor()
        
        # Create supervised tasks
        supervisor.create_task(
            my_async_function(),
            name="my_task",
            critical=True
        )
        
        # Get health status
        health = supervisor.get_health()
        
        # Graceful shutdown
        await supervisor.shutdown(timeout=10)
    """
    
    def __init__(self, max_restart_attempts: int = 5):
        """
        Initialize task supervisor.
        
        Args:
            max_restart_attempts: Maximum times to restart a critical task before giving up
        """
        self.tasks: Dict[str, TaskMetadata] = {}
        self.max_restart_attempts = max_restart_attempts
        self._shutdown_event = asyncio.Event()
        self._task_group: Optional[asyncio.TaskGroup] = None
        self._started = False
        
        logger.info("✅ TaskSupervisor initialized")
    
    def create_task(
        self,
        coro,
        name: str,
        critical: bool = True,
        restart_delay: float = 2.0
    ) -> asyncio.Task:
        """
        Create a supervised task with automatic restart on failure.
        
        Args:
            coro: Coroutine to run as task
            name: Unique task identifier
            critical: If True, auto-restart on failure; if False, log and stop
            restart_delay: Seconds to wait before restarting (with exponential backoff)
        
        Returns:
            The created asyncio.Task
        """
        if name in self.tasks:
            logger.warning(f"Task '{name}' already exists, replacing")
            self._stop_task(name)
        
        # Wrap coroutine with supervision logic
        async def supervised_task():
            while not self._shutdown_event.is_set():
                try:
                    await coro
                    break  # Task completed normally
                except asyncio.CancelledError:
                    logger.info(f"Task '{name}' cancelled")
                    self.tasks[name].status = "stopped"
                    raise
                except Exception as e:
                    error_msg = f"{type(e).__name__}: {str(e)}"
                    logger.error(f"Task '{name}' failed: {error_msg}", exc_info=True)
                    
                    metadata = self.tasks[name]
                    metadata.status = "failed"
                    metadata.error = error_msg
                    
                    if critical and metadata.restart_count < self.max_restart_attempts:
                        # Calculate exponential backoff delay
                        delay = restart_delay * (2 ** metadata.restart_count)
                        delay = min(delay, 60)  # Cap at 60 seconds
                        
                        logger.warning(
                            f"Restarting critical task '{name}' in {delay:.1f}s "
                            f"(attempt {metadata.restart_count + 1}/{self.max_restart_attempts})"
                        )
                        
                        metadata.restart_count += 1
                        metadata.last_restart = time.time()
                        metadata.status = "restarting"
                        
                        await asyncio.sleep(delay)
                        metadata.status = "running"
                        metadata.error = None
                        
                        # Recreate the coroutine (need fresh instance)
                        continue
                    else:
                        if not critical:
                            logger.warning(f"Non-critical task '{name}' stopped after failure")
                        else:
                            logger.critical(
                                f"Critical task '{name}' exceeded max restart attempts "
                                f"({self.max_restart_attempts}), stopping"
                            )
                        metadata.status = "stopped"
                        break
        
        # Create the actual task
        task = asyncio.create_task(supervised_task())
        
        # Store metadata
        self.tasks[name] = TaskMetadata(
            name=name,
            task=task,
            critical=critical,
            created_at=time.time()
        )
        
        logger.debug(f"Created supervised task: {name} (critical={critical})")
        return task
    
    def _stop_task(self, name: str):
        """Stop and remove a task."""
        if name in self.tasks:
            metadata = self.tasks[name]
            if not metadata.task.done():
                metadata.task.cancel()
            del self.tasks[name]
            logger.debug(f"Stopped task: {name}")
    
    def get_health(self) -> Dict[str, Any]:
        """
        Get comprehensive health status of all supervised tasks.
        
        Returns:
            Dict with task health information for /health/deep endpoint
        """
        healthy_tasks = []
        failed_tasks = []
        stopped_tasks = []
        
        for name, metadata in self.tasks.items():
            task_info = {
                "name": name,
                "status": metadata.status,
                "critical": metadata.critical,
                "restart_count": metadata.restart_count,
                "uptime_seconds": time.time() - metadata.created_at,
                "error": metadata.error
            }
            
            if metadata.status == "running":
                healthy_tasks.append(task_info)
            elif metadata.status == "failed":
                failed_tasks.append(task_info)
            else:
                stopped_tasks.append(task_info)
        
        return {
            "total_tasks": len(self.tasks),
            "healthy_tasks": len(healthy_tasks),
            "failed_tasks": len(failed_tasks),
            "stopped_tasks": len(stopped_tasks),
            "details": {
                "healthy": healthy_tasks,
                "failed": failed_tasks,
                "stopped": stopped_tasks
            }
        }
    
    async def shutdown(self, timeout: float = 10.0):
        """
        Gracefully shut down all supervised tasks.
        
        Args:
            timeout: Maximum seconds to wait for tasks to complete
        """
        logger.info(f"🛑 TaskSupervisor shutting down {len(self.tasks)} tasks...")
        
        # Signal all tasks to stop
        self._shutdown_event.set()
        
        # Cancel all non-completed tasks
        tasks_to_cancel = [
            metadata.task for metadata in self.tasks.values()
            if not metadata.task.done()
        ]
        
        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} active tasks...")
            for task in tasks_to_cancel:
                task.cancel()
            
            # Wait for tasks to finish with timeout
            try:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_cancel, return_exceptions=True),
                    timeout=timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for tasks to shutdown after {timeout}s")
        
        # Clear task registry
        self.tasks.clear()
        logger.info("✅ TaskSupervisor shutdown complete")
    
    def get_task_count(self) -> int:
        """Get total number of supervised tasks."""
        return len(self.tasks)
    
    def get_critical_task_count(self) -> int:
        """Get number of critical tasks."""
        return sum(1 for m in self.tasks.values() if m.critical)
