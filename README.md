# 🚀 智聘引擎 InWriting - AI 驱动的全栈模拟面试平台

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)
![Vue](https://img.shields.io/badge/Vue-3.x-brightgreen)
![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)

**智聘引擎 (InWriting)** 是一款面向大学生求职痛点的 AI Native Web 应用。平台致力于解决传统面试缺乏实战经验、简历无人指导的问题，通过集成大语言模型 (LLM)、RAG (检索增强生成)、Multi-Agent (多智能体) 与端侧视觉推理技术，为用户提供从**“简历智能解析”**到**“多角色全真模拟面试”**，再到**“生成式能力评估报告”**的全链路闭环体验。

## ✨ 核心功能亮点 (AI Highlights)

- 📄 **RAG 驱动的简历解析**：摒弃传统的正则提取，基于 Chroma 向量数据库与智谱 LLM，结合岗位 JD 进行检索匹配，并采用「向量召回 (Top-K) + 大模型重排 (Rerank)」双路检索提升匹配精度，自动生成结构化简历画像与匹配度评分。
- 🎭 **多智能体（Multi-Agent）联合面试**：
  - 👨‍💻 **技术面**：深挖底层原理与项目难点。
  - 👩‍💼 **HR 面**：温和考察团队协作与职业规划。
  - 😈 **压力面**：极限施压，测试候选人抗压能力。
- 🧭 **规划型 Agent 编排（MCP / Function Calling 工具集成）**：每轮面试前由「规划 Agent」基于候选人画像与上一轮作答质量，自主决策「深挖 / 切换话题 / 施压 / 收尾」，并经智谱 GLM 的工具调用（兼容 MCP 工具范式）检索岗位知识、技术考点与薪资带宽，使 AI 从「纯文本生成」升级为「先检索事实、再作答」的可控 Agent（见 `app/core/planner.py`、`app/core/tools.py`）。
- 🎥 **端云协同多模态监考**：引入 Google MediaPipe，纯浏览器端实现人脸特征点追踪与视线偏离检测（不上传视频流，保护隐私），将多模态数据转化为 Prompt 参与最终抗压能力的评分。
- ⚡ **丝滑的 SSE 流式对话**：基于 Server-Sent Events 实现打字机效果，并配合前端“蓄水池”算法，确保在任何网络波动下都能呈现完美的逐字渲染。
- 🛡 **AI 安全与可控性**：
  - 内置正则过滤器，拦截恶意 Prompt 注入与越狱。
  - System Prompt 强边界约束，防止 AI 闲聊越界。
  - 防摸鱼机制：无效回答或恶意辱骂将触发一票否决，极低分淘汰。
  - 大模型 429 重试与 Mock 兜底策略，确保演示绝对不翻车。
- 📊 **生成式 UI (Generative UI)**：大模型直接输出结构化 JSON，前端动态渲染 ECharts 能力雷达图与可勾选的待办学习路线卡片。
- 🔍 **可解释的面试策略**：`GET /interview/plan/{id}` 返回规划 Agent 的决策与理由，评委可实时查看「AI 为什么问这一题」。

## 🧠 技术架构设计

系统采用前后端分离架构，重点突出“AI 原生”与“端侧智能”。

### 后端 (Backend)

- **框架**：FastAPI (Python) - 高性能异步框架，完美支持 SSE 流式输出。
- **数据库**：SQLite + SQLAlchemy 2.0 ORM。
- **大模型**：智谱 GLM-4-Flash (极速稳定)，`chat_with_tools()` 支持 Function Calling 多轮工具调用。
- **向量库**：Chroma DB (持久化本地向量存储) + `embedding-3`。
- **Agent 编排**：5 类角色 Agent（解析 / 匹配 / 提问 / 评估 / 报告）+ 1 个规划 Agent（面试控制器），通过结构化 JSON 状态总线交接。
- **鉴权**：JWT (JSON Web Token) + Bcrypt 密码哈希。

### 前端 (Frontend)

- **框架**：Vue 3 (Composition API) + **TypeScript（strict 模式）** + Vite。
- **类型工程**：`tsconfig.json` 全量严格模式、`src/types.ts` 统一业务类型、`npm run type-check`（`vue-tsc --noEmit`）静态校验。
- **UI 库**：Element Plus (深度定制暗黑科技风主题)。
- **数据可视化**：ECharts (动态雷达图渲染)。
- **状态与路由**：Pinia + Vue Router (带全局鉴权守卫)。
- **多模态计算**：MediaPipe Tasks Vision (WebGPU 加速)。

### AI 核心链路

```text
简历上传 → 解析 Agent(结构化画像) → RAG: Top-K 召回 + LLM 重排 + 引用 → 匹配 Agent(0-100 分)
    → 规划 Agent(deepen / switch / pressure / close + 工具调用) → 提问 Agent(SSE 流式)
    → 端侧视觉监考(MediaPipe) → 评估 Agent → 报告 Agent(JSON → 生成式 UI)
```

## 📁 目录结构

```text
inwriting/
├─ app/                     # 后端 (FastAPI)
│  ├─ main.py               # 应用入口、CORS、路由注册
│  ├─ api/routers/          # auth / resume / interview / report
│  ├─ core/                 # config · llm · planner · tools · rag · security
│  ├─ models/  schemas/     # ORM 模型与 Pydantic 契约
│  └─ db/                   # 会话与初始化
├─ frontend/                # 前端 (Vue 3 + TypeScript + Vite)
│  └─ src/
│     ├─ views/             # Login / Home / Interview / Report
│     ├─ api/  stores/  router/  types.ts
│     └─ main.ts
├─ requirements.txt
└─ .env.example
```

## 🛠 本地开发与运行指南

### 1. 环境准备

- Python >= 3.10
- Node.js >= 20.19（Vite 8 的最低要求；推荐 22 LTS）

### 2. 启动后端 (Backend)

```bash
# 在项目根目录执行（根目录内含 app/、frontend/、requirements.txt）
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

pip install -r requirements.txt

# 配置环境变量：复制 .env.example 为 .env，填入智谱 API Key
# Windows: copy .env.example .env
cp .env.example .env

# 启动服务（默认 8001 端口）
python -m uvicorn app.main:app --reload --port 8001
```

### 3. 启动前端 (Frontend)

```bash
cd frontend

npm install          # 已包含 typescript / vue-tsc 等开发依赖
npm run type-check   # 可选：TypeScript 静态类型检查
npm run dev          # 开发服务器，默认 http://localhost:5173
```

> 前端通过 `VITE_API_BASE` 指定后端地址：未设置时默认请求同源 `/api`；本地联调可在 `frontend/.env.local` 写入
> `VITE_API_BASE=http://127.0.0.1:8001`。

### 4. 生产构建

```bash
cd frontend && npm run build      # 产物在 frontend/dist
```

### 5. 关键环境变量（`.env.example`）

| 变量 | 说明 | 必填 |
| --- | --- | --- |
| `ZHIPUAI_API_KEY` | 智谱开放平台 API Key（GLM-4-Flash / embedding-3） | ✅ |
| `SECRET_KEY` | JWT 签名密钥（部署时务必更换） | ✅ |
| `DATABASE_URL` | 数据库连接串（默认 `sqlite:///./inwriting.db`） | ⭕ |
| `CORS_ORIGINS` | 允许的前端源，逗号分隔（默认 `localhost:5173`） | ⭕ |
| `ENABLE_PLANNER` | 是否启用规划 Agent（默认 `true`，异常时自动回退原流程） | ⭕ |

## 👥 团队信息

- **参赛团队**：在写了在写了
- **参赛赛事**：传智杯 AI Web 网页开发挑战赛
- **团队分工**：
  - [徐思博]：全栈开发 / AI 架构设计 / 提示词工程
  - [郝继凯，弓瑞]：前端 UI/UX 设计 / 产品 PRD

---

*Built with ❤ for the AI Web Challenge.*
