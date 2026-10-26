# 🚀 智聘引擎 InWriting - AI 驱动的全栈模拟面试平台

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.10+-green)
![Vue](https://img.shields.io/badge/Vue-3.x-brightgreen)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-teal)

**智聘引擎 (InWriting)** 是一款面向大学生求职痛点的 AI Native Web 应用。平台致力于解决传统面试缺乏实战经验、简历无人指导的问题，通过集成大语言模型 (LLM)、RAG (检索增强生成)、Multi-Agent (多智能体) 与端侧视觉推理技术，为用户提供从**“简历智能解析”**到**“多角色全真模拟面试”**，再到**“生成式能力评估报告”**的全链路闭环体验。

## ✨ 核心功能亮点 (AI Highlights)

- 📄 **RAG 驱动的简历解析**：摒弃传统的正则提取，基于 Chroma 向量数据库与智谱 LLM，结合岗位 JD 进行检索匹配，自动生成结构化简历画像与匹配度评分。
- 🎭 **多智能体（Multi-Agent）联合面试**：
  - 👨‍💻 **技术面**：深挖底层原理与项目难点。
  - 👩‍💼 **HR 面**：温和考察团队协作与职业规划。
  - 😈 **压力面**：极限施压，测试候选人抗压能力。
- 🎥 **端云协同多模态监考**：引入 Google MediaPipe，纯浏览器端实现人脸特征点追踪与视线偏离检测（不上传视频流，保护隐私），将多模态数据转化为 Prompt 参与最终抗压能力的评分。
- ⚡ **丝滑的 SSE 流式对话**：基于 Server-Sent Events 实现打字机效果，并配合前端“蓄水池”算法，确保在任何网络波动下都能呈现完美的逐字渲染。
- 🛡 **工业级 AI 安全与可控性**：
  - 内置正则过滤器，拦截恶意 Prompt 注入与越狱。
  - System Prompt 强边界约束，防止 AI 闲聊越界。
  - 防摸鱼机制：无效回答或恶意辱骂将触发一票否决，极低分淘汰。
  - 大模型 429 重试与 Mock 兜底策略，确保演示绝对不翻车。
- 📊 **生成式 UI (Generative UI)**：大模型直接输出结构化 JSON，前端动态渲染 ECharts 能力雷达图与可勾选的待办学习路线卡片。

## 🧠 技术架构设计

系统采用前后端分离架构，重点突出“AI 原生”与“端侧智能”。

### 后端 (Backend)

- **框架**：FastAPI (Python) - 高性能异步框架，完美支持 SSE 流式输出。
- **数据库**：SQLite + SQLAlchemy 2.0 ORM。
- **大模型**：智谱 GLM-4-Flash (极速稳定)。
- **向量库**：Chroma DB (持久化本地向量存储)。
- **鉴权**：JWT (JSON Web Token) + Bcrypt 密码哈希。

### 前端 (Frontend)

- **框架**：Vue 3 (Composition API) + Vite。
- **UI 库**：Element Plus (深度定制暗黑科技风主题)。
- **数据可视化**：ECharts (动态雷达图渲染)。
- **状态与路由**：Pinia + Vue Router (带全局鉴权守卫)。
- **多模态计算**：MediaPipe Tasks Vision (WebGPU 加速)。

## 🛠 本地开发与运行指南

### 1. 环境准备

- 确保已安装 Python (>= 3.10) 与 Node.js (>= 18)。

### 2. 启动后端 (Backend)

```bash
# 进入项目根目录
cd inwriting

# 创建并激活虚拟环境
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量 (请复制 .env.example 为 .env，并填入你的智谱 API Key)
cp .env.example .env

# 启动服务 (运行在 8001 端口)
python -m uvicorn app.main:app --reload --port 8001
```
