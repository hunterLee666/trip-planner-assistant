"""
智能旅行助手 - 缓存服务

提供Redis缓存和内存缓存支持
"""

import hashlib
import json
import pickle
from functools import wraps
from typing import Any, Callable, Optional, TypeVar, Union

import redis.asyncio as redis

from app.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class CacheService:
    """缓存服务
    
    提供统一的缓存接口，支持Redis和内存缓存
    """
    
    def __init__(self, redis_url: Optional[str] = None):
        self.settings = get_settings()
        self._redis: Optional[redis.Redis] = None
        self._memory_cache: dict = {}
        self._redis_url = redis_url or self.settings.redis_url
        self._enabled = self.settings.cache_enabled
    
    async def _get_redis(self) -> Optional[redis.Redis]:
        """获取Redis连接（懒加载）"""
        if not self._enabled:
            return None
        
        if self._redis is None and self._redis_url:
            try:
                self._redis = redis.from_url(
                    self._redis_url,
                    decode_responses=False,  # 保持二进制，用于pickle
                )
                # 测试连接
                await self._redis.ping()
                logger.info("redis_connection_established")
            except Exception as e:
                logger.warning("redis_connection_failed", error=str(e))
                self._redis = None
        
        return self._redis
    
    def _serialize(self, value: Any) -> bytes:
        """序列化值"""
        return pickle.dumps(value)
    
    def _deserialize(self, data: bytes) -> Any:
        """反序列化值"""
        return pickle.loads(data)
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        # 构建键数据
        key_data = {
            "prefix": prefix,
            "args": args,
            "kwargs": kwargs,
        }
        # 序列化为JSON并哈希
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        hash_key = hashlib.md5(key_str.encode()).hexdigest()[:16]
        return f"{prefix}:{hash_key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            缓存值，如果不存在返回None
        """
        if not self._enabled:
            return None
        
        try:
            # 先尝试Redis
            redis_client = await self._get_redis()
            if redis_client:
                data = await redis_client.get(key)
                if data:
                    return self._deserialize(data)
            
            # 回退到内存缓存
            if key in self._memory_cache:
                return self._memory_cache[key].get("value")
            
            return None
            
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """设置缓存值
        
        Args:
            key: 缓存键
            value: 缓存值
            ttl: 过期时间（秒），默认使用配置值
            
        Returns:
            是否成功
        """
        if not self._enabled:
            return False
        
        try:
            ttl = ttl or self.settings.cache_ttl_default
            data = self._serialize(value)
            
            # 尝试写入Redis
            redis_client = await self._get_redis()
            if redis_client:
                await redis_client.setex(key, ttl, data)
                return True
            
            # 回退到内存缓存
            import time
            self._memory_cache[key] = {
                "value": value,
                "expires": time.time() + ttl,
            }
            return True
            
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """删除缓存值
        
        Args:
            key: 缓存键
            
        Returns:
            是否成功
        """
        if not self._enabled:
            return False
        
        try:
            # 删除Redis
            redis_client = await self._get_redis()
            if redis_client:
                await redis_client.delete(key)
            
            # 删除内存缓存
            if key in self._memory_cache:
                del self._memory_cache[key]
            
            return True
            
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
            return False
    
    async def clear(self, prefix: Optional[str] = None) -> bool:
        """清除缓存
        
        Args:
            prefix: 如果指定，只清除匹配前缀的键
            
        Returns:
            是否成功
        """
        if not self._enabled:
            return False
        
        try:
            # 清除Redis
            redis_client = await self._get_redis()
            if redis_client:
                if prefix:
                    # 查找并删除匹配的键
                    pattern = f"{prefix}:*"
                    keys = await redis_client.keys(pattern)
                    if keys:
                        await redis_client.delete(*keys)
                else:
                    # 清除所有（谨慎使用）
                    await redis_client.flushdb()
            
            # 清除内存缓存
            if prefix:
                keys_to_delete = [
                    k for k in self._memory_cache.keys() 
                    if k.startswith(f"{prefix}:")
                ]
                for k in keys_to_delete:
                    del self._memory_cache[k]
            else:
                self._memory_cache.clear()
            
            return True
            
        except Exception as e:
            logger.warning("cache_clear_error", prefix=prefix, error=str(e))
            return False
    
    async def exists(self, key: str) -> bool:
        """检查键是否存在
        
        Args:
            key: 缓存键
            
        Returns:
            是否存在
        """
        if not self._enabled:
            return False
        
        try:
            redis_client = await self._get_redis()
            if redis_client:
                return await redis_client.exists(key) > 0
            
            return key in self._memory_cache
            
        except Exception as e:
            logger.warning("cache_exists_error", key=key, error=str(e))
            return False
    
    def cached(
        self, 
        prefix: str, 
        ttl: Optional[int] = None,
        key_builder: Optional[Callable] = None
    ):
        """缓存装饰器
        
        Args:
            prefix: 缓存键前缀
            ttl: 过期时间（秒）
            key_builder: 自定义键生成函数
            
        Returns:
            装饰器函数
            
        Example:
            >>> cache = CacheService()
            >>> @cache.cached("poi_search", ttl=7200)
            >>> async def search_poi(city: str, keyword: str):
            >>>     ...
        """
        def decorator(func: F) -> F:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # 生成缓存键
                if key_builder:
                    cache_key = key_builder(*args, **kwargs)
                else:
                    # 跳过self参数
                    cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
                    cache_key = self._generate_key(prefix, *cache_args, **kwargs)
                
                # 尝试获取缓存
                cached_value = await self.get(cache_key)
                if cached_value is not None:
                    logger.debug("cache_hit", key=cache_key, function=func.__name__)
                    return cached_value
                
                # 执行函数
                result = await func(*args, **kwargs)
                
                # 存入缓存
                await self.set(cache_key, result, ttl)
                logger.debug("cache_set", key=cache_key, function=func.__name__)
                
                return result
            
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # 同步函数不支持自动缓存，仅记录日志
                logger.warning(
                    "sync_function_not_cached",
                    function=func.__name__,
                    message="同步函数不支持自动缓存，请改为异步函数"
                )
                return func(*args, **kwargs)
            
            # 根据函数类型返回适当的包装器
            import asyncio
            if asyncio.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper
        
        return decorator
    
    async def close(self):
        """关闭缓存连接"""
        if self._redis:
            await self._redis.close()
            self._redis = None


# 全局缓存服务实例
_cache_service: Optional[CacheService] = None


def get_cache_service() -> CacheService:
    """获取缓存服务实例（单例）
    
    Returns:
        CacheService: 缓存服务实例
    """
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


def reset_cache_service():
    """重置缓存服务实例（用于测试）"""
    global _cache_service
    _cache_service = None
