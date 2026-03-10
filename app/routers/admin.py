# app/routers/admin.py
import os
import shutil
import re
import time
import json
from pathlib import Path
from typing import Optional, List
import pandas as pd
from fastapi import APIRouter, Depends, Query, UploadFile, File, BackgroundTasks, HTTPException, Body
from sqlalchemy import or_
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from pydantic import BaseModel
from openai import OpenAI
import uuid
from app.database import SessionLocal
from app.models import ChatMessage, User, ChatSession, Document, AuditLog
from app.prompts import prompt_manager
from app.utils.vector_db import calculate_file_hash,add_texts_to_weaviate, delete_vectors_by_source, search_knowledge_base,add_qa_pairs_to_weaviate

router = APIRouter()

KB_UPLOAD_DIR = Path("data/knowledge_base")
KB_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_API_KEY = "ollama"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
CHAT_MODEL = "gemma3:4b"

client = OpenAI(api_key=OLLAMA_API_KEY, base_url=OLLAMA_BASE_URL)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def call_llm_simple(prompt):
    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {e}"


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    # 首页看板用的统计数据
    return {
        "users": db.query(User).count(),
        "messages": db.query(ChatMessage).count(),
        "likes": db.query(ChatMessage).filter(ChatMessage.feedback == 1).count(),
        "dislikes": db.query(ChatMessage).filter(ChatMessage.feedback == -1).count()
    }


@router.get("/feedbacks")
def get_feedbacks_list(
        filter_type: str = Query("all", description="all, like, dislike"),
        page: int = Query(1, ge=1),
        size: int = Query(9, ge=1, le=100),
        search: str = Query("", description="搜索关键词"),
        db: Session = Depends(get_db)
):
    # 只查AI回复的消息，毕竟用户发的消息没有反馈按钮
    query = (
        db.query(ChatMessage, User.username, ChatSession.title)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .join(User, ChatSession.user_id == User.id)
        .filter(ChatMessage.role == 'assistant')
    )

    # 搜索功能：搜索用户名或消息内容
    if search and search.strip():
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.username.like(search_term),
                ChatMessage.content.like(search_term)
            )
        )

    if filter_type == "like":
        query = query.filter(ChatMessage.feedback == 1)
    elif filter_type == "dislike":
        query = query.filter(ChatMessage.feedback == -1)

    total = query.count()

    # 处理分页
    offset = (page - 1) * size
    results = query.order_by(desc(ChatMessage.timestamp)).offset(offset).limit(size).all()

    items = []
    for msg, username, title in results:
        # 顺便把上一句用户问的话也查出来，不然光看回答不知道在聊啥
        user_query_msg = db.query(ChatMessage).filter(
            ChatMessage.session_id == msg.session_id,
            ChatMessage.id < msg.id,
            ChatMessage.role == "user"
        ).order_by(desc(ChatMessage.id)).first()

        items.append({
            "id": msg.id,
            "username": username,
            "user_query": user_query_msg.content if user_query_msg else "（无上下文）",
            "ai_reply": msg.content,
            "feedback": msg.feedback,
            "time": msg.timestamp.strftime("%Y-%m-%d %H:%M")
        })

    return {
        "total": total,
        "page": page,
        "size": size,
        "items": items
    }


class FeedbackDeleteRequest(BaseModel):
    message_ids: List[int]


@router.delete("/feedbacks")
def delete_feedbacks(body: FeedbackDeleteRequest, db: Session = Depends(get_db)):
    """批量删除反馈消息"""
    if not body.message_ids:
        raise HTTPException(400, "请选择要删除的消息")

    deleted_count = db.query(ChatMessage).filter(ChatMessage.id.in_(body.message_ids)).delete(synchronize_session=False)
    db.commit()
    return {"status": "ok", "msg": f"已删除 {deleted_count} 条反馈"}


@router.get("/message/{message_id}/details")
def get_message_details(message_id: int, db: Session = Depends(get_db)):
    # 后台双击某条反馈时，把整个聊天记录调出来方便回溯
    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        return {"error": "Message not found"}

    session_msgs = db.query(ChatMessage).filter(
        ChatMessage.session_id == msg.session_id
    ).order_by(ChatMessage.timestamp).all()

    return {
        "current_msg_id": msg.id,
        "chat_history": [
            {
                "role": m.role,
                "content": m.content,
                "time": m.timestamp.strftime("%H:%M:%S"),
                "is_target": m.id == msg.id
            }
            for m in session_msgs
        ]
    }


class PromptUpdate(BaseModel):
    key: str
    content: str


@router.get("/prompts")
def get_all_prompts(db: Session = Depends(get_db)):
    return prompt_manager._prompts


