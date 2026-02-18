"""
智能旅行助手 - 结构化日志配置

配置JSON格式的结构化日志，支持追踪和观测
"""

import logging
import sys
from typing import Any, Dict, Optional

import structlog
from structlog.types import EventDict, WrappedLogger


def configure_logging(log_level: str = "INFO", json_format: bool = True) -> None:
    """配置结构化日志
    
    Args:
        log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: 是否输出JSON格式
    """
    # 配置标准库日志
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )
    
    # 抑制第三方库的冗余日志
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # 配置structlog处理器
    processors = [
        # 过滤低级别日志
        structlog.stdlib.filter_by_level,
        # 添加logger名称
        structlog.stdlib.add_logger_name,
        # 添加日志级别
        structlog.stdlib.add_log_level,
        # 格式化位置参数
        structlog.stdlib.PositionalArgumentsFormatter(),
        # 添加时间戳
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # 添加堆栈信息
        structlog.processors.StackInfoRenderer(),
        # 格式化异常信息
        structlog.processors.format_exc_info,
        # 解码unicode
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        # JSON格式输出
        processors.append(structlog.processors.JSONRenderer())
    else:
        # 开发友好的控制台格式
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """获取结构化logger
    
    Args:
        name: logger名称，通常为模块名
        
    Returns:
        配置好的structlog logger
        
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_login", user_id="123", ip="192.168.1.1")
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """绑定上下文变量到当前日志上下文
    
    这些变量会自动附加到后续的所有日志记录中
    
    Args:
        **kwargs: 要绑定的键值对
        
    Example:
        >>> bind_context(trace_id="abc123", user_id="456")
        >>> logger.info("request_started")  # 自动包含trace_id和user_id
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """清除当前日志上下文"""
    structlog.contextvars.clear_contextvars()


def unbind_context(*keys: str) -> None:
    """从上下文中移除指定键
    
    Args:
        *keys: 要移除的键名
    """
    structlog.contextvars.unbind_contextvars(*keys)


class TraceIdMiddleware:
    """追踪ID中间件
    
    为每个请求生成唯一trace_id，并绑定到日志上下文
    """
    
    def __init__(self, header_name: str = "X-Trace-Id"):
        self.header_name = header_name
    
    async def __call__(self, request, call_next):
        import uuid
        
        # 尝试从请求头获取trace_id，或生成新的
        trace_id = request.headers.get(self.header_name.lower()) or str(uuid.uuid4())
        
        # 清除旧的上下文并绑定新上下文
        clear_context()
        bind_context(
            trace_id=trace_id,
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None,
        )
        
        # 执行请求
        response = await call_next(request)
        
        # 将trace_id添加到响应头
        response.headers[self.header_name] = trace_id
        
        return response


class LoggingMiddleware:
    """请求日志中间件
    
    记录每个请求的详细信息
    """
    
    def __init__(self, exclude_paths: Optional[list] = None):
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json"]
    
    async def __call__(self, request, call_next):
        import time
        
        # 跳过健康检查等路径
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        logger = get_logger("http")
        start_time = time.time()
        
        # 记录请求开始
        logger.info(
            "http_request_started",
            path=request.url.path,
            method=request.method,
            query_params=str(request.query_params),
        )
        
        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录请求完成
            logger.info(
                "http_request_completed",
                path=request.url.path,
                method=request.method,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # 记录请求失败
            logger.error(
                "http_request_failed",
                path=request.url.path,
                method=request.method,
                error=str(e),
                duration_ms=round(duration_ms, 2),
            )
            raise


def log_execution_time(logger_name: Optional[str] = None):
    """执行时间日志装饰器
    
    记录函数执行时间
    
    Args:
        logger_name: logger名称，默认为函数所在模块
        
    Example:
        >>> @log_execution_time()
        >>> async def search_poi(self, city: str):
        >>>     ...
    """
    import functools
    import time
    from typing import Callable, TypeVar
    
    F = TypeVar("F", bound=Callable[..., Any])
    
    def decorator(func: F) -> F:
        logger = get_logger(logger_name or func.__module__)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "function_executed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    "function_failed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                    status="error",
                )
                raise
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    "function_executed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    status="success",
                )
                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    "function_failed",
                    function=func.__name__,
                    duration_ms=round(duration_ms, 2),
                    error=str(e),
                    status="error",
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# 导入asyncio用于检查函数类型
import asyncio
