"""
API集成测试
"""

import pytest
from httpx import AsyncClient


class TestHealthEndpoint:
    """健康检查端点测试"""
    
    @pytest.mark.asyncio
    async def test_health_check(self, client: AsyncClient):
        """测试健康检查端点"""
        response = await client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data


class TestTripPlanningEndpoint:
    """旅行规划端点测试"""
    
    @pytest.mark.asyncio
    async def test_plan_trip_validation_error(self, client: AsyncClient):
        """测试参数验证错误"""
        invalid_request = {
            "city": "北京",
            "start_date": "invalid-date",
            "end_date": "2025-06-03",
            "travel_days": 3,
            "transportation": "公共交通",
            "accommodation": "酒店"
        }
        
        response = await client.post("/api/trip/plan", json=invalid_request)
        
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_plan_trip_days_validation(self, client: AsyncClient):
        """测试天数验证"""
        invalid_request = {
            "city": "北京",
            "start_date": "2025-06-01",
            "end_date": "2025-06-03",
            "travel_days": 31,  # 超过最大值
            "transportation": "公共交通",
            "accommodation": "酒店"
        }
        
        response = await client.post("/api/trip/plan", json=invalid_request)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="需要真实的LLM服务")
    async def test_plan_trip_success(
        self, 
        client: AsyncClient, 
        sample_trip_request
    ):
        """测试成功生成旅行计划"""
        response = await client.post("/api/trip/plan", json=sample_trip_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["city"] == "北京"


class TestAuthEndpoint:
    """认证端点测试"""
    
    @pytest.mark.asyncio
    async def test_login_endpoint(self, client: AsyncClient):
        """测试登录端点"""
        login_data = {
            "username": "test@example.com",
            "password": "testpassword"
        }
        
        response = await client.post("/api/auth/login", data=login_data)
        
        # 由于未实现用户验证，应该返回错误或模拟成功
        assert response.status_code in [200, 401]
    
    @pytest.mark.asyncio
    async def test_register_endpoint(self, client: AsyncClient):
        """测试注册端点"""
        register_data = {
            "email": "newuser@example.com",
            "password": "password123",
            "full_name": "Test User"
        }
        
        response = await client.post("/api/auth/register", json=register_data)
        
        # 应该返回成功或冲突
        assert response.status_code in [200, 201, 409]
