from pydantic import BaseModel, Field  # 1. 导入 Field
from datetime import datetime


# 基础模型
class UserBase(BaseModel):
    # ... (Ellipsis) 表示该字段是必填的
    username: str = Field(..., min_length=4, max_length=10, description="用户名")


# 注册时
class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="密码",max_length=15)


# 登录时
class UserLogin(UserBase):
    password: str = Field(..., min_length=6, description="密码")


# 返回给前端的用户信息
class UserOut(UserBase):
    id: int
    role: int
    created_at: datetime

    class Config:
        from_attributes = True