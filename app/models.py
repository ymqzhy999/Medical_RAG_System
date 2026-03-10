from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime, Text, Float
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base
class User(Base):
    """用户表：存储账号、密码、角色及头像信息"""
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    role = Column(Integer, default=0)  # 0:普通用户, 1:管理员

    # 账号是否启用，默认启用
    is_active = Column(Boolean, default=True)

    avatar_url = Column(String(255), default="")
    created_at = Column(DateTime, default=datetime.now)
    last_login = Column(DateTime, nullable=True)

    sessions = relationship("ChatSession", back_populates="user")
    logs = relationship("AuditLog", back_populates="user")


class ChatSession(Base):
    """会话表：存储对话窗口信息"""
    __tablename__ = "chat_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String, default="新建问诊")
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    user = relationship("User", back_populates="sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    """消息表：存储具体的问答记录及引用源"""
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String)  # user 或 assistant
    content = Column(Text)
    sources = Column(Text, nullable=True)  # JSON格式存储的引用资料
    feedback = Column(Integer, default=0)  # 0:无, 1:赞, -1:踩
    model_name = Column(String(50), default="gemma3:4b")
    process_time = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

    session = relationship("ChatSession", back_populates="messages")


class AuditLog(Base):
    """审计日志表 (精简版)：专注记录用户的敏感/消极提问"""
    __tablename__ = "audit_logs"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    # 记录敏感关键词或摘要
    content = Column(Text)

    # 是否为敏感高危问题
    is_risky = Column(Boolean, default=False)

    timestamp = Column(DateTime, default=datetime.now)

    user = relationship("User", back_populates="logs")


class Document(Base):
    """知识库文档表"""
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    file_type = Column(String)
    vector_id = Column(String, nullable=True)
    file_hash = Column(String(64), index=True, nullable=True)
    file_size = Column(Integer, default=0)
    chunks_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    upload_time = Column(DateTime, default=datetime.now)
    status = Column(String, default="processing")