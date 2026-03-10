import weaviate
import pandas as pd
import requests
import os
import glob
import jieba

WEAVIATE_URL = "http://127.0.0.1:8080"
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
CSV_DATA_DIR = r"/medical_data\测试数据"

client = weaviate.Client(
    url=WEAVIATE_URL,
    startup_period=6
)


def init_schema():
    class_obj = {
        "class": "MedicalQAPair",
        "description": "存储医疗问答对",
        "vectorizer": "none",
        "vectorIndexConfig": {
            "distance": "cosine"
        },
        "properties": [
            {"name": "question", "dataType": ["text"], "tokenization": "whitespace"},
            {"name": "answer", "dataType": ["text"], "tokenization": "whitespace"},
            {"name": "category", "dataType": ["string"]},
            {"name": "source_file", "dataType": ["string"]},
            {"name": "combined_text", "dataType": ["text"], "tokenization": "whitespace"}
        ]
    }

    if not client.schema.exists("MedicalQAPair"):
        client.schema.create_class(class_obj)
        print("Schema 创建成功")
    else:
        print("Schema 'MedicalQAPair' 已存在，保留原有数据...")



def get_embedding(text, is_query=False):
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
            print(f"Embedding Error: {response.text}")
            return None
    except Exception as e:
        print(f"Ollama Error: {e}")
        return None


def ingest_all_csvs():
    if not os.path.exists(CSV_DATA_DIR): return
    # 查找所有 CSV 文件
    csv_files = glob.glob(os.path.join(CSV_DATA_DIR, "*.csv"))

    init_schema()
    total_success = 0

    with client.batch as batch:
        batch.batch_size = 100  # 每100条提交一次
        for file_path in csv_files:
            file_name = os.path.basename(file_path)
            print(f"Processing: {file_name}")
            try:
                try:
                    df = pd.read_csv(file_path, encoding='utf-8')
                except:
                    print("   (UTF-8 读取失败，尝试 GBK...)")
                    df = pd.read_csv(file_path, encoding='gbk')

                df = df.fillna('')
                print(f"   -> 加载了 {len(df)} 行数据")

                for _, row in df.iterrows():
                    # 增强列名兼容性
                    q = str(row.get('question', '')).strip()
                    if not q: q = str(row.get('query', '')).strip()
                    if not q: q = str(row.get('问题', '')).strip()

                    a = str(row.get('answer', '')).strip()
                    if not a: a = str(row.get('response', '')).strip()
                    if not a: a = str(row.get('回答', '')).strip()

                    if not q or not a:
                        continue

                    # 清理数据
                    q = ' '.join(q.split())
                    a = ' '.join(a.split())

                    raw_text = f"问题：{q}\n回答：{a}"
                    seg_text = " ".join(jieba.cut(raw_text))
                    vector = get_embedding(raw_text, is_query=False)

                    if vector:
                        properties = {
                            "question": q,
                            "answer": a,
                            "category": str(row.get('department', '通用')),
                            "source_file": file_name,
                            "combined_text": seg_text
                        }
                        batch.add_data_object(properties, "MedicalQAPair", vector=vector)
                        total_success += 1

                        if total_success % 10 == 0:
                            print(f"   ⏳ 已成功入库 {total_success} 条...", end='\r')

            except Exception as e:
                print(f"Error in {file_name}: {e}")

    print(f"\n\n全部完成，总共成功存入 {total_success} 条问答对")


def delete_vectors_by_filename(filename):
    result = client.batch.delete_objects(
        class_name="MedicalQAPair",
        where={
            "path": ["source_file"],
            "operator": "Equal",
            "valueString": filename
        },
        dry_run=False
    )

    print(f"Weaviate 删除结果: {result}")
    return result


if __name__ == "__main__":
    ingest_all_csvs()