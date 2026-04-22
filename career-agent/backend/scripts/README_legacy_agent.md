# Agent 目录说明

这个目录专门存放基于 LangChain 的职业规划智能体代码。

当前包含：
- `langchain_career_agent.py`
  - 职业规划智能体主入口
  - 默认改为阿里通义千问兼容模式接入
  - 默认模型为 `qwen-plus`
  - 当未配置真实 API Key 时，会自动回退到本地可运行的规则回答
- `job_kb_milvus.py`
  - 负责岗位 Excel 读取、文本规整、向量化、Milvus/本地向量库检索
- `import_job_excel_to_milvus.py`
  - 负责岗位知识库导入
- `run_agent_chat.py`
  - 适合在 PyCharm 里直接运行的本地对话脚本

## 当前模型配置

- 服务提供方：阿里通义千问
- 默认模型：`qwen-plus`
- 默认兼容地址：`https://dashscope.aliyuncs.com/compatible-mode/v1`
- API Key 环境变量：`DASHSCOPE_API_KEY`

## 知识库说明

如果你的岗位 Excel 已经导入当前向量库，就不需要重复执行导入脚本，直接运行智能体即可。

## PyCharm 运行步骤

1. 用 PyCharm 打开项目根目录 `career-agent`。
2. 将 Python Interpreter 设置为 `backend/.venv/Scripts/python.exe`。
3. 打开 `Run | Edit Configurations...`，新建一个 `Python` 配置。
4. 将 `Script path` 设置为 `Agent/run_agent_chat.py`。
5. 将 `Working directory` 设置为项目根目录 `career-agent`。
6. 在 `Environment variables` 中至少配置以下内容：

```env
DASHSCOPE_API_KEY=你的通义千问API_KEY
LANGCHAIN_PROVIDER=dashscope-compatible
LANGCHAIN_MODEL=qwen-plus
LANGCHAIN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LANGCHAIN_TEMPERATURE=0.2
```

7. 如果你希望脚本直接读取当前知识库，可保留现有 `MILVUS_URI` 配置；如果知识库已导入，则无需再执行导入脚本。
8. 点击运行后，终端会进入对话模式，直接输入问题即可。
9. 如果只想做一次单轮测试，可以在 `Parameters` 中填写：

```bash
--query 给我分析一下数据分析师岗位还缺哪些能力
```

## 可选说明

- `run_agent_chat.py` 支持通过参数覆盖演示身份、专业、目标岗位、优势、短板等上下文。
- 当前后端前台对话页也会复用 `langchain_career_agent.py`，所以这里的模型切换会同步影响系统里的 AI 对话。
