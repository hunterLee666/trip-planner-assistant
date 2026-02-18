"""
智能旅行助手 - 核心异常定义

定义所有业务异常和错误代码
"""

from typing import Any, Dict, Optional


class TripPlannerException(Exception):
    """基础业务异常
    
    所有业务异常的基类，提供统一的错误处理接口
    """
    
    error_code: str = "INTERNAL_ERROR"
    status_code: int = 500
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None, 
        details: Optional[Dict[str, Any]] = None,
        status_code: Optional[int] = None
    ):
        self.message = message
        self.error_code = error_code or self.error_code
        self.details = details or {}
        self.status_code = status_code or self.status_code
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式，用于API响应"""
        return {
            "success": False,
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


# ============ 客户端错误 (4xx) ============

class ValidationError(TripPlannerException):
    """参数验证错误
    
    请求参数不合法或缺失
    """
    error_code = "VALIDATION_ERROR"
    status_code = 400


class AuthenticationError(TripPlannerException):
    """认证错误
    
    用户未登录或Token无效
    """
    error_code = "AUTHENTICATION_ERROR"
    status_code = 401


class AuthorizationError(TripPlannerException):
    """授权错误
    
    用户无权限执行此操作
    """
    error_code = "AUTHORIZATION_ERROR"
    status_code = 403


class NotFoundError(TripPlannerException):
    """资源不存在
    
    请求的资源未找到
    """
    error_code = "NOT_FOUND"
    status_code = 404


class ConflictError(TripPlannerException):
    """资源冲突
    
    资源已存在或状态冲突
    """
    error_code = "CONFLICT_ERROR"
    status_code = 409


class RateLimitError(TripPlannerException):
    """请求频率限制
    
    请求过于频繁，触发限流
    """
    error_code = "RATE_LIMIT_EXCEEDED"
    status_code = 429


# ============ 服务端错误 (5xx) ============

class AmapServiceError(TripPlannerException):
    """高德地图服务错误
    
    调用高德地图API失败
    """
    error_code = "AMAP_SERVICE_ERROR"
    status_code = 502


class LLMServiceError(TripPlannerException):
    """LLM服务错误
    
    调用大语言模型服务失败
    """
    error_code = "LLM_SERVICE_ERROR"
    status_code = 502


class CacheError(TripPlannerException):
    """缓存服务错误
    
    Redis缓存操作失败
    """
    error_code = "CACHE_ERROR"
    status_code = 503


class DatabaseError(TripPlannerException):
    """数据库错误
    
    数据库操作失败
    """
    error_code = "DATABASE_ERROR"
    status_code = 503


class TripPlanningError(TripPlannerException):
    """旅行规划错误
    
    行程生成过程失败
    """
    error_code = "TRIP_PLANNING_ERROR"
    status_code = 500


class ExternalServiceError(TripPlannerException):
    """外部服务错误
    
    调用第三方服务失败
    """
    error_code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502


# ============ 降级策略异常 ============

class FallbackActivatedError(TripPlannerException):
    """降级策略激活
    
    主服务失败，已启用降级方案
    """
    error_code = "FALLBACK_ACTIVATED"
    status_code = 200  # 降级后仍返回成功，但标记为降级
    
    def __init__(self, message: str, fallback_data: Any, **kwargs):
        super().__init__(message, **kwargs)
        self.fallback_data = fallback_data
    
    def to_dict(self) -> Dict[str, Any]:
        result = super().to_dict()
        result["is_fallback"] = True
        result["fallback_data"] = self.fallback_data
        return result


class RetryExhaustedError(TripPlannerException):
    """重试次数耗尽
    
    多次重试后仍然失败
    """
    error_code = "RETRY_EXHAUSTED"
    status_code = 503


# ============ 错误代码映射表 ============

ERROR_CODE_MAP = {
    # 4xx 客户端错误
    "VALIDATION_ERROR": (ValidationError, 400),
    "AUTHENTICATION_ERROR": (AuthenticationError, 401),
    "AUTHORIZATION_ERROR": (AuthorizationError, 403),
    "NOT_FOUND": (NotFoundError, 404),
    "CONFLICT_ERROR": (ConflictError, 409),
    "RATE_LIMIT_EXCEEDED": (RateLimitError, 429),
    
    # 5xx 服务端错误
    "INTERNAL_ERROR": (TripPlannerException, 500),
    "TRIP_PLANNING_ERROR": (TripPlanningError, 500),
    "AMAP_SERVICE_ERROR": (AmapServiceError, 502),
    "LLM_SERVICE_ERROR": (LLMServiceError, 502),
    "EXTERNAL_SERVICE_ERROR": (ExternalServiceError, 502),
    "CACHE_ERROR": (CacheError, 503),
    "DATABASE_ERROR": (DatabaseError, 503),
    "RETRY_EXHAUSTED": (RetryExhaustedError, 503),
}


def get_exception_class(error_code: str) -> type:
    """根据错误代码获取异常类
    
    Args:
        error_code: 错误代码字符串
        
    Returns:
        对应的异常类
    """
    return ERROR_CODE_MAP.get(error_code, (TripPlannerException, 500))[0]
