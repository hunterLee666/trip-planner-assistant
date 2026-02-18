# 智能旅行助手

基于LangChain和LangGraph构建的智能旅行规划助手，集成高德地图MCP服务，提供个性化的旅行计划生成。

## ✨ 功能特点

- 🤖 **AI驱动的旅行规划**: 基于LangChain和LangGraph，智能生成详细的多日旅程
- 🗺️ **高德地图集成**: 通过MCP协议接入高德地图服务，支持景点搜索、路线规划、天气查询
- ⚡ **并行处理**: 景点搜索、天气查询、酒店搜索并行执行，响应更快
- 💾 **状态持久化**: 支持PostgreSQL检查点，任务可恢复
- 🔄 **缓存机制**: Redis缓存，减少API调用
- 🔐 **用户认证**: JWT认证支持
- 📊 **观测性**: 结构化日志和性能指标
- 🎨 **现代化前端**: Vue3 + TypeScript + Vite，响应式设计

## 🏗️ 技术栈

### 后端
- **框架**: FastAPI + LangChain + LangGraph
- **Agent框架**: LangGraph状态图工作流
- **数据库**: PostgreSQL + SQLAlchemy + Alembic
- **缓存**: Redis
- **MCP工具**: amap-mcp-server (高德地图)
- **LLM**: OpenAI GPT-4 / 兼容OpenAI API的模型
- **观测性**: LangSmith + structlog

### 前端
- **框架**: Vue 3 + TypeScript
- **构建工具**: Vite
- **UI组件库**: Ant Design Vue
- **地图服务**: 高德地图 JavaScript API
- **HTTP客户端**: Axios

## 📁 项目结构

```
trip-planner-assistant/
├── backend/                    # 后端服务
│   ├── app/
│   │   ├── core/              # 核心框架
│   │   │   ├── exceptions.py  # 异常处理
│   │   │   ├── logging.py     # 结构化日志
│   │   │   └── security.py    # JWT认证
│   │   ├── api/               # API层
│   │   │   ├── main.py        # FastAPI主应用
│   │   │   ├── dependencies.py # 依赖注入
│   │   │   └── routes/        # API路由
│   │   │       ├── trip_v2.py # 旅行规划API
│   │   │       └── auth.py    # 认证API
│   │   ├── agents/            # Agent层
│   │   │   ├── graph.py       # LangGraph状态图
│   │   │   ├── state.py       # 状态定义
│   │   │   ├── tools.py       # 工具定义
│   │   │   └── nodes/         # Agent节点
│   │   │       ├── attraction_node.py
│   │   │       ├── weather_node.py
│   │   │       ├── hotel_node.py
│   │   │       └── planner_node.py
│   │   ├── services/          # 服务层
│   │   │   ├── amap_service.py # 高德地图服务
│   │   │   ├── llm_service.py  # LLM服务
│   │   │   ├── cache_service.py # 缓存服务
│   │   │   └── trip_planning_service.py
│   │   ├── models/            # 数据模型
│   │   │   ├── schemas.py     # Pydantic模型
│   │   │   └── database.py    # 数据库模型
│   │   ├── db/                # 数据库
│   │   │   └── base.py        # SQLAlchemy配置
│   │   └── config.py          # 配置管理
│   ├── tests/                 # 测试
│   ├── docker/                # Docker配置
│   ├── alembic/               # 数据库迁移
│   └── pyproject.toml         # 项目配置
├── frontend/                  # 前端应用
│   ├── src/
│   │   ├── views/             # 页面视图
│   │   ├── services/          # API服务
│   │   └── types/             # TypeScript类型
│   └── package.json
└── README.md
```

## 🚀 快速开始

### 使用Docker（推荐）

```bash
cd backend/docker
docker-compose up -d
```

访问：
- API: http://localhost:8000
- API文档: http://localhost:8000/docs
- 前端: http://localhost:5173

### 本地开发

#### 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -e ".[dev]"

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API keys

# 初始化数据库
alembic upgrade head

# 启动服务
uvicorn app.api.main:app --reload
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

## 📝 使用指南

1. 在首页填写旅行信息（目的地、日期、偏好等）
2. 点击"生成旅行计划"
3. 系统并行处理：
   - 搜索景点
   - 查询天气
   - 搜索酒店
4. 整合结果生成完整行程

## 🔧 API示例

### 生成旅行计划

```bash
curl -X POST http://localhost:8000/api/trip/plan \
  -H "Content-Type: application/json" \
  -d '{
    "city": "北京",
    "start_date": "2025-06-01",
    "end_date": "2025-06-03",
    "travel_days": 3,
    "transportation": "公共交通",
    "accommodation": "经济型酒店",
    "preferences": ["历史文化", "美食"]
  }'
```

## 🧪 测试

```bash
cd backend
pytest
```

## 📄 环境变量

| 变量名 | 说明 | 必需 |
|--------|------|------|
| `AMAP_API_KEY` | 高德地图API Key | ✅ |
| `OPENAI_API_KEY` | OpenAI API Key | ✅ |
| `DATABASE_URL` | PostgreSQL连接URL | ✅ |
| `REDIS_URL` | Redis连接URL | ✅ |
| `SECRET_KEY` | JWT密钥 | ✅ |

完整配置请参见 `.env.example`

## 🤝 贡献指南

欢迎提交Pull Request或Issue！

## 📜 开源协议

MIT License

## 🙏 致谢

- [LangChain](https://github.com/langchain-ai/langchain) - LLM应用框架
- [LangGraph](https://github.com/langchain-ai/langgraph) - 状态图工作流
- [FastAPI](https://fastapi.tiangolo.com/) - Web框架
- [高德地图开放平台](https://lbs.amap.com/) - 地图服务

---

**智能旅行助手** - 让旅行计划变得简单而智能 🌈
