import io
import pandas as pd
from typing import List
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db, SessionLocal
from app.models import Document
from app.utils.vector_db import delete_vectors_by_source, add_texts_to_weaviate, add_qa_pairs_to_weaviate
import weaviate

# 初始化 Weaviate 客户端
try:
    client = weaviate.Client(url="http://localhost:8080")
except Exception:
    client = None

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])

CLASS_NAME = "MedicalQAPair"


class DocumentStatusUpdate(BaseModel):
    status: str


class BatchOperation(BaseModel):
    ids: List[int]
    status: str = None


@router.get("/list")
async def get_knowledge_list(
        db: Session = Depends(get_db),
        page: int = Query(1, ge=1),
        size: int = Query(10, ge=1, le=100)
):
    """获取知识库文档列表，包含分页和统计信息"""
    response_data = {"total_docs": 0, "total_chunks": 0, "files": []}
    base_query = db.query(Document).filter(Document.is_deleted == False)
    response_data["total_docs"] = base_query.count()

    if client:
        try:
            result = client.query.aggregate(CLASS_NAME).with_meta_count().do()
            response_data["total_chunks"] = result['data']['Aggregate'][CLASS_NAME][0]['meta']['count']
        except Exception:
            pass

    offset = (page - 1) * size
    docs = base_query.order_by(Document.upload_time.desc()).offset(offset).limit(size).all()

    for doc in docs:
        response_data["files"].append({
            "id": doc.id,
            "filename": doc.filename,
            "size": doc.file_size,
            "chunks_count": doc.chunks_count,
            "status": doc.status,
            "created_at": doc.upload_time.strftime("%Y-%m-%d %H:%M") if doc.upload_time else "未知"
        })

    return response_data


@router.put("/file/{file_id}/status")
def update_file_status(file_id: int, body: DocumentStatusUpdate, db: Session = Depends(get_db)):
    """更新单个文档状态（启用/归档）"""
    doc = db.query(Document).filter(Document.id == file_id).first()
    if not doc: raise HTTPException(404, "文件不存在")
    doc.status = body.status
    db.commit()
    return {"status": "ok", "msg": f"文件状态已更新为 {body.status}"}


@router.delete("/file/{file_id}")
def delete_file_permanently(file_id: int, db: Session = Depends(get_db)):
    """彻底删除单个文件：删除数据库记录及向量数据（无需删除本地文件）"""
    doc = db.query(Document).filter(Document.id == file_id).first()
    if not doc: raise HTTPException(404, "文件不存在")

    # 1. 删除向量库数据
    try:
        delete_vectors_by_source(doc.filename)
    except:
        pass

    # 2. 删除数据库记录
    db.delete(doc)
    db.commit()
    return {"status": "ok", "msg": "文件及向量数据已彻底删除"}


@router.put("/batch/status")
def batch_update_status(body: BatchOperation, db: Session = Depends(get_db)):
    """批量更新文档状态"""
    if not body.ids: return {"msg": "未选择文件"}
    db.query(Document).filter(Document.id.in_(body.ids)).update(
        {Document.status: body.status}, synchronize_session=False
    )
    db.commit()
    return {"status": "ok", "msg": f"批量更新完成"}


@router.delete("/batch/delete")
def batch_delete_files(body: BatchOperation, db: Session = Depends(get_db)):
    """批量彻底删除文档"""
    if not body.ids: return {"msg": "未选择文件"}
    docs_to_delete = db.query(Document).filter(Document.id.in_(body.ids)).all()

    count = 0
    for doc in docs_to_delete:
        try:
            delete_vectors_by_source(doc.filename)
        except:
            pass
        # 移除了 os.remove 本地文件的逻辑
        db.delete(doc)
        count += 1

    db.commit()
    return {"status": "ok", "msg": f"已删除 {count} 个文件"}


def process_uploaded_file(doc_id: int, file_content: bytes):
    """
    后台任务：直接在内存中处理文件内容，不依赖本地磁盘文件
    :param doc_id: 数据库文档ID
    :param file_content: 文件二进制内容
    """
    db = SessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        if not doc: return

        # 根据文件类型分流处理
        if doc.filename.lower().endswith('.csv'):
            # 策略 A: CSV 结构化处理
            try:
                # 使用 io.BytesIO 将二进制转为文件流供 pandas 读取
                # 尝试用 utf-8 读取，失败则回退到 gbk
                try:
                    df = pd.read_csv(io.BytesIO(file_content), encoding='utf-8')
                except UnicodeDecodeError:
                    df = pd.read_csv(io.BytesIO(file_content), encoding='gbk')

                df = df.fillna('')
                qa_pairs = []

                # 智能列名匹配
                for _, row in df.iterrows():
                    q = str(row.get('question', '') or row.get('query', '') or row.get('问题', '')).strip()
                    a = str(row.get('answer', '') or row.get('response', '') or row.get('回答', '')).strip()
                    if q and a:
                        qa_pairs.append({'q': q, 'a': a})

                if qa_pairs:
                    # 调用 vector_db.py 中的入库方法
                    add_qa_pairs_to_weaviate(qa_pairs, doc.filename)
                    doc.chunks_count = len(qa_pairs)
                else:
                    print(f"CSV {doc.filename} 未识别到有效问答对")

            except Exception as e:
                print(f"CSV 解析失败: {e}")
                doc.status = "failed"
                db.commit()
                return

        else:
            # 策略 B: 普通文档处理 (TXT/MD 等)
            text_content = ""
            try:
                text_content = file_content.decode("utf-8")
            except:
                try:
                    text_content = file_content.decode("gbk")
                except:
                    print(f"无法解码文件内容 {doc.filename}")
                    doc.status = "failed"
                    db.commit()
                    return

            # 简单切片
            chunks = [text_content[i:i + 500] for i in range(0, len(text_content), 500)]

            # 调用 vector_db.py 中的入库方法
            add_texts_to_weaviate(chunks, doc.filename)
            doc.chunks_count = len(chunks)

        # 更新状态为完成
        doc.status = "indexed"
        db.commit()
        print(f"文档 {doc.filename} 后台处理完成")

    except Exception as e:
        print(f"文档处理异常: {e}")
        doc.status = "failed"
        db.commit()
    finally:
        db.close()


@router.post("/upload")
async def upload_document(
        background_tasks: BackgroundTasks,
        file: UploadFile = File(...),
        db: Session = Depends(get_db)
):

    content = await file.read()
    file_size = len(content)

    new_doc = Document(
        filename=file.filename,
        file_type=file.filename.split(".")[-1],
        file_size=file_size,
        status="processing",
        chunks_count=0
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    background_tasks.add_task(process_uploaded_file, new_doc.id, content)

    return {"status": "ok", "msg": "上传成功，正在后台处理中...", "doc_id": new_doc.id}