@router.post("/prompts")
def update_prompt(item: PromptUpdate, db: Session = Depends(get_db)):
    # 保存提示词到文件，这样重启服务也不会丢
    success = prompt_manager.update_and_save(item.key, item.content)
    if not success:
        raise HTTPException(status_code=500, detail="写入文件失败")
    return {"status": "ok", "msg": "提示词已更新并保存"}


class PromptTestRequest(BaseModel):
    template: str
    inputs: dict


@router.post("/test_prompt")
def test_prompt(req: PromptTestRequest):
    """
    接收前端传来的 提示词模板 + 模拟变量，调用 LLM 返回结果
    """
    try:
        # 把前端传来的变量填进模板里
        prompt_content = req.template.format(**req.inputs)

        # 发给大模型看看效果
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt_content}],
            temperature=0.1
        )
        return {"status": "ok", "result": response.choices[0].message.content}
    except KeyError as e:
        return {"status": "error", "msg": f"缺少必要变量: {e}"}
    except Exception as e:
        return {"status": "error", "msg": str(e)}


class ChainTestRequest(BaseModel):
    query: str
    # 允许接收 null，防止前端传空报错
    override_key: Optional[str] = None
    override_content: Optional[str] = None


@router.post("/test_rag_chain")
def test_rag_chain(req: ChainTestRequest):
    logs = []

    def get_prompt(key):
        # 如果是在调试模式下临时改了Prompt，就用临时的，否则用系统的
        if req.override_key == key and req.override_content:
            return req.override_content
        return prompt_manager.get(key)

    # 第一步：先检查安全问题，防止注入或违规
    t0 = time.time()
    safety_tpl = get_prompt("SAFETY_CHECK_PROMPT")
    safety_res = call_llm_simple(safety_tpl.format(query=req.query))
    logs.append({
        "step": "安全检测",
        "title": "Safety Check",
        "output": f"Prompt:\n{safety_tpl}\n\nResult:\n{safety_res}",
        "preview": f"结果: {safety_res}",
        "time": f"{time.time() - t0:.2f}s",
        "status": "danger" if "Unsafe" in safety_res else "success"
    })

    if "Unsafe" in safety_res:
        block_text = get_prompt("BLOCK_RESPONSE_TEXT")
        return {"status": "ok", "final_reply": block_text, "logs": logs}

    # 第二步：判断意图，如果是闲聊就没必要去查数据库了
    t0 = time.time()
    intent_tpl = get_prompt("INTENT_CLASSIFY_PROMPT")
    intent_res = call_llm_simple(intent_tpl.format(query=req.query))
    is_medical = "medical" in intent_res.lower()
    logs.append({
        "step": "意图分类",
        "title": "Intent Classification",
        "output": f"Prompt:\n{intent_tpl}\n\nResult:\n{intent_res}",
        "preview": f"分类: {intent_res}",
        "time": f"{time.time() - t0:.2f}s",
        "status": "info"
    })

    if is_medical:
        # 第三步：提取关键词，把用户的大白话转成适合搜索的词条
        t0 = time.time()
        opt_tpl = get_prompt("QUERY_OPTIMIZE_PROMPT")
        keywords_raw = call_llm_simple(opt_tpl.format(query=req.query))
        # 去掉换行符，整理干净
        clean_keywords = " ".join(keywords_raw.replace("\n", " ").split())
        logs.append({
            "step": "关键词提取",
            "title": "Query Optimization",
            "output": f"Raw LLM Output:\n{keywords_raw}\n\nFinal Keywords:\n{clean_keywords}",
            "preview": clean_keywords,
            "time": f"{time.time() - t0:.2f}s",
            "status": "info"
        })

        # 第四步：去知识库里检索（混合检索：向量+关键词）
        t0 = time.time()

        allowed_list = None

        search_res = search_knowledge_base(
            req.query,
            clean_keywords,
            limit=3,
            allowed_files=allowed_list  # 这里传 None，就和 chat.py 一模一样了
        )

        # 记录一下到底搜到了啥原始数据
        logs.append({
            "step": "知识库检索",
            "title": "Hybrid Retrieval",
            "output": json.dumps(search_res, ensure_ascii=False, indent=2),
            "preview": f"检索到 {len(search_res)} 条原始数据",
            "time": f"{time.time() - t0:.2f}s",
            "status": "warning" if not search_res else "success"
        })

        # 第五步：资料清洗，用大模型把不相关的搜索结果剔除掉
        valid_docs = []
        if search_res:
            t0 = time.time()
            docs_text = "\n".join([f"资料[{i}]: {r['content'][:100]}..." for i, r in enumerate(search_res)])
            filter_tpl = get_prompt("DATA_FILTER_PROMPT")
            filter_res = call_llm_simple(filter_tpl.format(docs=docs_text, query=req.query))

            # 解析大模型返回的索引号
            valid_indices = [int(x) for x in re.findall(r'\d+', filter_res)]
            valid_docs = [search_res[i] for i in valid_indices if 0 <= i < len(search_res)]

            logs.append({
                "step": "资料清洗",
                "title": "Data Filtering",
                "output": f"Prompt:\n{filter_tpl}\n\nLLM Response:\n{filter_res}\n\nValid Indices: {valid_indices}",
                "preview": f"保留 {len(valid_docs)}/{len(search_res)} 篇",
                "time": f"{time.time() - t0:.2f}s",
                "status": "info"
            })
        else:
            # 没搜到东西就跳过清洗
            logs.append({
                "step": "资料清洗",
                "title": "Data Filtering",
                "output": "由于检索结果为空，跳过清洗步骤。",
                "preview": "跳过 (无数据)",
                "time": "0.00s",
                "status": "warning"
            })

        # 组装上下文，把保留下来的资料拼成一段话
        if valid_docs:
            context_str = "\n".join([f"- {r['content']} (来源:{r['filename']})" for r in valid_docs])
            doctor_user_tpl = get_prompt("DOCTOR_USER_PROMPT")
            final_context = doctor_user_tpl.format(context=context_str, query=req.query)
        else:
            no_data_tpl = get_prompt("NO_DATA_RESPONSE_TEXT")
            doctor_user_tpl = get_prompt("DOCTOR_USER_PROMPT")
            # 处理一下模板里可能没有context占位符的情况
            if "{context}" in doctor_user_tpl:
                final_context = doctor_user_tpl.format(context=no_data_tpl, query=req.query)
            else:
                final_context = no_data_tpl

    else:
        # 非医疗问题直接闲聊
        final_context = f"用户进行闲聊：{req.query}。请亲切回复。"
        logs.append({"step": "非医疗问题", "title": "Skip RAG", "output": "跳过检索与清洗", "preview": "跳过 RAG",
                     "status": "warning"})

    # 第六步：最终生成回答
    # 注意：这里我们不再记录 Prompt 构建的日志，防止内容太长把前端撑爆
    system_tpl = get_prompt("DOCTOR_SYSTEM_PROMPT")
    t0 = time.time()
    messages = [
        {"role": "system", "content": system_tpl},
        {"role": "user", "content": final_context}
    ]

    try:
        resp = client.chat.completions.create(
            model=CHAT_MODEL, messages=messages, temperature=0.1
        )
        final_reply = resp.choices[0].message.content
    except Exception as e:
        final_reply = f"Error: {e}"

    logs.append({
        "step": "最终回答",
        "title": "Final Answer",
        "output": final_reply,
        "preview": "生成完毕 (点击查看)",
        "time": f"{time.time() - t0:.2f}s",
        "status": "success"
    })

    return {
        "status": "ok",
        "final_reply": final_reply,
        "logs": logs
    }


