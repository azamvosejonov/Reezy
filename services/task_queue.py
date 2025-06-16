import logging
from typing import Any, Dict, Optional, TypeVar, Generic, Type, List
from datetime import datetime, timedelta
from enum import Enum
import json

from celery.result import AsyncResult
from pydantic import BaseModel, Field

from core.redis import redis_client
from core.celery import celery_app

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

class TaskStatus(str, Enum):
    """Status of a background task."""
    PENDING = 'PENDING'
    STARTED = 'STARTED'
    RETRY = 'RETRY'
    FAILURE = 'FAILURE'
    SUCCESS = 'SUCCESS'
    REVOKED = 'REVOKED'

class TaskResult(BaseModel):
    """Represents the result of a background task."""
    task_id: str
    status: TaskStatus
    result: Optional[Any] = None
    error: Optional[str] = None
    date_done: Optional[datetime] = None
    traceback: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
        use_enum_values = True

class TaskQueueService:
    """
    Service for managing background tasks using Celery and Redis.
    """
    
    def __init__(self, redis_client=redis_client):
        self.redis = redis_client
        self.celery = celery_app
    
    async def submit_task(
        self, 
        task_name: str, 
        args: tuple = None, 
        kwargs: dict = None,
        expires: int = 3600,
        countdown: int = None,
        **options
    ) -> str:
        """
        Submit a task to the Celery worker pool.
        
        Args:
            task_name: Name of the Celery task to execute
            args: Positional arguments to pass to the task
            kwargs: Keyword arguments to pass to the task
            expires: Time in seconds after which the task expires
            countdown: Time in seconds to wait before executing the task
            **options: Additional options to pass to Celery
            
        Returns:
            str: Task ID
        """
        try:
            # Submit the task to Celery
            result = self.celery.send_task(
                task_name,
                args=args or (), 
                kwargs=kwargs or {},
                countdown=countdown,
                expires=expires,
                **options
            )
            
            # Store initial task status in Redis
            task_result = TaskResult(
                task_id=result.id,
                status=TaskStatus.PENDING
            )
            await self._store_task_result(task_result)
            
            return result.id
            
        except Exception as e:
            logger.error(f"Error submitting task {task_name}: {str(e)}")
            raise
    
    async def get_task_result(self, task_id: str) -> Optional[TaskResult]:
        """
        Get the result of a task by its ID.
        
        Args:
            task_id: ID of the task to retrieve
            
        Returns:
            Optional[TaskResult]: The task result, or None if not found
        """
        try:
            # First try to get from Redis
            cached_result = await self._get_cached_task_result(task_id)
            if cached_result:
                return cached_result
            
            # If not in Redis, check Celery
            result = AsyncResult(task_id, app=self.celery)
            
            if not result.id:
                return None
            
            # Convert Celery result to our format
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus(result.status),
                result=result.result if result.ready() else None,
                error=str(result.result) if result.failed() else None,
                date_done=result.date_done,
                traceback=result.traceback
            )
            
            # Cache the result
            await self._store_task_result(task_result)
            
            return task_result
            
        except Exception as e:
            logger.error(f"Error getting task result {task_id}: {str(e)}")
            return None
    
    async def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """
        Revoke a task.
        
        Args:
            task_id: ID of the task to revoke
            terminate: Whether to terminate the task if it's currently running
            
        Returns:
            bool: True if the task was successfully revoked
        """
        try:
            # Revoke the task in Celery
            self.celery.control.revoke(task_id, terminate=terminate)
            
            # Update status in Redis
            task_result = TaskResult(
                task_id=task_id,
                status=TaskStatus.REVOKED,
                error="Task was revoked"
            )
            await self._store_task_result(task_result)
            
            return True
            
        except Exception as e:
            logger.error(f"Error revoking task {task_id}: {str(e)}")
            return False
    
    async def wait_for_task(
        self, 
        task_id: str, 
        timeout: int = 30,
        poll_interval: float = 0.5
    ) -> Optional[TaskResult]:
        """
        Wait for a task to complete.
        
        Args:
            task_id: ID of the task to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time to wait between polls in seconds
            
        Returns:
            Optional[TaskResult]: The task result, or None if timeout
        """
        import asyncio
        
        start_time = datetime.now()
        
        while True:
            # Check if timeout has been reached
            elapsed = (datetime.now() - start_time).total_seconds()
            if elapsed > timeout:
                return None
            
            # Get the current task status
            task_result = await self.get_task_result(task_id)
            
            if not task_result:
                return None
                
            # Return if task is done
            if task_result.status in (TaskStatus.SUCCESS, TaskStatus.FAILURE, TaskStatus.REVOKED):
                return task_result
            
            # Wait before polling again
            await asyncio.sleep(poll_interval)
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        Get the status of a task.
        
        Args:
            task_id: ID of the task
            
        Returns:
            Optional[TaskStatus]: The task status, or None if not found
        """
        task_result = await self.get_task_result(task_id)
        return task_result.status if task_result else None
    
    async def get_task_results(self, task_ids: List[str]) -> Dict[str, TaskResult]:
        """
        Get results for multiple tasks.
        
        Args:
            task_ids: List of task IDs
            
        Returns:
            Dict mapping task IDs to their results
        """
        return {task_id: await self.get_task_result(task_id) for task_id in task_ids}
    
    async def _store_task_result(self, task_result: TaskResult, ttl: int = 86400):
        """Store a task result in Redis."""
        try:
            await self.redis.set(
                f"task:{task_result.task_id}",
                task_result.json(),
                ex=ttl
            )
        except Exception as e:
            logger.error(f"Error storing task result in Redis: {str(e)}")
    
    async def _get_cached_task_result(self, task_id: str) -> Optional[TaskResult]:
        """Get a task result from Redis cache."""
        try:
            cached = await self.redis.get(f"task:{task_id}")
            if cached:
                return TaskResult.parse_raw(cached)
            return None
        except Exception as e:
            logger.error(f"Error getting cached task result: {str(e)}")
            return None

# Global instance
task_queue = TaskQueueService()
