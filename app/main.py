import os
import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.routing import APIRoute
from contextlib import asynccontextmanager
from app.routers import auth, chat, admin, knowledge
from app.database import engine, Base
from app import models
Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("\n" + "=" * 50)
    print("系统启动中...")

    # 1. 打印路由表
    print("\n当前生效的接口地址:")
    for route in app.routes:
        if isinstance(route, APIRoute):
            print(f"  [{', '.join(route.methods)}] {route.path}")

    # 2. 检查 Ollama 连接
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://localhost:11434/")
            if resp.status_code == 200:
                print("Ollama 服务已在线")
    except Exception:
        print("警告: 无法连接 Ollama (http://localhost:11434)")

    print("=" * 50 + "\n")
    yield
    print("系统已关闭")


app = FastAPI(title="智能医疗问答系统", lifespan=lifespan)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

app.include_router(knowledge.router, tags=["Knowledge Base"])


# 静态文件配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


# --- 页面路由 ---
@app.get("/")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/chat")
def chat_page(request: Request):
    return templates.TemplateResponse(request=request, name="chat.html")


@app.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")

@app.get("/admin/prompts")
def admin_prompts_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_prompts.html")

@app.get("/profile")
def profile_page(request: Request):
    return templates.TemplateResponse(request=request, name="profile.html")