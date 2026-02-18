"""
缓存服务单元测试
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.cache_service import CacheService, get_cache_service


class TestCacheService:
    """缓存服务测试"""
    
    @pytest.fixture
    def cache_service(self):
        """创建缓存服务实例"""
        return CacheService(redis_url="redis://localhost:6379/0")
    
    @pytest.mark.asyncio
    async def test_generate_key(self, cache_service):
        """测试键生成"""
        key = cache_service._generate_key("test", "arg1", "arg2", kwarg1="value1")
        
        assert key.startswith("test:")
        assert len(key) > 5
    
    @pytest.mark.asyncio
    async def test_get_cache_miss(self, cache_service):
        """测试缓存未命中"""
        with patch.object(cache_service, '_get_redis', return_value=None):
            result = await cache_service.get("nonexistent_key")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, cache_service):
        """测试设置和获取缓存"""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        
        with patch.object(cache_service, '_get_redis', return_value=mock_redis):
            # 设置缓存
            await cache_service.set("test_key", {"data": "value"}, ttl=3600)
            
            # 验证redis被调用
            mock_redis.setex.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete(self, cache_service):
        """测试删除缓存"""
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        
        with patch.object(cache_service, '_get_redis', return_value=mock_redis):
            result = await cache_service.delete("test_key")
            
            assert result is True
            mock_redis.delete.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_cached_decorator(self, cache_service):
        """测试缓存装饰器"""
        
        @cache_service.cached("test_prefix", ttl=3600)
        async def expensive_function(arg1, arg2):
            return {"result": f"{arg1}_{arg2}"}
        
        # 第一次调用
        with patch.object(cache_service, 'get', return_value=None):
            with patch.object(cache_service, 'set', return_value=True):
                result = await expensive_function("a", "b")
                assert result == {"result": "a_b"}
    
    def test_singleton(self):
        """测试单例模式"""
        from app.services.cache_service import _cache_service
        
        # 重置单例
        import app.services.cache_service as cache_module
        cache_module._cache_service = None
        
        # 获取实例
        service1 = get_cache_service()
        service2 = get_cache_service()
        
        assert service1 is service2
