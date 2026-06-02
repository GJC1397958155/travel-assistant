# Travel Assistant Agent

基于 LangGraph 构建的多 Agent 智能旅游助手，融合 RAG 检索增强、MCP 工具调用、长期记忆管理与个性化行程规划能力，实现复杂旅游场景下的智能问答与行程生成。


## 📖 项目简介

Travel Assistant 是一个面向旅游规划场景的大模型 Agent 系统。

系统采用 **Supervisor + Specialist Agents** 协同架构，通过需求解析、知识检索、工具调用、行程规划与结果审查等多个 Agent 协同完成复杂旅游任务。

支持：

- 🤖 多轮对话
- 🗺️ 智能行程规划
- 🌦️ 实时天气查询
- 📍 地点搜索与路线规划
- 🏨 酒店推荐
- 🧠 长短期记忆管理
- 📚 RAG知识增强
- ⚡ SSE流式输出
  
<img width="1920" height="1080" alt="旅游2" src="https://github.com/user-attachments/assets/4cd63048-b8c8-47e7-b3b1-40f2b2b12f9f" />


## ✨ 核心功能

### 1. 多 Agent 协同规划

基于 LangGraph 构建多 Agent Workflow：

- Supervisor Agent
- Requirement Agent
- Information Agent
- Planner Agent
- Reviewer Agent

通过共享状态与条件路由实现复杂任务拆解与协同执行。


### 2. RAG 知识增强

构建旅游领域知识库：

- 景点数据
- 酒店数据
- 旅游攻略
- 交通信息

采用：

- Dense Retrieval
- BM25 Retrieval
- Hybrid Search
- RRF Fusion
- Query Rewrite

提升复杂旅游问题下的召回效果与回答准确性。


### 3. MCP 工具调用

接入真实旅游服务 API：

- Weather API
- Map API
- POI Search API

实现：

- 实时天气查询
- 路线规划
- 景点检索
- 动态行程调整

### 4. 长短期记忆机制

#### 短期记忆

Sliding Window

维护最近对话上下文。

#### 中期记忆

Conversation Summary

压缩历史会话内容。

#### 长期记忆

SQLite

存储：

- 用户画像
- 历史行程
- 出行偏好

实现跨会话个性化服务。


## 🛠️ 技术栈

### 大模型

- Qwen3

### Agent Framework

- LangChain
- LangGraph

### 检索增强

- Chroma
- BM25
- Hybrid Search
- RRF
- Query Rewrite

### 数据存储

- SQLite

### 后端服务

- FastAPI
- SSE

### 工具调用

- MCP


## 🏗️ 系统架构

```text
User Query
      │
      ▼
Supervisor Agent
      │
      ▼
Requirement Agent
      │
      ▼
┌─────────────────────┐
│  RAG + MCP Tools    │
└─────────────────────┘
      │
      ▼
Planner Agent
      │
      ▼
Reviewer Agent
      │
      ▼
Response Generation
```


## 🔄 Workflow

```text
用户输入
    │
    ▼
Supervisor Agent
    │
    ▼
Requirement Agent
    │
    ▼
Information Agent
    │
    ├── RAG Retrieval
    └── MCP Tool Calling
    │
    ▼
Planner Agent
    │
    ▼
Reviewer Agent
    │
    ▼
最终行程输出
```


## 📚 RAG Pipeline

```text
User Query
      │
      ▼
Query Rewrite
      │
      ▼
Hybrid Search
 ┌──────────────┐
 │ Vector Search│
 └──────────────┘
        +
 ┌──────────────┐
 │ BM25 Search  │
 └──────────────┘
      │
      ▼
RRF Fusion
      │
      ▼
Context Construction
      │
      ▼
LLM Generation
```


## 📊 项目评测

### 测试集构建

覆盖旅游场景：

- 城市推荐
- 预算约束
- 老人出游
- 亲子出游
- 雨天重规划
- 多约束组合场景

共计 30+ 条固定测试用例。

### 评测指标

- Recall@5
- Faithfulness
- Answer Relevancy

### 实验结果

| 指标 | Baseline | Hybrid RAG |
|--------|--------|--------|
| Recall@5 | 79% | 91% |
| Faithfulness | 82% | 89% |


## 📂 项目结构

```bash
travel-assistant/
│
├── Travel Planning Assistant/      # 前端项目（React + Vite）
│
├── rag/                            # RAG检索模块
│   ├── embedding.py
│   ├── retrieval.py
│   ├── hybrid_search.py
│   └── ...
│
├── tools/                          # MCP工具封装
│   ├── weather_tool.py
│   ├── map_tool.py
│   ├── place_search.py
│   └── ...
│
├── china_34_travel_rag_kb/         # 旅游知识库数据
│   ├── attractions/
│   ├── hotels/
│   ├── transportation/
│   └── ...
│
├── .travel-memory/                 # 用户长期记忆存储
│
├── evals/                          # RAG评测数据与实验结果
│
├── app.py                          # FastAPI应用入口
├── config.py                       # 项目配置管理
├── state.py                        # LangGraph共享状态定义
├── prompts.py                      # Prompt模板管理
├── itinerary.py                    # 行程规划核心逻辑
├── mcp_server.py                   # MCP服务端实现
│
├── requirements.txt                # Python依赖
├── start-dev.ps1                   # Windows启动脚本
├── start-dev.cmd
│
├── .env                            # 环境变量配置
├── .gitignore
└── README.md
```



## 🚀 快速启动

### 1. 克隆项目

```bash
git clone https://github.com/GJC1397958155/travel-assistant.git

cd travel-assistant
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
OPENAI_API_KEY=xxx
QWEN_API_KEY=xxx
AMAP_API_KEY=xxx
WEATHER_API_KEY=xxx
```

### 4. 启动后端

```bash
uvicorn app.main:app --reload
```

### 5. 启动前端

```bash
npm install

npm run dev
```


## 🎯 项目亮点

- 基于 LangGraph 实现多 Agent 协同架构
- 支持 MCP 标准化工具调用
- 构建 Hybrid RAG 检索链路
- 引入 Query Rewrite 提升召回效果
- 使用 RRF 融合优化多路召回排序
- 实现长短期记忆管理机制
- 支持 SSE 流式响应输出
- 构建固定测试集进行回归评测

---

## 🔮 Future Work

未来计划：

- 引入 Rerank 模型优化排序
- Multi-Query Retrieval
- Parent-Child Retrieval
- Agent Self Reflection
- 多模态旅游规划
- 用户画像增强
- 行程自动导出 PDF


## 🤝 Contributing

欢迎提交：

- Issue
- Pull Request
- Feature Request

共同完善 Travel Assistant Agent。


## ⭐ Star History

如果这个项目对你有所帮助，欢迎点一个 Star ⭐

```
Star 越多，头发越多。
```

---
