"""
智能旅行助手 - API依赖注入

FastAPI依赖定义
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import verify_token
from app.db.base import get_db_session
from app.services.cache_service import get_cache_service
from app.services.trip_planning_service import get_trip_planning_service

# JWT认证方案
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取当前用户

    从JWT令牌中解码用户信息

    Args:
        credentials: HTTP认证凭证

    Returns:
        用户ID

    Raises:
        HTTPException: 认证失败时
    """
    from app.config import get_settings

    settings = get_settings()

    # 如果认证不是强制的，允许匿名访问
    if not settings.auth_required:
        return None

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证令牌",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="令牌中未包含用户信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user_id


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取当前用户（可选）

    认证失败时不抛出异常，返回None

    Args:
        credentials: HTTP认证凭证

    Returns:
        用户ID或None
    """
    if not credentials:
        return None

    token = credentials.credentials
    payload = verify_token(token)

    if payload is None:
        return None

    return payload.get("sub")


# 导出依赖
__all__ = [
    "get_db_session",
    "get_cache_service",
    "get_trip_planning_service",
    "get_current_user",
    "get_optional_user",
]
