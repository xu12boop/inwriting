"""预置岗位 JD 语料库（知识库为空时自动写入）。

为什么需要它：RAG 的"检索依据"要能被人看懂，前提是库里有多条**不同**
的岗位 JD。若库中只有一条（早期冷启动写入的占位文本），无论用户填什么
目标岗位都会命中同一条，检索就退化成了摆设——引用看起来像在溯源，
实际什么也没证明。

这里放 6 条通用岗位要求（不含任何真实公司信息），覆盖本作品面向的
主要求职方向。写入是 upsert + 岗位名做 id，重复执行无副作用。
"""

SEED_JDS: list[tuple[str, str]] = [    (
        "AI 应用开发工程师",
        "【AI 应用开发工程师】\n"
        "1. 熟练使用 Python，掌握 FastAPI / Flask 等 Web 框架；\n"
        "2. 有大模型 API（GLM / 通义 / OpenAI）接入经验，理解 Function Calling；\n"
        "3. 了解 RAG 链路：文档切分、向量检索、重排、引用溯源；\n"
        "4. 了解向量数据库（Chroma / Milvus / FAISS）的基本用法；\n"
        "5. 能独立完成接口设计、联调与部署，具备工程化意识。",
    ),
    (
        "后端开发工程师（Python）",
        "【后端开发工程师（Python）】\n"
        "1. 扎实的 Python 基础，熟悉面向对象与常见设计模式；\n"
        "2. 熟悉 FastAPI / Django，能设计 RESTful 接口；\n"
        "3. 熟练使用 MySQL，了解索引与慢查询优化；\n"
        "4. 了解 Redis 缓存与消息队列（Kafka / RabbitMQ）；\n"
        "5. 有接口性能优化或高并发场景经验者优先。",
    ),
    (
        "前端开发工程师",
        "【前端开发工程师】\n"
        "1. 熟练掌握 Vue3 或 React，理解组件化与响应式原理；\n"
        "2. 熟练使用 TypeScript，能维护 strict 模式下的类型定义；\n"
        "3. 熟悉 Vite / Webpack 工程化配置与构建优化；\n"
        "4. 有组件库封装、性能优化（首屏、包体积）经验；\n"
        "5. 了解浏览器渲染机制与常见兼容性问题。",
    ),
    (
        "数据分析工程师",
        "【数据分析工程师】\n"
        "1. 熟练编写 SQL，能独立完成多表关联与窗口函数取数；\n"
        "2. 熟悉 Pandas / NumPy，具备数据清洗与特征处理能力；\n"
        "3. 了解数据仓库分层与 ETL 流程；\n"
        "4. 能独立搭建指标体系，输出可落地的分析结论；\n"
        "5. 有 ECharts / Tableau 等可视化经验者优先。",
    ),
    (
        "算法工程师（NLP）",
        "【算法工程师（NLP）】\n"
        "1. 熟悉 Transformer / BERT 等预训练模型原理；\n"
        "2. 熟练使用 PyTorch，能复现论文中的基础实验；\n"
        "3. 有文本分类、信息抽取或语义检索的实际项目经验；\n"
        "4. 了解向量召回与重排（bge / reranker）的工程落地；\n"
        "5. 有竞赛获奖或论文发表者优先。",
    ),
    (
        "测试开发工程师",
        "【测试开发工程师】\n"
        "1. 熟悉 Python 或 Java，能编写可维护的自动化脚本；\n"
        "2. 了解接口自动化框架（Pytest / Requests / RestAssured）；\n"
        "3. 了解性能测试工具（JMeter / Locust）与指标口径；\n"
        "4. 有 CI/CD 流水线搭建经验，理解质量门禁；\n"
        "5. 具备定位线上问题的排查思路。",
    ),
]


def _purge_placeholder(collection) -> int:
    """清掉早期冷启动写入的占位 JD（形如「【岗位】要求：熟练掌握 Python…」）。

    这类占位条目的内容是模板，不是真实岗位要求；留在库里会污染检索，
    让"检索依据"引用一条没有信息量的文本。
    """
    removed = 0
    try:
        data = collection.get()
        ids, docs = data.get("ids") or [], data.get("documents") or []
        for cid, doc in zip(ids, docs):
            text = doc or ""
            if "要求：熟练掌握 Python" in text and len(text) < 120:
                collection.delete(ids=[cid])
                removed += 1
    except Exception as e:  # noqa: BLE001
        print(f"⚠️  清理占位 JD 失败: {e}")
    return removed


def seed_if_empty(collection, embed_fn, min_count: int = 3) -> int:
    """库中条目过少时写入预置 JD，返回写入条数。

    用 min_count 而不是 count==0：早期版本冷启动只写了一条占位文本，
    count 已经是 1，若只判断"为空"就永远不会补真实语料。
    """
    try:
        if collection.count() >= min_count:
            return 0
    except Exception:
        return 0

    removed = _purge_placeholder(collection)
    if removed:
        print(f"🧹 已清理 {removed} 条占位 JD")

    written = 0
    for job_name, jd_text in SEED_JDS:
        try:
            emb = embed_fn(jd_text)
            if not emb:
                continue
            collection.upsert(
                embeddings=[emb],
                documents=[jd_text],
                metadatas=[{"job_name": job_name}],
                ids=[job_name],
            )
            written += 1
        except Exception as e:  # noqa: BLE001
            print(f"⚠️  预置 JD 失败 {job_name}: {e}")
    if written:
        print(f"📚 已预置 {written} 条岗位 JD 到向量库")
    return written