@router.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    # 列表页展示
    docs = db.query(Document).order_by(desc(Document.upload_time)).all()
    return [{
        "id": d.id,
        "filename": d.filename,
        "size": f"{d.file_size / 1024:.2f} KB",
        "type": d.file_type,
        "upload_time": d.upload_time.strftime("%Y-%m-%d %H:%M"),
        "status": d.status
    } for d in docs]


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """删除文档及其向量数据"""
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")

    file_path = KB_UPLOAD_DIR / doc.filename
    if file_path.exists():
        os.remove(file_path)

    delete_vectors_by_source(doc.filename)

    # 3. 最后删掉 MySQL 里的记录
    db.delete(doc)
    db.commit()
    return {"status": "ok"}


def chunk_text(text, chunk_size=500, overlap=50):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def process_document_task(doc_id: int):
    db = SessionLocal()
    doc = None
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc: return

        file_path = KB_UPLOAD_DIR / doc.filename
        file_ext = doc.file_type.lower()

        if file_ext == "csv":
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except:
                df = pd.read_csv(file_path, encoding='gbk')
            df = df.fillna('')

            qa_pairs = []
            for _, row in df.iterrows():
                q = str(row.get('question', '')).strip() or str(row.get('query', '')).strip() or str(row.get('问题', '')).strip()
                a = str(row.get('answer', '')).strip() or str(row.get('response', '')).strip() or str(row.get('回答', '')).strip()
                if q and a:
                    qa_pairs.append({'q': q, 'a': a})

            if qa_pairs:
                add_qa_pairs_to_weaviate(qa_pairs, source_filename=doc.filename)
                doc.chunks_count = len(qa_pairs)

        elif file_ext in ["md", "txt"]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    text_content = f.read()
            except:
                with open(file_path, "r", encoding="gbk") as f:
                    text_content = f.read()

            text_content = ' '.join(text_content.split())
            chunks = chunk_text(text_content, chunk_size=500, overlap=50)

            if chunks:
                add_texts_to_weaviate(chunks, source=doc.filename)
                doc.chunks_count = len(chunks)    # <--- 关键：持久化 Markdown 切片数量！

        else:
            raise ValueError(f"暂不支持处理此文件类型: {file_ext}")

        # 更新数据库状态为已索引，并提交 chunks_count
        doc.status = "indexed"
        db.commit()
        print(f"文档 {doc.filename} 处理完成，共持久化 {doc.chunks_count} 个切片/问答")

    except Exception as e:
        print(f"文档处理失败: {e}")
        if doc:
            doc.status = "failed"
            db.commit()
    finally:
        db.close()

