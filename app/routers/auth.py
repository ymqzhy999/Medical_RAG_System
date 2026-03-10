from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User
from app.schemas import UserCreate, UserLogin, UserOut
from app.services.auth_service import get_password_hash, verify_password
from captcha.image import ImageCaptcha
import random
import string
from datetime import datetime,timedelta
from app.services.auth_service import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,   # 新增
)
router = APIRouter()

def get_db():
    """获取数据库会话生成器"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/captcha")
def get_captcha():
    """生成图形验证码并设置Cookie"""
    try:
        image = ImageCaptcha(width=130, height=45)
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        data = image.generate(code)

        resp = StreamingResponse(data, media_type="image/png")
        resp.set_cookie(key="captcha_code", value=code, httponly=True, max_age=300, samesite="lax")
        return resp
    except Exception as e:
        return Response(status_code=500, content="验证码生成出错")

@router.post("/register", response_model=UserOut)
def register(
        user: UserCreate,
        request: Request,
        captcha: str = Query(None),
        db: Session = Depends(get_db)
):
    """用户注册：校验验证码、查重、加密存储密码"""
    correct_code = request.cookies.get("captcha_code")
    if not correct_code:
        raise HTTPException(status_code=400, detail="验证码已过期")

    if not captcha or captcha.upper() != correct_code.upper():
        raise HTTPException(status_code=400, detail="验证码错误")

    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="该账号已存在")

    hashed_pwd = get_password_hash(user.password)
    role = 1 if user.username == "admin" else 0

    new_user = User(username=user.username, hashed_password=hashed_pwd, role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    # 检查账号是否被禁用
    if not db_user.is_active:
        raise HTTPException(status_code=403, detail="账号已被封禁，请联系管理员")
    
    # 更新最后登录时间
    db_user.last_login = datetime.now()
    db.commit()
    db.refresh(db_user)
    
    # 创建访问令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": db_user.id,
        "username": db_user.username,
        "role": db_user.role,
            "avatar_url": db_user.avatar_url,
            "last_login": db_user.last_login
        }
    }