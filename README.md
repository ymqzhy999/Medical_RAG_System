
---
# 基于 RAG 的智能医疗问答系统 (Medical RAG System)

本系统是一个完全本地化部署、基于**检索增强生成 (Retrieval-Augmented Generation, RAG)** 技术的智能医疗问答平台。系统利用开源大语言模型提供极具同理心和专业度的医疗咨询服务，并通过严格的多步骤 Prompt 链路与混合检索技术，有效解决了大模型在医疗领域的“幻觉”与“张冠李戴”问题。

---

## 整体系统架构

系统采用经典的前后端分离与双数据库架构，确保数据的安全性与高并发处理能力：

* **表现层 (前端)**：原生 HTML/CSS/JS 构建，前端代码采用模块化（Modules）与控制器（Controllers）架构，支持 Markdown 实时渲染与 SSE (Server-Sent Events) 打字机流式输出。
* **业务层 (后端)**：基于 `FastAPI` 异步框架，提供高性能的 RESTful API，涵盖鉴权、会话管理、后台看板及知识库上传等功能。
* **模型驱动层**：基于 `Ollama` 本地引擎。
* **文本生成**：`Gemma3:4b` (负责意图识别、逻辑推理与对话生成)
* **向量表征**：`nomic-embed-text` (负责文档切片与用户问题的 Embedding 化)


* **数据持久层**：
* **结构化数据**：`SQLite` (`data/medical.db`)，存储用户、会话、聊天记录与文档元数据。
* **非结构化/向量数据**：`Weaviate`，存储医疗文本切片、分词索引与高维向量。



---

## 数据集说明

知识库兼容两种主流格式的医疗数据，满足不同维度的知识补充需求：

1. **结构化问答对 (CSV)**：
* **来源**：如 `cmedqa2` 等开源中文医疗问答数据集。
* **处理**：智能匹配文件中的 `question` 与 `answer` 列，拼接成固定格式后进行分词与向量化入库。


2. **非结构化长文本 (Markdown / TXT)**：
* **来源**：各类专业医学指南（如存放于 `MedicalGuide-PDF_and_Markdown` 中的文献）。
* **处理**：采用**带重叠的滑动窗口切片算法**，按固定长度切割，消除排版冗余，保障上下文语义不断裂。



---

## 核心算法与机制

1. **滑动窗口文本切片 (Sliding Window Chunking)**
针对 MD 长文本，按照 **500** 字符进行截断，同时保留 **50** 字符的上下文重叠（Overlap），避免完整的医学概念被生硬切断。
2. **混合检索算法 (Hybrid Search)**
在召回阶段，不单纯依赖向量距离。系统在 Weaviate 中设定混合权重，将 **BM25 关键词倒排索引匹配 (基于 Jieba 中文分词)** 与 **高维向量余弦相似度匹配** 结合，极大提升了专有名词的召回精准度。
3. **多步安全与过滤工作流 (LLM Prompt Chain)**
* **安全检测**：拦截违规或极端危险输入。
* **意图分类**：区分“医疗咨询”与“日常闲聊”，闲聊直接绕过 RAG 库，节省算力。
* **查询优化**：大模型将用户的大白话提炼为“症状”与“病因”关键词，喂给检索算法。
* **资料清洗**：大模型充当“判官”，剔除严重程度不符、主题偏离的无用检索结果。
* **最终生成**：限制大模型仅参考留存的优质资料输出【病情分析】、【用药建议】与【生活护理】，并通过 Prompt 严格封印 LaTeX 乱码输出，杜绝“患者混淆”。



---

## 项目目录结构

```text
Medical_RAG_System/
├── app/                            # 后端核心业务代码目录
│   ├── medical_data/               # 本地原始医疗数据集 (cmedqa2, 医学指南等)
│   ├── routers/                    # 路由分发层 (API 控制器)
│   │   ├── admin.py                # 后台管理、数据看板与知识库上传接口
│   │   ├── auth.py                 # 用户鉴权与登录注册接口
│   │   ├── chat.py                 # RAG 对话核心链路与流式输出接口
│   │   └── knowledge.py            # 知识库列表检索与操作接口
│   ├── services/                   # 独立业务服务逻辑层
│   ├── utils/                      # 通用工具包
│   │   ├── experiment.py           # 消融实验与参数对比测试脚本
│   │   ├── scan_files.py           # 离线文件扫描与元数据同步 SQLite 工具
│   │   ├── util.py                 # 日志配置与系统基础辅助工具
│   │   └── vector_db.py            # 核心：Weaviate 向量库驱动与混合检索引擎
│   ├── 离线脚本/                   # 知识库初始化专用的刷库工具
│   │   ├── ingest_csv.py           # 结构化问答对(CSV)批量入库脚本
│   │   └── ingest_md.py            # 非结构化长文本(MD)切片入库脚本
│   ├── database.py                 # SQLite 数据库连接配置
│   ├── docker-compose-weaviate.yml # Weaviate 向量库一键部署容器编排文件
│   ├── main.py                     # FastAPI 应用实例及全局路由挂载
│   ├── models.py                   # SQLAlchemy 数据表模型 (ORM)
│   ├── prompts.json & .py          # 核心 RAG 提示词模板集中管理库
│   └── schemas.py                  # Pydantic 数据请求验证模型
├── data/                           # 动态生成的数据持久化目录
│   └── medical.db                  # 系统结构化关系型数据库文件
├── static/                         # 前端静态资源目录
│   ├── avatars/                    # 用户默认及上传的头像
│   ├── css/                        # 页面样式表 (admin.css, chat.css等)
│   ├── images/                     # 静态图片资源
│   └── js/                         # 模块化前端脚本
│       ├── controllers/            # 页面级业务逻辑 (admin, chat, profile, session)
│       ├── modules/                # 封装的功能模块 (api, state, ui, utils)
│       └── main.js                 # 前端全局入口文件
├── templates/                      # 前端 HTML 模板目录
│   ├── admin.html                  # 管理员数据看板与知识库操作大盘
│   ├── chat.html                   # 核心医患对话与流式渲染交互界面
│   └── index.html                  # 登录与注册主页
├── .gitignore                      # Git 提交忽略配置文件
├── README.md                       # 项目说明文档
├── requirements.txt                # Python 依赖包清单
└── run.py                          # 项目启动主入口脚本

```

