"""
智能旅行助手 - 数据库模型

定义所有数据库模型类
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=True)  # OAuth用户可能无密码
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)
    
    # OAuth相关
    oauth_provider = Column(String(50))  # google, github等
    oauth_id = Column(String(255))
    
    # API密钥（用于程序化访问）
    api_key = Column(String(128), unique=True, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    
    # 关联关系
    trip_plans = relationship("TripPlanRecord", back_populates="user", lazy="dynamic")
    
    def __repr__(self):
        return f"<User(email='{self.email}', id='{self.id}')>"


class TripPlanRecord(Base):
    """旅行计划记录表"""
    __tablename__ = "trip_plans"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # 请求数据（完整保存用户请求）
    request_data = Column(JSON, nullable=False)
    
    # 响应数据（完整保存生成的旅行计划）
    response_data = Column(JSON)
    
    # 执行状态: pending, processing, completed, failed, cached
    status = Column(String(50), default="pending", index=True)
    
    # 元数据
    execution_time_ms = Column(Integer)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # LangGraph检查点ID（用于恢复状态）
    checkpoint_id = Column(String(255))
    
    # 是否使用降级方案
    is_fallback = Column(Boolean, default=False)
    
    # 是否公开分享
    is_public = Column(Boolean, default=False)
    share_token = Column(String(64), unique=True, index=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系
    user = relationship("User", back_populates="trip_plans")
    
    def __repr__(self):
        return f"<TripPlanRecord(id='{self.id}', city='{self.request_data.get('city')}', status='{self.status}')>"


class CacheEntry(Base):
    """缓存表（PostgreSQL备用，Redis为主）
    
    用于需要持久化的缓存数据
    """
    __tablename__ = "cache_entries"
    
    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False)
    expires_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<CacheEntry(key='{self.key}', expires_at='{self.expires_at}')>"


class AuditLog(Base):
    """审计日志表
    
    记录重要操作，用于安全和合规
    """
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    
    # 操作信息
    action = Column(String(50), nullable=False, index=True)  # create, update, delete, login等
    resource_type = Column(String(50))  # trip_plan, user等
    resource_id = Column(String(255))
    
    # 请求信息
    ip_address = Column(String(45))
    user_agent = Column(Text)
    request_path = Column(String(500))
    request_method = Column(String(10))
    
    # 变更详情（JSON格式）
    before_data = Column(JSON)
    after_data = Column(JSON)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AuditLog(action='{self.action}', user_id='{self.user_id}', created_at='{self.created_at}')>"


class SystemMetric(Base):
    """系统指标表
    
    存储性能指标和统计信息
    """
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 指标类型
    metric_type = Column(String(50), nullable=False, index=True)  # api_latency, agent_execution等
    metric_name = Column(String(100), nullable=False)
    
    # 数值
    value = Column(Float, nullable=False)
    unit = Column(String(20))  # ms, count, percent等
    
    # 维度标签（JSON格式）
    labels = Column(JSON)
    
    # 时间戳（按小时聚合）
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<SystemMetric(type='{self.metric_type}', name='{self.metric_name}', value={self.value})>"
