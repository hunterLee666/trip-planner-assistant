"""
智能旅行助手 - 扩展配置管理

增强的配置管理，支持数据库、缓存、观测性等配置
"""

import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# 加载环境变量
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


class Settings(BaseSettings):
    """应用配置
    
    所有配置项均支持通过环境变量覆盖
    """
    
    # ============ 应用基本配置 ============
    app_name: str = "智能旅行助手"
    app_version: str = "2.0.0"
    debug: bool = False
    environment: str = "development"  # development, staging, production
    
    # ============ 服务器配置 ============
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1  # 生产环境建议使用多个worker
    
    # ============ CORS配置 ============
    cors_origins: str = (
        "http://localhost:5173,"
        "http://localhost:3000,"
        "http://127.0.0.1:5173,"
        "http://127.0.0.1:3000"
    )
    
    # ============ 数据库配置 ============
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/tripdb"
    database_echo: bool = False  # 是否输出SQL语句
    
    # ============ Redis配置 ============
    redis_url: str = "redis://localhost:6379/0"
    redis_password: Optional[str] = None
    
    # ============ 高德地图API配置 ============
    amap_api_key: str = ""
    amap_api_secret: Optional[str] = None
    
    # ============ Unsplash API配置 ============
    unsplash_access_key: str = ""
    unsplash_secret_key: str = ""
    
    # ============ LLM配置 ============
    # LangChain/LangGraph支持的LLM配置
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4"
    openai_temperature: float = 0.7
    
    # 备用LLM配置
    llm_api_key: Optional[str] = None
    llm_base_url: Optional[str] = None
    llm_model_id: Optional[str] = None
    
    # ============ LangSmith配置（观测性） ============
    langsmith_api_key: str = ""
    langsmith_project: str = "trip-planner"
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_tracing: bool = True
    
    # ============ JWT配置 ============
    secret_key: str = "your-secret-key-change-in-production"  # 生产环境必须修改
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    
    # ============ 日志配置 ============
    log_level: str = "INFO"
    log_format: str = "json"  # json 或 console
    
    # ============ 性能配置 ============
    # 缓存TTL（秒）
    cache_ttl_default: int = 3600
    cache_ttl_poi: int = 7200  # POI数据缓存2小时
    cache_ttl_weather: int = 1800  # 天气数据缓存30分钟
    
    # Agent执行超时（秒）
    agent_timeout: int = 60
    agent_max_retries: int = 3
    
    # 限流配置
    rate_limit_requests: int = 100  # 每分钟请求数
    rate_limit_window: int = 60  # 窗口大小（秒）
    
    # ============ 功能开关 ============
    use_langgraph: bool = True  # 是否使用LangGraph（否则使用旧版）
    langgraph_fallback_enabled: bool = True  # 失败时是否回退到旧版
    cache_enabled: bool = True
    auth_required: bool = False  # 向后兼容，默认不强制认证
    metrics_enabled: bool = True
    audit_log_enabled: bool = True
    
    # ============ 安全配置 ============
    max_request_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: str = ".jpg,.jpeg,.png,.gif,.pdf"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # 忽略额外的环境变量
    
    # ============ 辅助方法 ============
    
    def get_cors_origins_list(self) -> List[str]:
        """获取CORS origins列表"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    def get_llm_config(self) -> dict:
        """获取LLM配置（兼容新旧配置）"""
        return {
            "api_key": self.llm_api_key or self.openai_api_key,
            "base_url": self.llm_base_url or self.openai_base_url,
            "model": self.llm_model_id or self.openai_model,
        }
    
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.environment.lower() == "production"
    
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.environment.lower() == "development"


# 创建全局配置实例
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """获取配置实例（单例）
    
    Returns:
        Settings: 应用配置实例
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """重新加载配置
    
    用于配置热更新
    
    Returns:
        Settings: 新的配置实例
    """
    global _settings
    _settings = Settings()
    return _settings


# 验证必要的配置
def validate_config():
    """验证配置是否完整
    
    Raises:
        ValueError: 当必要配置缺失时
    """
    settings = get_settings()
    errors = []
    warnings = []
    
    # 必要配置
    if not settings.amap_api_key:
        errors.append("AMAP_API_KEY未配置，高德地图服务将无法使用")
    
    if not settings.database_url:
        errors.append("DATABASE_URL未配置，数据库功能将无法使用")
    
    # LLM配置（使用openai或llm_api_key均可）
    llm_key = settings.openai_api_key or settings.llm_api_key
    if not llm_key:
        warnings.append("LLM API Key未配置，AI功能将无法使用")
    
    # 生产环境检查
    if settings.is_production():
        if settings.secret_key == "your-secret-key-change-in-production":
            errors.append("生产环境必须使用自定义SECRET_KEY")
        
        if settings.debug:
            warnings.append("生产环境不应启用DEBUG模式")
        
        if not settings.langsmith_api_key and settings.langsmith_tracing:
            warnings.append("生产环境建议启用LangSmith追踪")
    
    if errors:
        error_msg = "配置错误:\n" + "\n".join(f"  - {e}" for e in errors)
        raise ValueError(error_msg)
    
    if warnings:
        print("\n⚠️  配置警告:")
        for w in warnings:
            print(f"  - {w}")
    
    return True


def print_config():
    """打印当前配置（隐藏敏感信息）"""
    settings = get_settings()
    
    print(f"应用名称: {settings.app_name}")
    print(f"版本: {settings.app_version}")
    print(f"环境: {settings.environment}")
    print(f"服务器: {settings.host}:{settings.port}")
    print(f"数据库: {'已配置' if settings.database_url else '未配置'}")
    print(f"Redis: {'已配置' if settings.redis_url else '未配置'}")
    print(f"高德地图API Key: {'已配置' if settings.amap_api_key else '未配置'}")
    print(f"LLM API Key: {'已配置' if (settings.openai_api_key or settings.llm_api_key) else '未配置'}")
    print(f"LangSmith: {'已配置' if settings.langsmith_api_key else '未配置'}")
    print(f"LangGraph: {'启用' if settings.use_langgraph else '禁用'}")
    print(f"缓存: {'启用' if settings.cache_enabled else '禁用'}")
    print(f"认证: {'必需' if settings.auth_required else '可选'}")
    print(f"日志级别: {settings.log_level}")
