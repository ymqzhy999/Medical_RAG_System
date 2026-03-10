import os
import hashlib
import uuid
import glob
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base

# 数据库配置
DATABASE_URL = r"sqlite:///F:\基于rag的智能医疗问答系统\Medical_RAG_System\data\medical.db"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# 表结构定义
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255))
    file_type = Column(String(50))
    vector_id = Column(String(255), nullable=True)
    file_hash = Column(String(64), index=True, nullable=True)
    file_size = Column(Integer, default=0)
    chunks_count = Column(Integer, default=0)
    is_deleted = Column(Boolean, default=False)
    upload_time = Column(DateTime, default=datetime.now)
    status = Column(String(50), default="success")


# 核心工具函数

def calculate_file_hash(file_path):
    """计算文件的 SHA256 Hash"""
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def count_valid_rows(file_path):
    """计算 CSV 文件的有效问答对数量"""
    try:
        try:
            df = pd.read_csv(file_path, encoding='utf-8')
        except:
            df = pd.read_csv(file_path, encoding='gbk')

        df = df.fillna('')
        valid_count = 0

        for _, row in df.iterrows():
            q = str(row.get('question', '')).strip() or \
                str(row.get('query', '')).strip() or \
                str(row.get('问题', '')).strip()

            a = str(row.get('answer', '')).strip() or \
                str(row.get('response', '')).strip() or \
                str(row.get('回答', '')).strip()

            if q and a:
                valid_count += 1

        return valid_count
    except Exception as e:
        print(f"读取 CSV 失败 {os.path.basename(file_path)}: {e}")
        return 0


def count_md_chunks(file_path, chunk_size=500, overlap=50):
    """计算 MD 文件的文本切片数量 (复刻后端的切片逻辑)"""
    try:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except:
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()

        # 移除多余空白，模拟实际入库前的数据清洗
        content = ' '.join(content.split())
        if not content:
            return 0

        chunks_count = 0
        start = 0
        # 模拟滑动窗口切片算法计算总切片数
        while start < len(content):
            chunks_count += 1
            start += chunk_size - overlap

        return chunks_count
    except Exception as e:
        print(f"读取 MD 失败 {os.path.basename(file_path)}: {e}")
        return 0


# 主逻辑
def sync_all_files(directory_paths):
    """
    支持传入单个目录路径或目录路径列表，同时扫描 CSV 和 MD 文件
    """
    if isinstance(directory_paths, str):
        directory_paths = [directory_paths]

    db = SessionLocal()
    try:
        files_processed = 0

        for directory_path in directory_paths:
            if not os.path.exists(directory_path):
                print(f"目录不存在，跳过: {directory_path}")
                continue

            print(f"\n开始扫描目录: {directory_path}")

            # 获取目录下所有 CSV 和 MD 文件
            all_files = glob.glob(os.path.join(directory_path, "*.csv")) + \
                        glob.glob(os.path.join(directory_path, "*.md"))

            for file_path in all_files:
                filename = os.path.basename(file_path)
                file_ext = filename.split('.')[-1].lower()

                # 1. 计算基础信息
                file_size = os.path.getsize(file_path)
                file_hash = calculate_file_hash(file_path)

                # 2. 检查数据库是否已存在 (避免重复)
                existing = db.query(Document).filter(Document.file_hash == file_hash).first()
                if existing:
                    print(f"跳过已存在: {filename}")
                    continue

                # 3. 根据文件类型计算真实的 chunks_count
                real_chunks_count = 0
                if file_ext == "csv":
                    real_chunks_count = count_valid_rows(file_path)
                elif file_ext == "md":
                    real_chunks_count = count_md_chunks(file_path)

                # 4. 入库
                new_doc = Document(
                    filename=filename,
                    file_type=file_ext,  # 动态记录为 csv 或 md
                    vector_id=str(uuid.uuid4()),
                    file_hash=file_hash,
                    file_size=file_size,
                    chunks_count=real_chunks_count,  # 填入真实数量
                    is_deleted=False,
                    status="success",
                    upload_time=datetime.now()
                )

                db.add(new_doc)
                files_processed += 1
                print(f"同步成功: {filename} (类型: {file_ext}, 包含 {real_chunks_count} 个切片/问答)")

        db.commit()
        print(f"\n全部处理完成，共同步 {files_processed} 个文件。")

    except Exception as e:
        print(f"发生错误: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":

    TARGET_DIRS = [
        r"F:\基于rag的智能医疗问答系统\Medical_RAG_System\app\medical_data\cmedqa2",
        r"F:\基于rag的智能医疗问答系统\Medical_RAG_System\app\medical_data\MedicalGuide-PDF_and_Markdown\骨科指南60\Markdown"
    ]

    sync_all_files(TARGET_DIRS)