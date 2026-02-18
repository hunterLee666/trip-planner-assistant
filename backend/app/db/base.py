"""
智能旅行助手 - 数据库基础配置

SQLAlchemy基础配置和会话管理
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import get_settings

# 声明式基类
Base = declarative_base()

# 全局引擎和会话工厂
_async_engine = None
_async_session_factory = None


def get_engine():
    """获取异步数据库引擎（单例）"""
    global _async_engine
    if _async_engine is None:
        settings = get_settings()
        _async_engine = create_async_engine(
            settings.database_url,
            echo=settings.debug,  # 调试模式下输出SQL
            pool_size=10,
            max_overflow=20,
            pool_timeout=30,
            pool_recycle=1800,
        )
    return _async_engine


def get_session_factory():
    """获取异步会话工厂（单例）"""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _async_session_factory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（依赖注入使用）
    
    Yields:
        AsyncSession: 异步数据库会话
        
    Example:
        >>> @app.get("/items")
        >>> async def get_items(session: AsyncSession = Depends(get_db_session)):
        >>>     result = await session.execute(select(Item))
        >>>     return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库
    
    创建所有表（仅用于开发/测试，生产环境应使用Alembic迁移）
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """关闭数据库连接"""
    global _async_engine
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