@router.post("/upload_doc")
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    file_path = KB_UPLOAD_DIR / file.filename
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    file_size = os.path.getsize(file_path)
    file_hash = calculate_file_hash(file_path)

    existing_doc = db.query(Document).filter(Document.file_hash == file_hash).first()
    if existing_doc:
        return {"status": "error", "msg": "该文件已存在于知识库中！"}

    new_doc = Document(
        filename=file.filename,
        file_type=file.filename.split(".")[-1].lower(),
        vector_id=str(uuid.uuid4()),  # 持久化 UUID
        file_hash=file_hash,          # 持久化 Hash
        file_size=file_size,          # 持久化 文件大小
        chunks_count=0,
        status="processing"
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    # 扔给后台慢慢跑，别卡住接口
    background_tasks.add_task(process_document_task, new_doc.id)

    return {"status": "ok", "msg": "文件已上传，正在后台处理..."}

class UserStatusUpdate(BaseModel):
    is_active: bool


@router.get("/dashboard/charts")
def get_dashboard_charts(db: Session = Depends(get_db)):
    """获取数据面板的图表数据"""

    # 用户反馈分布饼图
    feedback_stats = db.query(
        ChatMessage.feedback, func.count(ChatMessage.id)
    ).group_by(ChatMessage.feedback).all()

    feedback_map = {0: "普通咨询", 1: "好评", -1: "差评"}
    pie_data = []
    colors = {0: "#6b7280", 1: "#4caf50", -1: "#ef4444"}

    for fb_val, count in feedback_stats:
        pie_data.append({
            "name": feedback_map.get(fb_val, "未知"),
            "value": count,
            "itemStyle": {"color": colors.get(fb_val, "#888")}
        })

    # 消极敏感提问用户排行柱状图
    risky_stats = db.query(
        User.username, func.count(AuditLog.id).label("count")
    ).join(AuditLog, AuditLog.user_id == User.id) \
        .filter(AuditLog.is_risky == True) \
        .group_by(User.id) \
        .order_by(desc("count")) \
        .limit(10).all()

    bar_x = [row[0] for row in risky_stats]  # 用户名
    bar_y = [row[1] for row in risky_stats]  # 次数

    # 平均响应时间
    avg_time = db.query(func.avg(ChatMessage.process_time)).filter(ChatMessage.process_time > 0).scalar() or 0

    return {
        "feedback_chart": pie_data,
        "risk_user_chart": {
            "usernames": bar_x,
            "counts": bar_y
        },
        "avg_response_time": round(avg_time, 2)
    }


@router.get("/users")
def get_user_list(
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100),
        db: Session = Depends(get_db)
):
    """获取用户列表 (支持分页)"""
    offset = (page - 1) * size
    total = db.query(User).count()

    users = db.query(User).order_by(desc(User.created_at)).offset(offset).limit(size).all()

    return {
        "total": total,
        "items": [{
            "id": u.id,
            "username": u.username,
            "role": "管理员" if u.role == 1 else "普通用户",
            "is_active": u.is_active,
            "avatar": u.avatar_url,
            "created_at": u.created_at.strftime("%Y-%m-%d"),
            "last_login": u.last_login.strftime("%Y-%m-%d %H:%M") if u.last_login else "从未登录"
        } for u in users]
    }


@router.put("/users/{user_id}/status")
def update_user_status(user_id: int, body: UserStatusUpdate, db: Session = Depends(get_db)):
    """禁用或启用用户"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")

    if user.username == "admin" and body.is_active is False:
        raise HTTPException(400, "无法禁用超级管理员")

    user.is_active = body.is_active
    db.commit()

    action_text = "启用" if body.is_active else "禁用"
    return {"status": "ok", "msg": f"用户 {user.username} 已{action_text}"}