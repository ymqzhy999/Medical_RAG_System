import weaviate
import requests
from app.utils.util import logger
import jieba
import os
import hashlib
import uuid

WEAVIATE_URL = os.getenv("WEAVIATE_URL", "http://127.0.0.1:8080")
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"

client = weaviate.Client(
    url=WEAVIATE_URL,
    startup_period=10
)

def init_schema():
    """初始化 Weaviate Schema，确保配置最佳"""
    class_obj = {
        "class": "MedicalQAPair",
        "description": "存储医疗问答对",
        "vectorizer": "none",  # 我们自己生成向量 (Ollama)，不让 Weaviate 自动生成
        "vectorIndexConfig": {
            "distance": "cosine"  # 显式指定余弦距离
        },
        "properties": [
            {"name": "question", "dataType": ["text"], "tokenization": "whitespace"},
            {"name": "answer", "dataType": ["text"], "tokenization": "whitespace"},
            {"name": "source_file", "dataType": ["string"]},
            {"name": "combined_text", "dataType": ["text"], "tokenization": "whitespace"}
        ]
    }
    
    try:
        if not client.schema.exists("MedicalQAPair"):
            client.schema.create_class(class_obj)
            print("Schema 'MedicalQAPair' created successfully.")
        else:
            print("Schema 'MedicalQAPair' already exists.")
    except Exception as e:
        logger.error(f"Schema initialization failed: {e}")

init_schema()

def calculate_file_hash(file_path):
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def get_embedding_internal(text, is_query=False):
    prefix = "search_query: " if is_query else "search_document: "
    text_with_prefix = prefix + text

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": EMBEDDING_MODEL, "prompt": text_with_prefix}
        )
        if response.status_code == 200:
            return response.json()["embedding"]
        else:
            logger.error(f"Embedding API Error: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Ollama Error: {e}")
        return None


def get_query_embedding(text):
    return get_embedding_internal(text, is_query=True)


def add_qa_pairs_to_weaviate(qa_pairs, source_filename):
    total_success = 0
    total_count = len(qa_pairs)
    print(f"开始处理文件: {source_filename} (共 {total_count} 条)...")

    with client.batch as batch:
        batch.batch_size = 100

        for item in qa_pairs:
            q = item.get('q', '').strip()
            a = item.get('a', '').strip()

            if not q or not a:
                continue

            raw_text = f"问题：{q}\n回答：{a}"
            seg_text = " ".join(jieba.cut(raw_text))
            vector = get_embedding_internal(raw_text, is_query=False)

            if vector:
                properties = {
                    "question": q,
                    "answer": a,
                    "source_file": source_filename,
                    "combined_text": seg_text
                }
                batch.add_data_object(properties, "MedicalQAPair", vector=vector)
                total_success += 1

                if total_success % 10 == 0:
                    print(f"   ⏳ {source_filename} 已成功入库 {total_success}/{total_count} 条...", end='\r')

    print(f"\n{source_filename} 处理完毕，总共成功存入 {total_success} 条问答对")


def add_texts_to_weaviate(texts, source):
    with client.batch as batch:
        batch.batch_size = 100
        for i, text in enumerate(texts):
            vector = get_embedding_internal(text, is_query=False)
            if vector:
                properties = {
                    "question": "上传文档片段",
                    "answer": text,
                    "source_file": source,
                    "combined_text": " ".join(jieba.cut(text))
                }
                batch.add_data_object(properties, "MedicalQAPair", vector=vector)
    logger.info(f"文件 {source} 已入库 Weaviate")


def delete_vectors_by_source(filename: str):
    try:
        client.batch.delete_objects(
            class_name="MedicalQAPair",
            where={
                "path": ["source_file"],
                "operator": "Equal",
                "valueString": filename
            }
        )
        logger.info(f"已删除 Weaviate 中文件 {filename} 的向量")
        return True
    except Exception as e:
        logger.error(f"删除向量失败: {e}")
        return False


def search_knowledge_base(original_query: str, extracted_keywords: str, limit: int = 3, alpha: float = 0.5,
                          allowed_files: list = None):
    vector = get_embedding_internal(original_query, is_query=True)
    if not vector:
        return []

    class_name = "MedicalQAPair"

    where_filter = None
    if allowed_files is not None:
        if len(allowed_files) == 0: return []
        where_filter = {
            "path": ["source_file"],
            "operator": "ContainsAny",
            "valueString": allowed_files
        }

    try:
        query_builder = (
            client.query
            .get(class_name, ["question", "answer", "source_file", "combined_text"])
            .with_hybrid(
                query=extracted_keywords,
                vector=vector,
                alpha=alpha,
                properties=["combined_text"]
            )
            .with_additional(["score"])
            .with_limit(limit)
        )

        if where_filter:
            query_builder = query_builder.with_where(where_filter)

        response = query_builder.do()
        result_list = []
        raw_data = response.get("data", {}).get("Get", {}).get(class_name, [])

        for item in raw_data:
            q = item.get('question', '')
            a = item.get('answer', '')
            content_text = f"问题：{q}\n回答：{a}" if q and a else a

            raw_score = float(item['_additional']['score'])
            similarity_score = 1 - raw_score

            result_list.append({
                "content": content_text,
                "filename": item.get("source_file", "未知"),
                "score": f"{similarity_score:.4f}"
            })

        return result_list

    except Exception as e:
        logger.error(f"Weaviate 查询失败: {e}")
        return []