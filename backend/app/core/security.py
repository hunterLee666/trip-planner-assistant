"""
智能旅行助手 - 安全配置

JWT认证、密码哈希等安全相关配置
"""

from datetime import datetime, timedelta
from typing import Optional, Union

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

# 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希后的密码
        
    Returns:
        是否匹配
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """获取密码哈希
    
    Args:
        password: 明文密码
        
    Returns:
        哈希后的密码
    """
    return pwd_context.hash(password)


def create_access_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None
) -> str:
    """创建JWT访问令牌
    
    Args:
        data: 要编码的数据，通常包含sub（subject）
        expires_delta: 过期时间增量，默认为配置中的值
        
    Returns:
        JWT令牌字符串
    """
    settings = get_settings()
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm="HS256"
    )
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建JWT刷新令牌
    
    刷新令牌有效期更长，用于获取新的访问令牌
    
    Args:
        data: 要编码的数据
        
    Returns:
        JWT刷新令牌
    """
    settings = get_settings()
    to_encode = data.copy()
    
    # 刷新令牌有效期30天
    expire = datetime.utcnow() + timedelta(days=30)
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.secret_key, 
        algorithm="HS256"
    )
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """解码JWT令牌
    
    Args:
        token: JWT令牌字符串
        
    Returns:
        解码后的数据，如果无效则返回None
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def verify_token(token: str, token_type: str = "access") -> Optional[dict]:
    """验证JWT令牌
    
    Args:
        token: JWT令牌字符串
        token_type: 期望的令牌类型 (access/refresh)
        
    Returns:
        验证通过返回payload，否则返回None
    """
    payload = decode_token(token)
    if payload is None:
        return None
    
    # 检查令牌类型
    if payload.get("type") != token_type:
        return None
    
    # 检查是否过期
    exp = payload.get("exp")
    if exp is None or datetime.utcnow() > datetime.fromtimestamp(exp):
        return None
    
    return payload


def generate_api_key() -> str:
    """生成API密钥
    
    Returns:
        随机生成的API密钥
    """
    import secrets
    import string
    
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(64))


class SecurityHeaders:
    """安全响应头
    
    推荐的安全HTTP响应头配置
    """
    
    @staticmethod
    def get_security_headers() -> dict:
        """获取安全响应头"""
        return {
            # 内容安全策略
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "font-src 'self'; "
                "connect-src 'self' https:;"
            ),
            # 禁止在frame中嵌入（防止点击劫持）
            "X-Frame-Options": "DENY",
            # MIME类型嗅探保护
            "X-Content-Type-Options": "nosniff",
            # XSS保护
            "X-XSS-Protection": "1; mode=block",
            #  referrer策略
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # 权限策略
            "Permissions-Policy": (
                "accelerometer=(), "
                "camera=(), "
                "geolocation=(), "
                "gyroscope=(), "
                "magnetometer=(), "
                "microphone=(), "
                "payment=(), "
                "usb=()"
            ),
            # HSTS（仅HTTPS环境启用）
            # "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        }
