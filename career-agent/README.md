# 大学生职业规划 AI 智能体系统

基于 `Vue 3 + Vite + Element Plus + ECharts` 与 `FastAPI + SQLAlchemy + JWT` 实现的大学生职业规划智能体平台。系统围绕以下闭环提供可运行的 MVP：

岗位要求采集 -> 岗位画像构建 -> 岗位关联图谱 -> 学生信息接入 -> 学生能力画像 -> 人岗匹配分析 -> 职业目标与路径规划 -> 职业规划报告生成 -> 学生执行成长计划 -> 成果回传与阶段复评 -> 更新画像与匹配结果 -> 再次生成优化方案

当前版本以“企业端”演示链路为主，重点支持：
- 学生端一键投递简历
- 企业端查看简历投递箱、候选人画像摘要与成长记录
- 企业端提交阶段复评并驱动新的优化方案

## 项目结构

```text
career-agent/
  Agent/
  backend/
    app/
      api/
      core/
      models/
      repositories/
      schemas/
      services/
      templates/
      static/
      utils/
      main.py
    scripts/
    uploads/
    requirements.txt
    .env.example
  frontend/
    src/
      api/
      assets/
      components/
      layouts/
      router/
      stores/
      views/
      utils/
      App.vue
      main.js
    package.json
    vite.config.js
  sql/
    init.sql
    seed.sql
  README.md
```

## 已实现能力

- 登录鉴权与角色权限控制：管理员、学生、企业
- 岗位画像库 CRUD 与 Mock AI 岗位画像生成
- 岗位关联图谱、岗位发展路径、技能关联展示
- 学生基础信息、附件上传、简历预览中心
- 支持图片简历与文档简历接入、识别、画像生成、可编辑 Word 导出
- 学生能力画像生成：六维评分、标签、优势短板、综合图谱分析
- 人岗匹配分析：总分、维度分、差距项、TopN 推荐岗位
- 职业目标设定与分阶段成长路径生成
- 职业规划报告预览与 PDF 导出
- 成长记录提交、企业复评、重新优化建议
- 学生端一键投递简历到企业知识库目标
- 企业端 HRM 工作台：投递收件箱、候选人筛选、简历预览、复评待办
- 管理端 CRM / 中控仪表盘：账号总览、企业库、MySQL 与 Milvus 状态、系统统计
- 登录页统一登录/注册入口，默认从 `/login` 进入
- 三个端采用不同界面风格：学生端偏成长助手、企业端偏 HRM 后台、管理端偏系统中控

## 默认账号

- 管理员：`admin / admin123`
- 学生：`student01 / student123`
- 企业：`enterprise01 / enterprise123`

说明：
- 系统启动时默认仅保留以上 3 个测试账号，方便按角色分别演示。
- 学生向知识库中的新企业投递简历时，系统仍然会自动创建新的企业账号，默认密码仍为 `enterprise123`。

## 当前界面说明

- 登录页：简洁双栏登录/注册页，集成角色切换与测试账号快速填充，访问根地址会先进入 `/login`
- AI 对话首页：以智能体对话为主，首屏压缩为紧凑对话入口，支持 AI 技能选择，并内嵌附件上传、简历识别和写入档案入口
- 学生中控台：学生端 `/dashboard` 已改为中控台视角，集中展示画像、匹配、路径、报告和快捷入口
- AI 简历优化技能：保留在 Agent 技能中，对话里可直接分析简历并生成可编辑 Word
- 简历预览中心：集中预览原始简历与最新 AI 优化稿，支持上传、写入档案、图像预览和 Word 下载
- 学生档案中心：基础信息、技能清单与学生能力画像已整合到同一页面，学生可直接生成 / 刷新画像
- 学生画像：保留“综合图谱分析页”作为深度分析入口，统一暗色高对比展示
- 学生端界面：已统一补强深色主题下的文字对比度，表单、描述表、标签页、卡片正文与报告预览页可读性更稳定
- 成长模块：优化方案页与成长趋势页已切换为新版可读性更强的深色界面
- 企业端：提供 HRM 后台总览，以及独立的“候选人库”工作台，分别负责招聘总览和候选人筛选
- 管理端：提供 CRM / 中控仪表盘，展示账号、企业库、数据库状态与系统运行情况

