from fastapi import HTTPException
from starlette import status

import redis
from typing import Optional, Any, Dict, Union, List, Callable
import json
import logging
from functools import wraps
from datetime import timedelta
import pickle

logger = logging.getLogger(__name__)

class RedisClient:
    """
    A Redis client wrapper that provides a simplified interface for common Redis operations
    with connection pooling and error handling.
    """
    _instance = None
    
    def __new__(cls, host: str = 'localhost', port: int = 6379, db: int = 0, 
                password: Optional[str] = None, **kwargs):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
            cls._instance._initialize(host, port, db, password, **kwargs)
        return cls._instance
    
    def _initialize(self, host: str, port: int, db: int, 
                   password: Optional[str], **kwargs):
        """Initialize the Redis connection pool."""
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            max_connections=20,  # Adjust based on your needs
            **kwargs
        )
    
    @property
    def connection(self) -> redis.Redis:
        """Get a Redis connection from the pool."""
        return redis.Redis(connection_pool=self.pool, decode_responses=False)
    
    # Basic Key Operations
    def set(self, key: str, value: Any, ex: Optional[int] = None, 
            px: Optional[int] = None, nx: bool = False, xx: bool = False) -> bool:
        """Set the string value of a key."""
        with self.connection as r:
            try:
                if not isinstance(value, (str, int, float, bool, bytes)):
                    value = pickle.dumps(value)
                return r.set(key, value, ex=ex, px=px, nx=nx, xx=xx)
            except Exception as e:
                logger.error(f"Redis set error: {str(e)}")
                return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get the value of a key."""
        with self.connection as r:
            try:
                value = r.get(key)
                if value is None:
                    return default
                try:
                    return pickle.loads(value)
                except (pickle.PickleError, TypeError):
                    return value.decode('utf-8')
            except Exception as e:
                logger.error(f"Redis get error: {str(e)}")
                return default
    
    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        with self.connection as r:
            try:
                return r.delete(*keys)
            except Exception as e:
                logger.error(f"Redis delete error: {str(e)}")
                return 0
    
    def exists(self, key: str) -> bool:
        """Check if a key exists."""
        with self.connection as r:
            try:
                return bool(r.exists(key))
            except Exception as e:
                logger.error(f"Redis exists error: {str(e)}")
                return False
    
    def expire(self, key: str, time: int) -> bool:
        """Set a key's time to live in seconds."""
        with self.connection as r:
            try:
                return bool(r.expire(key, time))
            except Exception as e:
                logger.error(f"Redis expire error: {str(e)}")
                return False
    
    # Hash Operations
    def hset(self, name: str, key: str, value: Any) -> int:
        """Set the string value of a hash field."""
        with self.connection as r:
            try:
                if not isinstance(value, (str, int, float, bool, bytes)):
                    value = pickle.dumps(value)
                return r.hset(name, key, value)
            except Exception as e:
                logger.error(f"Redis hset error: {str(e)}")
                return 0
    
    def hget(self, name: str, key: str, default: Any = None) -> Any:
        """Get the value of a hash field."""
        with self.connection as r:
            try:
                value = r.hget(name, key)
                if value is None:
                    return default
                try:
                    return pickle.loads(value)
                except (pickle.PickleError, TypeError):
                    return value.decode('utf-8')
            except Exception as e:
                logger.error(f"Redis hget error: {str(e)}")
                return default
    
    def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all fields and values in a hash."""
        with self.connection as r:
            try:
                result = {}
                for k, v in r.hgetall(name).items():
                    try:
                        result[k.decode('utf-8')] = pickle.loads(v)
                    except (pickle.PickleError, TypeError):
                        result[k.decode('utf-8')] = v.decode('utf-8')
                return result
            except Exception as e:
                logger.error(f"Redis hgetall error: {str(e)}")
                return {}
    
    # List Operations
    def lpush(self, name: str, *values: Any) -> int:
        """Prepend one or multiple values to a list."""
        with self.connection as r:
            try:
                serialized = [
                    pickle.dumps(v) if not isinstance(v, (str, int, float, bool, bytes)) 
                    else v for v in values
                ]
                return r.lpush(name, *serialized)
            except Exception as e:
                logger.error(f"Redis lpush error: {str(e)}")
                return 0
    
    def rpush(self, name: str, *values: Any) -> int:
        """Append one or multiple values to a list."""
        with self.connection as r:
            try:
                serialized = [
                    pickle.dumps(v) if not isinstance(v, (str, int, float, bool, bytes)) 
                    else v for v in values
                ]
                return r.rpush(name, *serialized)
            except Exception as e:
                logger.error(f"Redis rpush error: {str(e)}")
                return 0
    
    def lrange(self, name: str, start: int, end: int) -> List[Any]:
        """Get a range of elements from a list."""
        with self.connection as r:
            try:
                result = []
                for item in r.lrange(name, start, end):
                    try:
                        result.append(pickle.loads(item))
                    except (pickle.PickleError, TypeError):
                        result.append(item.decode('utf-8'))
                return result
            except Exception as e:
                logger.error(f"Redis lrange error: {str(e)}")
                return []
    
    # Pub/Sub
    def publish(self, channel: str, message: Any) -> int:
        """Post a message to a channel."""
        with self.connection as r:
            try:
                if not isinstance(message, (str, int, float, bool, bytes)):
                    message = pickle.dumps(message)
                return r.publish(channel, message)
            except Exception as e:
                logger.error(f"Redis publish error: {str(e)}")
                return 0
    
    def get_pubsub(self):
        """Return a pubsub object."""
        return self.connection.pubsub()
    
    # Utility Methods
    def cache_result(self, key: str, ttl: int = 300, prefix: str = "cache:"):
        """
        Decorator to cache function results in Redis.
        
        Args:
            key: Cache key (can include format placeholders for function args)
            ttl: Time to live in seconds
            prefix: Prefix for cache keys
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{prefix}{key}"
                if args or kwargs:
                    cache_key = cache_key.format(*args, **{k: v for k, v in kwargs.items() if k != 'self'})
                
                # Try to get from cache
                cached = self.get(cache_key)
                if cached is not None:
                    return cached
                
                # Call the function
                result = func(*args, **kwargs)
                
                # Cache the result
                if result is not None:
                    self.set(cache_key, result, ex=ttl)
                
                return result
            return wrapper
        return decorator
    
    def rate_limit(self, key: str, limit: int, period: int = 60):
        """
        Decorator to rate limit a function.
        
        Args:
            key: Rate limit key (can include format placeholders for function args)
            limit: Maximum number of allowed requests in the period
            period: Time period in seconds
        """
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Generate rate limit key
                rate_key = f"rate_limit:{key}"
                if args or kwargs:
                    rate_key = rate_key.format(*args, **{k: v for k, v in kwargs.items() if k != 'self'})
                
                # Get current count
                with self.connection as r:
                    current = r.incr(rate_key)
                    if current == 1:  # First request, set expiration
                        r.expire(rate_key, period)
                
                # Check if rate limit exceeded
                if current > limit:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Rate limit exceeded"
                    )
                
                return func(*args, **kwargs)
            return wrapper
        return decorator

# Initialize Redis client with default settings
redis_client = RedisClient(
    host='localhost',
    port=6379,
    db=0,
    password=None
)
