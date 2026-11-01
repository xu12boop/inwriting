"""MCP / Function-Calling 工具层。

把"岗位知识检索""技术概念查询""薪资带宽查询"封装为可被大模型自主调用的工具
（智谱 GLM 的 tool_calling 即 OpenAI 兼容的 Function Calling 协议，等价于 MCP 的工具调用范式）。
规划 Agent（planner.py）在面试中可自主决定调用哪一个工具，从而让 AI 从"纯文本生成"
升级为"先检索外部事实、再作答"的可控 Agent。
"""

from app.core.rag import search_jd_top_k
from app.core.config import settings

# ---------------------------------------------------------------------------
# 1) 工具 Schema（GLM / OpenAI 兼容格式）
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_job_knowledge",
            "description": "检索与目标岗位最相关的真实招聘需求（JD）知识。当需要根据岗位要求设计提问、判断候选人匹配度时使用。输入岗位关键词，返回 Top 相关 JD 片段。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "岗位关键词，例如 '后端开发' 或 '数据分析师'"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_tech_concept",
            "description": "查询常见技术概念的标准定义与考察要点（本地知识库，零延迟）。当候选人简历中出现某项技术、面试官需要确认该技术的关键考点时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {"type": "string", "description": "技术概念名称，例如 'Redis' 或 'React' 或 '微服务'"}
                },
                "required": ["concept"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_salary_band",
            "description": "查询指定岗位在主流城市的应届/初级薪资带宽，用于评估候选人期望是否合理。输入岗位名，返回大致薪资区间。",
            "parameters": {
                "type": "object",
                "properties": {
                    "role": {"type": "string", "description": "岗位名称，例如 '前端工程师'"}
                },
                "required": ["role"],
            },
        },
    },
]

# 本地技术概念知识库（演示用，可扩展为向量库）
_TECH_KB = {
    "redis": "Redis 是基于内存的键值型数据库，常用于缓存、会话存储与排行榜。考察要点：缓存穿透/击穿/雪崩、数据结构（String/Hash/ZSet）、持久化（RDB/AOF）、高可用（哨兵/集群）。",
    "react": "React 是 Meta 开源的声明式 UI 库，核心是虚拟 DOM 与组件化。考察要点：Hooks 原理、受控/非受控组件、Diff 算法、Fiber 架构、状态管理（Redux/Zustand）。",
    "vue": "Vue 是渐进式前端框架，3.x 采用 Composition API 与 Proxy 响应式。考察要点：响应式原理、组件通信、虚拟 DOM、Vite 构建、Pinia 状态管理。",
    "mysql": "MySQL 是关系型数据库。考察要点：索引（B+树）、事务与隔离级别、锁机制、慢查询优化、分库分表。",
    "微服务": "微服务是将单体应用拆分为多个独立部署服务的架构。考察要点：服务拆分边界、服务间通信（RPC/REST）、注册发现、分布式事务、链路追踪、网关。",
    "fastapi": "FastAPI 是基于 ASGI 的高性能 Python Web 框架，原生支持异步与类型注解，适合构建流式接口与 AI 服务。考察要点：依赖注入、Pydantic、SSE 流式响应、异步并发。",
    "docker": "Docker 是容器化技术，通过镜像与容器实现环境一致。考察要点：镜像分层、Dockerfile 优化、数据卷、网络模式、与 K8s 的关系。",
    "kafka": "Kafka 是高吞吐分布式消息队列。考察要点：分区与副本、生产者消费者模型、消息有序性、削峰填谷、与 RocketMQ 的区别。",
}

_SALARY_KB = {
    "前端工程师": "应届约 8k-15k/月，1-3 年约 12k-22k/月（一线城市）。",
    "后端工程师": "应届约 9k-16k/月，1-3 年约 13k-24k/月（一线城市）。",
    "数据分析师": "应届约 8k-14k/月，1-3 年约 11k-20k/月（一线城市）。",
    "算法工程师": "应届约 15k-30k/月，1-3 年约 20k-40k/月（一线城市）。",
    "测试工程师": "应届约 7k-12k/月，1-3 年约 10k-18k/月（一线城市）。",
}


def _lookup_tech(concept: str) -> str:
    key = (concept or "").strip().lower()
    for k, v in _TECH_KB.items():
        if k in key or key in k:
            return v
    return "未在本地知识库中找到该概念的详细考点，请基于通用工程知识进行考察。"


def _lookup_salary(role: str) -> str:
    key = (role or "").strip()
    for k, v in _SALARY_KB.items():
        if k in key or key in k:
            return v
    return "暂无该岗位的精确薪资数据，可结合行业平均水平（应届一线城市 8k-16k/月）进行合理性判断。"


# ---------------------------------------------------------------------------
# 2) 工具执行入口
# ---------------------------------------------------------------------------

def execute_tool(name: str, arguments: dict) -> str:
    """根据工具名执行对应逻辑，返回字符串结果（喂回大模型）。"""
    try:
        if name == "search_job_knowledge":
            query = arguments.get("query", "") if isinstance(arguments, dict) else str(arguments)
            docs = search_jd_top_k(query, k=3)
            if not docs:
                return "未检索到相关岗位知识。"
            return "\n".join(f"[JD-{i+1}] {d['job_name']}: {d['snippet']}" for i, d in enumerate(docs))
        if name == "lookup_tech_concept":
            concept = arguments.get("concept", "") if isinstance(arguments, dict) else str(arguments)
            return _lookup_tech(concept)
        if name == "lookup_salary_band":
            role = arguments.get("role", "") if isinstance(arguments, dict) else str(arguments)
            return _lookup_salary(role)
        return f"未知工具: {name}"
    except Exception as e:
        return f"工具执行异常: {e}"