## 首次启动方式

### 方式一：直接启动，使用默认 SQLite 自动播种

适合本地快速演示，不依赖 MySQL。

默认会在系统临时目录下创建 SQLite 数据库文件，例如：
- Windows: `%TEMP%\career-agent\career_agent_local.db`

### 1. 启动后端

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端启动后会自动：
- 创建数据表
- 写入管理员、企业、学生、岗位、岗位关系、成长记录等演示数据
- 自动为学生生成画像、匹配结果、成长路径、报告、投递记录与企业复评示例

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认地址：
- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

前端入口说明：
- 打开前端地址后默认先进入登录页：`http://127.0.0.1:5173/login`
- 登录成功后会按角色进入对应工作台

## 已安装依赖后的启动方式

```bash
cd backend
.venv\Scripts\activate
uvicorn app.main:app --reload
```

```bash
cd frontend
npm run dev
```

## API 文档

- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`
- 项目接口文档：[API_DOC.md](D:/python程序/大学生职业规划/career-agent/backend/app/static/API_DOC.md)

## 关键业务服务

后端按模块拆分为以下服务：
- `AuthService`
- `UserService`
- `JobService`
- `JobProfileService`
- `JobGraphService`
- `StudentService`
- `ResumeParserService`
- `StudentProfileService`
- `AbilityScoringService`
- `JobMatchService`
- `CareerPathService`
- `GoalPlanningService`
- `ReportService`
- `PdfExportService`
- `GrowthTrackingService`
- `ReviewService`
- `OptimizationService`
- `LLMService`
- `ResumeDeliveryService`

## 报告与上传文件

- 附件上传目录：`backend/uploads/`
- PDF 报告目录：`backend/uploads/reports/`

## 推荐演示流程

### 学生端流程

1. 使用 `student01 / student123` 登录
2. 进入“AI 对话首页”，直接在智能体页面上传简历附件
3. 执行识别、写入档案、画像生成，或在 AI 对话中启用“AI 简历优化技能”生成最新 Word 版
4. 进入“学生档案中心”“综合图谱分析”查看学生画像
5. 进入“人岗匹配结果”查看推荐岗位和差距项
6. 进入“职业目标设定”“成长路径”生成规划
7. 进入“报告预览”生成职业规划报告
8. 进入“简历预览中心”查看原稿与 AI 优化稿，并下载可编辑 Word 版

### 企业端流程

1. 使用 `enterprise01 / enterprise123` 登录
2. 进入企业端 HRM 后台查看招聘总览
3. 进入“候选人库”页面筛选收到的投递记录、查看候选人画像摘要与简历预览
4. 打开候选人详情查看学生信息、成长情况和岗位来源
5. 在“阶段复评”中填写企业反馈，驱动新的优化方案

### 管理端流程

1. 使用 `admin / admin123` 登录
2. 进入系统管理 / CRM 仪表盘
3. 查看注册账号总量、企业库数量、角色分布和系统统计
4. 查看 MySQL 业务库状态、Milvus 岗位知识库状态和关键配置
5. 在用户管理、系统参数配置中完成后台管理演示

## 说明

- LLM 已提供抽象层和 `mock` 实现，没有真实模型 Key 也可以运行
- 图谱模块当前使用关系表模拟，后续可扩展到 Neo4j
- 向量检索已预留 `VectorSearchService`，当前可接 Milvus / Milvus Lite
- 若使用 MySQL，请确保数据库表结构与当前 ORM 主键类型保持一致；项目 SQL 初始化脚本默认使用 `BIGINT`

## HuggingFace 模型配置（本地缓存 + 懒加载 + 自动降级）

系统使用两个 HuggingFace 模型增强 AI 能力：
- **Embedding 模型**（`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`）：用于意图分类的语义相似度匹配
- **Reranker 模型**（`cross-encoder/ms-marco-MiniLM-L-6-v2`）：用于 RAG 检索结果的重排序

### 设计原则

1. **懒加载**：启动时不加载 HF 模型，首次真正需要时才按需加载
2. **首次自动下载**：本地无模型时，自动从 HuggingFace 下载到项目 `./models/` 目录
3. **后续走本地**：下载完成后始终优先从本地目录加载
4. **失败不崩溃**：模型不可用时自动降级，embedding 降级为规则分类，reranker 降级为原始排序
5. **离线友好**：只要 `models/` 目录存在即可完全离线运行

### 配置项（环境变量）

在 `.env` 文件中配置以下变量：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `ENABLE_INTENT_EMBEDDING` | `true` | 是否启用 embedding 意图分类 |
| `ENABLE_RAG_RERANKER` | `true` | 是否启用 RAG reranker |
| `HF_MODEL_AUTO_DOWNLOAD` | `true` | 首次使用时是否自动从 HF 下载 |
| `HF_MODEL_LOCAL_FILES_ONLY` | `false` | 严格仅从本地加载，禁止联网 |
| `HF_HUB_OFFLINE` | `false` | 离线模式，避免访问 HF Hub |
| `EMBEDDING_MODEL` | `sentence-transformers/...` | Embedding 模型 repo id |
| `RERANKER_MODEL` | `cross-encoder/...` | Reranker 模型 repo id |
| `EMBEDDING_MODEL_DIR` | `./models/embedding` | Embedding 本地存储路径 |
| `RERANKER_MODEL_DIR` | `./models/reranker` | Reranker 本地存储路径 |
| `HF_TOKEN` | *(空)* | HF Token（public 模型无需填写） |
| `MODEL_DOWNLOAD_TIMEOUT` | `120` | 下载超时时间（秒） |

### 使用方式

#### 方式一：首次运行自动下载（推荐）

保持默认配置（`HF_MODEL_AUTO_DOWNLOAD=true`），首次调用相关功能时模型会自动下载到本地。后续启动直接使用本地模型。

#### 方式二：预下载模型（适合部署/演示环境）

```bash
cd backend
python scripts/init_models.py
```

可选参数：
```bash
# 仅下载 embedding
python scripts/init_models.py --embedding-only

