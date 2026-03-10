import json
import re
import time
import shutil
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, Depends, Body, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc
from openai import OpenAI

from app.utils.util import logger, log_step
from app.database import SessionLocal
from app.models import ChatSession, ChatMessage, AuditLog, User,Document
from app.utils.vector_db import search_knowledge_base

from app.prompts import prompt_manager
router = APIRouter()

OLLAMA_API_KEY = "ollama"
OLLAMA_BASE_URL = "http://localhost:11434/v1"
CHAT_MODEL = "gemma3:4b"

BASE_DIR = Path(__file__).parent.parent.parent
UPLOAD_DIR = BASE_DIR / "static" / "avatars"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

client = OpenAI(api_key=OLLAMA_API_KEY, base_url=OLLAMA_BASE_URL)


def call_llm_sync(prompt, step_name="LLM_Call"):
    """带日志监控的 LLM 调用"""
    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1
        )
        result = response.choices[0].message.content.strip()
        log_step(step_name, prompt, result, time.time() - t0)
        return result
    except Exception as e:
        logger.error(f"{step_name} Error: {e}")
        return ""


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




@router.post("/users/{user_id}/avatar")
async def upload_avatar(
        user_id: int,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    # 1. 检查用户是否存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")

    # 2. 生成文件名 (防止重名覆盖)
    file_ext = file.filename.split(".")[-1]
    filename = f"avatar_{user_id}_{int(time.time())}.{file_ext}"
    file_path = UPLOAD_DIR / filename

    # 3. 保存文件
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"Avatar upload failed: {e}")
        raise HTTPException(500, "File save failed")

    # 4. 更新数据库 URL
    # 注意：这里生成的路径需要匹配 main.py 里的 mount 路径
    avatar_url = f"/static/avatars/{filename}"
    user.avatar_url = avatar_url
    db.commit()

    logger.info(f"用户 {user_id} 头像上传成功: {avatar_url}")
    return {"status": "ok", "avatar_url": avatar_url}




@router.get("/sessions")
def get_sessions(user_id: int, db: Session = Depends(get_db)):
    # 按更新时间倒序
    return db.query(ChatSession).filter(ChatSession.user_id == user_id, ChatSession.is_deleted == False).order_by(
        desc(ChatSession.updated_at)).all()


@router.post("/sessions")
def create_session(item: dict = Body(...), db: Session = Depends(get_db)):
    if not item.get("user_id"): raise HTTPException(400, "Missing user_id")
    sess = ChatSession(user_id=item["user_id"], title="新问诊对话")
    db.add(sess)
    db.commit()
    db.refresh(sess)
    return sess


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, db: Session = Depends(get_db)):
    sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if sess:
        sess.is_deleted = True
        db.commit()
    return {"status": "ok"}


@router.put("/sessions/{session_id}/rename")
def rename_session(session_id: int, item: dict = Body(...), db: Session = Depends(get_db)):
    sess = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if sess: sess.title = item.get("title"); db.commit()
    return sess


@router.get("/sessions/{session_id}/messages")
def get_messages(session_id: int, db: Session = Depends(get_db)):
    msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(
        ChatMessage.timestamp.asc()).all()

    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "sources": m.sources,
            "feedback": m.feedback
        }
        for m in msgs
    ]



@router.post("/messages/{message_id}/feedback")
def update_feedback(
        message_id: int,
        payload: dict = Body(...),
        db: Session = Depends(get_db)
):
    msg = db.query(ChatMessage).filter(ChatMessage.id == message_id).first()
    if not msg:
        raise HTTPException(404, "Message not found")

    action = payload.get("action")

    if action == "like":
        msg.feedback = 1
    elif action == "dislike":
        msg.feedback = -1
    else:
        msg.feedback = 0

    db.commit()
    return {"status": "ok", "current_feedback": msg.feedback}


