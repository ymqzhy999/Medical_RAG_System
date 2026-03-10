import weaviate
import requests
import os
import glob
import jieba

WEAVIATE_URL = "http://127.0.0.1:8080"
OLLAMA_API_URL = "http://127.0.0.1:11434/api/embeddings"
EMBEDDING_MODEL = "nomic-embed-text"
MD_DATA_DIR = r"/medical_data/MedicalGuide-PDF_and_Markdown/骨科指南60/Markdown"

CHUNK_SIZE = 500  # 文本切片长度
CHUNK_OVERLAP = 50  # 切片重叠长度，防止关键信息被截断

client = weaviate.Client(
    url=WEAVIATE_URL,
    startup_period=6
)


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


def chunk_text(text, chunk_size, overlap):
    """将长文本切分为带有重叠的短片段"""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def ingest_all_mds():
    if not os.path.exists(MD_DATA_DIR):
        print(f"目录不存在: {MD_DATA_DIR}")
        return

    # 查找所有 MD 文件
    md_files = glob.glob(os.path.join(MD_DATA_DIR, "*.md"))
    if not md_files:
        print("未找到任何 .md 文件。")
        return

    # 检查 Schema 是否存在 (不执行删除)
    if not client.schema.exists("MedicalQAPair"):
        print("警告：MedicalQAPair Schema 不存在。请先运行 init_schema 逻辑。")
        return

    total_success = 0

    with client.batch as batch:
        batch.batch_size = 100  # 每100条提交一次
        for file_path in md_files:
            file_name = os.path.basename(file_path)
            print(f"\nProcessing: {file_name}")

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                print(f"   (UTF-8 读取失败，尝试 GBK...)")
                try:
                    with open(file_path, 'r', encoding='gbk') as f:
                        content = f.read()
                except Exception as e:
                    print(f"   文件读取失败: {e}")
                    continue

            # 移除过多的空白字符
            content = ' '.join(content.split())
            if not content:
                continue

            # 对长文本进行切片
            chunks = chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
            print(f"   -> 文本被切分为 {len(chunks)} 个片段")

            for chunk in chunks:
                # 针对非结构化长文本的适配逻辑：
                # question 固定标识为指南片段，answer 存放实际片段内容
                q_placeholder = "医学指南文档片段"

                # 分词用于 BM25 检索
                seg_text = " ".join(jieba.cut(chunk))
                # 向量化 (仅针对实际内容)
                vector = get_embedding(chunk, is_query=False)

                if vector:
                    properties = {
                        "question": q_placeholder,
                        "answer": chunk,  # 核心内容存放在 answer 字段
                        "category": "医学指南",
                        "source_file": file_name,
                        "combined_text": seg_text
                    }
                    batch.add_data_object(properties, "MedicalQAPair", vector=vector)
                    total_success += 1

                    if total_success % 10 == 0:
                        print(f"   ⏳ 已成功入库 {total_success} 个片段...", end='\r')

    print(f"\n\n全部完成，总共成功存入 {total_success} 个 MD 文档片段")


if __name__ == "__main__":
    ingest_all_mds()