# 仅下载 reranker
python scripts/init_models.py --reranker-only

# 自定义模型和路径
python scripts/init_models.py --embedding-repo xxx --reranker-dir ./my-reranker
```

#### 方式三：完全离线运行

```bash
# 1. 在有网络的环境下先执行 init_models.py 下载模型
python scripts/init_models.py

# 2. 将整个 models/ 目录随项目一起拷贝到目标机器

# 3. 在目标机器上设置离线模式
# .env 中添加：
HF_HUB_OFFLINE=true
HF_MODEL_LOCAL_FILES_ONLY=true

# 4. 正常启动，不再需要网络
uvicorn app.main:app --reload
```

#### 方式四：完全禁用 HF 模型

如果不需要 embedding 分类或 reranker 功能：

```bash
# .env 中设置：
ENABLE_INTENT_EMBEDDING=false
ENABLE_RAG_RERANKER=false
```

系统将纯规则方式进行意图分类和检索排序。

### 关于 HF_TOKEN

- **Public 模型**（本项目默认使用的两个模型）：**不需要** HF_TOKEN，匿名即可下载
- **Private/Gated 模型**：需要在 [HuggingFace](https://huggingface.co/settings/tokens) 申请 Token 并填入 `HF_TOKEN`
- Token 不会硬编码在代码中，仅通过环境变量读取

### 打包分发

将 `models/embedding/` 和 `models/reranker/` 目录与项目一起打包，目标机器即可零配置离线运行。