@router.post("/send")
async def send_message(
        user_id: int = Body(...),
        session_id: int = Body(...),
        content: str = Body(...),
        db: Session = Depends(get_db)
):
    logger.info(f"\n{'#' * 30} 新的问诊请求 {'#' * 30}")
    
    # 记录开始时间
    t_start = time.time()

    # 1. 存入数据库
    user_msg = ChatMessage(session_id=session_id, role="user", content=content)
    db.add(user_msg)

    # 更新会话时间
    session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
    if session:
        session.updated_at = datetime.now()
        if session.title == "新问诊对话":
            session.title = content[:10] + "..." if len(content) > 10 else content
    db.commit()

    # Step 1: 安全检测
    safety_result = call_llm_sync(prompt_manager.get("SAFETY_CHECK_PROMPT").format(query=content), "1. Safety Check")
    if "Unsafe" in safety_result:
        return StreamingResponse(iter([f"data: {json.dumps({'text': prompt_manager.get('BLOCK_RESPONSE_TEXT')})}\n\n"]),
                                 media_type="text/event-stream")

    # Step 2: 意图判断
    intent = call_llm_sync(prompt_manager.get("INTENT_CLASSIFY_PROMPT").format(query=content),
                           "2. Intent Classification")
    is_medical = "medical" in intent.lower()

    user_final_content = ""
    sources_data = []

    if is_medical:
        # Step 3: LLM 语义提炼
        keywords_str = call_llm_sync(prompt_manager.get("QUERY_OPTIMIZE_PROMPT").format(query=content),
                                     "3. Query Optimization")
        clean_keywords = " ".join(keywords_str.replace("\n", " ").split())

        # 混合检索，使用黑名单策略过滤归档文件
        t_search = time.time()

        # 4.1 获取“黑名单”：只查那些明确被归档的文件
        archived_docs = db.query(Document).filter(Document.status == 'archived').all()
        archived_filenames = {doc.filename for doc in archived_docs}

        if archived_filenames:
            logger.info(f"归档文件黑名单: {archived_filenames}")

        # 4.2 执行全局检索 (不传 allowed_files，让它搜所有)
        # 这样脚本导入的 CSV (MySQL里没记录) 也能被搜到了！
        # 降低 alpha 值，提高关键词检索权重，减少无关结果
        raw_results = search_knowledge_base(
            original_query=content,
            extracted_keywords=clean_keywords,
            limit=5,
            alpha=0.0,
            allowed_files=None
        )

        # 4.3 在 Python 层面进行过滤
        # 如果检索结果的文件名在黑名单里，就剔除
        valid_results = []
        for res in raw_results:
            if res['filename'] not in archived_filenames:
                valid_results.append(res)
            else:
                logger.info(f"过滤掉已归档内容: {res['filename']}")

        # 截取前3个
        raw_results = valid_results[:3]

        log_step("4. Hybrid Retrieval", f"Keys: {clean_keywords}", raw_results, time.time() - t_search)

        # Step 5: 资料相关性过滤
        final_results = []
        if raw_results:
            docs_preview = "\n".join([f"资料[{i}]: {r['content'][:120]}..." for i, r in enumerate(raw_results)])
            valid_ids_str = call_llm_sync(
                prompt_manager.get("DATA_FILTER_PROMPT").format(docs=docs_preview, query=content), "5. Data Filtering")
            valid_indices = [int(x) for x in re.findall(r'\d+', valid_ids_str)]

            for idx in valid_indices:
                if 0 <= idx < len(raw_results):
                    final_results.append(raw_results[idx])

        if final_results:
            context_str = "\n".join([f"- {r['content']} (来源:{r['filename']})" for r in final_results])
            user_final_content = prompt_manager.get("DOCTOR_USER_PROMPT").format(context=context_str, query=content)

            for i, res in enumerate(final_results):
                sources_data.append({
                    "id": i + 1,
                    "title": res['filename'],
                    "snippet": res['content'][:50] + "...",
                    "full_content": res['content'],
                    "score": res['score']
                })
        else:
            no_data_text = prompt_manager.get("NO_DATA_RESPONSE_TEXT")
            user_final_content = prompt_manager.get("DOCTOR_USER_PROMPT").format(context=no_data_text, query=content)
    else:
        user_final_content = f"用户进行闲聊：{content}。请亲切回复。"

    # Step 6: 流式生成
    def response_generator():
        if sources_data:
            yield f"data: {json.dumps({'sources': sources_data})}\n\n"

        history = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(
            ChatMessage.timestamp.desc()).limit(4).all()
        history.reverse()

        messages = [{"role": "system", "content": prompt_manager.get("DOCTOR_SYSTEM_PROMPT")}]
        for h in history: messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": user_final_content})

        try:
            response = client.chat.completions.create(model=CHAT_MODEL, messages=messages, stream=True)
            full_reply = ""
            for chunk in response:
                token = chunk.choices[0].delta.content
                if token:
                    full_reply += token
                    yield f"data: {json.dumps({'text': token})}\n\n"

            # 存库 AI 回复
            new_db = SessionLocal()
            try:
                # 计算总处理时间（从请求开始到回复完成）
                process_time = time.time() - t_start
                ai_msg = ChatMessage(session_id=session_id, role="assistant", content=full_reply,
                                     sources=json.dumps(sources_data) if sources_data else None, 
                                     feedback=0, process_time=process_time)
                new_db.add(ai_msg);
                new_db.commit();
                new_db.refresh(ai_msg)
                yield f"data: {json.dumps({'meta': {'message_id': ai_msg.id}})}\n\n"
            finally:
                new_db.close()

        except Exception as e:
            logger.error(f"Generate Error: {e}")
            yield f"data: {json.dumps({'text': '系统繁忙...'})}\n\n"

    return StreamingResponse(response_generator(), media_type="text/event-stream")