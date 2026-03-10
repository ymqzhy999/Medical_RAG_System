import sys
import os

# 必须在导入 app 模块之前添加项目根目录到 sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import statistics
from typing import List, Dict
from app.vector_db import search_knowledge_base
from app.routers.chat import call_llm_sync
from app.prompts import prompt_manager


# 1. 测试数据集 (Golden Dataset)
# 包含问题和期望的关键词/答案方向，用于评估检索质量
TEST_CASES = [
    {
        "query": "糖尿病患者饮食要注意什么？",
        "expected_keywords": ["糖尿病", "饮食", "糖", "碳水"],
    },
    {
        "query": "头痛恶心想吐是怎么回事？",
        "expected_keywords": ["头痛", "恶心", "呕吐"],
    },
    {
        "query": "高血压能吃香蕉吗？",
        "expected_keywords": ["高血压", "香蕉", "钾"],
    },
    {
        "query": "失眠多梦吃什么药好？",
        "expected_keywords": ["失眠", "多梦", "药物", "安神"],
    },
    {
        "query": "胃溃疡的症状有哪些？",
        "expected_keywords": ["胃溃疡", "胃痛", "反酸"],
    }
]

# 2. 实验变量：Alpha 值 (混合检索权重)
# alpha = 1.0 (纯向量检索)
# alpha = 0.0 (纯关键词检索)
# alpha = 0.5 (平衡)
ALPHA_VARIANTS = [0.0, 0.3, 0.5, 0.7, 1.0]


#评估指标：LLM-as-a-Judge
EVAL_PROMPT = """
你是一个公正的评判者。请评估【检索到的资料】与【用户问题】的相关性。

用户问题：{query}

检索到的资料：
{context}

请打分（0-10分）：
- 0分：完全不相关
- 5分：部分相关，提到了一些关键词但没解决核心问题
- 10分：非常相关，资料包含了回答问题所需的信息

只输出一个数字（例如：8），不要输出其他内容。
"""

def evaluate_relevance(query: str, retrieved_docs: List[Dict]) -> float:
    if not retrieved_docs:
        return 0.0
    
    context_text = "\n".join([f"- {d['content']}" for d in retrieved_docs])
    
    # 调用 LLM 进行打分
    try:
        score_str = call_llm_sync(EVAL_PROMPT.format(query=query, context=context_text), "Experiment-Eval")
        # 提取数字
        import re
        match = re.search(r'\d+', score_str)
        if match:
            return float(match.group())
        return 0.0
    except Exception:
        return 0.0

# ==========================================
# 🚀 运行实验
# ==========================================
def run_ablation_study():
    print(f"\n🔬 开始运行消融实验 (Ablation Study)")
    print(f"==================================================")
    print(f"测试用例数: {len(TEST_CASES)}")
    print(f"变量 (Alpha): {ALPHA_VARIANTS}")
    print(f"==================================================\n")

    results_report = {}

    for alpha in ALPHA_VARIANTS:
        print(f"\n🔄 正在测试 Alpha = {alpha} ...")
        scores = []
        latencies = []

        for case in TEST_CASES:
            query = case["query"]
            
            # 1. 模拟 chat.py 中的关键词提取 (简化版，直接用预设或jieba)
            keywords = " ".join(case["expected_keywords"])
            
            t_start = time.time()
            
            # 2. 执行检索
            docs = search_knowledge_base(
                original_query=query,
                extracted_keywords=keywords,
                limit=3,
                alpha=alpha
            )
            
            latency = time.time() - t_start
            latencies.append(latency)

            # 3. 评估相关性
            score = evaluate_relevance(query, docs)
            scores.append(score)
            
            print(f"   - 问题: {query[:10]}... | 得分: {score} | 耗时: {latency:.2f}s")

        avg_score = statistics.mean(scores) if scores else 0
        avg_latency = statistics.mean(latencies) if latencies else 0
        
        results_report[alpha] = {
            "avg_relevance": avg_score,
            "avg_latency": avg_latency
        }

    # ==========================================
    # 📊 实验报告
    # ==========================================
    print(f"\n\n📊 消融实验最终报告")
    print(f"==================================================")
    print(f"{'Alpha':<10} | {'Avg Relevance (0-10)':<25} | {'Avg Latency (s)':<15}")
    print(f"-"*55)
    
    best_alpha = -1
    best_score = -1

    for alpha, metrics in results_report.items():
        print(f"{alpha:<10} | {metrics['avg_relevance']:<25.2f} | {metrics['avg_latency']:<15.4f}")
        
        if metrics['avg_relevance'] > best_score:
            best_score = metrics['avg_relevance']
            best_alpha = alpha

    print(f"==================================================")
    print(f"🏆 最佳 Alpha 参数: {best_alpha} (得分: {best_score:.2f})")
    print(f"💡 结论: 建议将 chat.py 中的 alpha 参数设置为 {best_alpha}")

    # 4. 生成图表
    try:
        plot_results(results_report)
        print(f"\n📊 图表已生成: ablation_study_results.png")
    except Exception as e:
        print(f"\n⚠️ 生成图表失败: {e}")

def plot_results(results: Dict):
    import matplotlib.pyplot as plt
    import pandas as pd
    
    # 设置中文字体 (尝试常见的 Windows 中文字体)
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    alphas = list(results.keys())
    relevances = [results[a]['avg_relevance'] for a in alphas]
    latencies = [results[a]['avg_latency'] for a in alphas]
    
    df = pd.DataFrame({
        'Alpha': alphas,
        'Relevance': relevances,
        'Latency': latencies
    })
    
    fig, ax1 = plt.subplots(figsize=(10, 6))
    
    color = 'tab:blue'
    ax1.set_xlabel('Alpha (0=Keyword, 1=Vector)')
    ax1.set_ylabel('Avg Relevance Score (0-10)', color=color)
    ax1.plot(alphas, relevances, color=color, marker='o', linewidth=2, label='Relevance')
    ax1.tick_params(axis='y', labelcolor=color)
    ax1.set_ylim(0, 10.5)
    
    ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
    
    color = 'tab:red'
    ax2.set_ylabel('Avg Latency (s)', color=color)  # we already handled the x-label with ax1
    ax2.plot(alphas, latencies, color=color, marker='s', linestyle='--', linewidth=2, label='Latency')
    ax2.tick_params(axis='y', labelcolor=color)
    
    plt.title('Ablation Study: Alpha Impact on Retrieval Quality & Latency')
    fig.tight_layout()  # otherwise the right y-label is slightly clipped
    
    plt.grid(True, which='both', linestyle='--', alpha=0.5)
    
    # Add data labels
    for i, txt in enumerate(relevances):
        ax1.annotate(f"{txt:.1f}", (alphas[i], relevances[i]), textcoords="offset points", xytext=(0,10), ha='center')
        
    plt.savefig('ablation_study_results.png', dpi=300)
    plt.close()

if __name__ == "__main__":
    # 确保 app 模块可以被导入
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    run_ablation_study()
