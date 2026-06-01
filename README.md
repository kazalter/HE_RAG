# 通用 RAG 知识库问答系统

一个本地优先的中文**通用** RAG（检索增强生成）知识库问答系统：上传任意文档自动建库，提问时先在本地向量库检索相关片段，再交给 DeepSeek 大模型基于片段生成**可溯源**的回答，并对**无关问题阈值拒答**以降低幻觉。

系统与领域无关——可用于课程资料、规章制度、产品手册、企业知识库等任意中文文档。仓库内置的样例资料恰好是一份《院系教学信息管理系统》毕业论文，仅作演示与评测之用，替换为你自己的资料即可。

## 功能特性

- 文档上传 / 替换 / 删除，自动解析、章节感知切块、向量化入库
- 支持 `.docx / .pdf / .txt / .md`
- 本地 `bge-small-zh-v1.5` 中文 embedding，离线可用
- 本地 Chroma 向量库 + SQLite 文档/版本/chunk 管理
- 回答可溯源：展开可见命中片段、所属章节、相关度、距离
- 相似度阈值拒答：检索不到足够依据时直接拒答，不强行生成
- 检索/生成两端评测脚本，一键产出对比报告

## 技术栈

| 层 | 选型 |
|---|---|
| 后端 | FastAPI + Uvicorn |
| 前端 | Vue 3 + Element Plus + Vite |
| 向量库 | Chroma（本地持久化） |
| Embedding | sentence-transformers · BAAI/bge-small-zh-v1.5（本地权重） |
| 元数据 | SQLite（documents / document_versions / document_chunks / document_events） |
| 生成模型 | DeepSeek（OpenAI 兼容协议） |

## 目录结构

```
rag_thesis_demo/
├─ src/                 后端
│  ├─ settings.py       集中配置（路径/模型/top_k/阈值），改一处即可
│  ├─ config.py         DeepSeek Key 读写（环境变量优先）
│  ├─ web.py            FastAPI 应用与接口
│  ├─ rag.py            检索 + 生成 + 阈值拒答
│  ├─ chunker.py        文本提取与章节感知切块（独立脚本）
│  ├─ doc_index.py      上传/替换/删除的索引流程
│  ├─ doc_store.py      SQLite 资料管理
│  ├─ query_db.py       命令行检索调试工具
│  ├─ pipeline.py       一键建库 + 启动
│  └─ launcher.py       Web 启动入口
├─ eval/                评测
│  ├─ questions.json    评测题库（fact / cross / irrelevant）
│  ├─ run_eval.py       评测脚本，产出 report.md
│  └─ report.md         自动生成的评测报告
├─ frontend/            Vue 前端（构建产物在 frontend/dist）
├─ data/                运行期数据（chroma / app.db / material / text / chunks）
├─ models/              本地 embedding 权重（bge-small-zh-v1.5）
└─ requirements.txt
```

## 环境要求

- Windows（开发环境；其他平台理论可用，启动脚本为 .bat）
- Python 3.12（开发使用 3.12.13）
- Node.js 18+（仅构建前端时需要）
- 本地 embedding 权重：将 `BAAI/bge-small-zh-v1.5` 放在 `models/bge-small-zh-v1.5/`（离线运行必需）

## 快速开始

### 1. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
```

### 2. 配置 DeepSeek API Key

读取优先级：**环境变量 `DEEPSEEK_API_KEY` > 本地 `.rag_config.json`**。推荐用环境变量，Key 不落盘：

```powershell
$env:DEEPSEEK_API_KEY = "sk-你的key"
```

也可以在前端「设置与资料」里保存（会写入 `.rag_config.json`，该文件已被 `.gitignore` 忽略）。

### 3. 构建前端

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 4. 启动

```powershell
# 方式一：一键建库 + 构建前端 + 启动 Web
python -m src.pipeline

# 方式二：仅启动 Web（前端已构建、向量库已存在）
python -m src.launcher

# 方式三：Windows 双击
run_web.bat
```

启动后访问 `http://127.0.0.1:7860`。

## 使用流程

1. 在「设置与资料」中上传一份 `.docx/.pdf/.txt/.md` 文档，系统自动切块入库。
2. 在对话框提问资料内的问题 → 得到回答，可展开「引用来源」查看命中片段、章节、相关度。
3. 提问与资料无关的问题 → 系统判定依据不足并**拒答**，同时给出最接近的片段供参考。
4. 需要更新资料时「替换」，旧向量会自动删除并重建。

## 评测

检索评测无需 API Key；生成评测需要 Key。在项目根目录运行：

```powershell
# 检索评测（hit@1 / hit@3 / 章节命中率 / 拒答准确率）
python -m eval.run_eval

# top_k 对比实验
python -m eval.run_eval --compare-top-k 1,3,5,8

# 加生成质量评测（回答关键词覆盖率）
python -m eval.run_eval --generate

# 再加 LLM-as-judge 忠实度打分
python -m eval.run_eval --generate --judge
```

报告写入 `eval/report.md`，同时包含「最佳命中距离分布」用于标定拒答阈值。
更换资料后，请把 `eval/questions.json` 换成对应资料的问题并重跑评测重新标定阈值。

## 配置项

集中在 `src/settings.py`，也支持运行期覆盖（环境变量优先于 `.rag_config.json`）：

| 项 | 环境变量 | 配置键 | 默认 |
|---|---|---|---|
| 默认检索条数 | `RAG_TOP_K` | `top_k` | 3 |
| 拒答距离阈值 | `RAG_SIMILARITY_DISTANCE_THRESHOLD` | `similarity_distance_threshold` | 0.865 |
| 默认生成模型 | `RAG_DEFAULT_LLM_MODEL` | `default_llm_model` | `deepseek-v4-flash` |

## 安全注意事项

- **不要把 API Key 提交进 Git。** `.rag_config.json` 已在 `.gitignore` 中；优先用环境变量。
- 如果某个 Key 曾以明文出现在配置文件或被提交过，应视为已泄露，**立刻在 DeepSeek 控制台轮换**。
- 首次 `git init` 前请确认 `.gitignore` 已就位，避免把 Key 与大体积运行数据带进历史。

## 常见问题

- **回答"资料中未检索到足够依据"**：属于正常拒答（相关度低于阈值）。可上传相关资料，或在 `settings.py` 调整阈值。
- **DeepSeek 调用 404 / 模型不存在**：直连 `api.deepseek.com` 请使用官方 V4 模型 `deepseek-v4-flash` / `deepseek-v4-pro`；`deepseek-chat` / `deepseek-reasoner` 是遗留别名（将于 2026-07-24 弃用，映射到 v4-flash）。
- **首页提示"前端还没有构建"**：先 `cd frontend && npm run build` 再启动后端。
- **加载 embedding 模型失败**：确认 `models/bge-small-zh-v1.5/` 下有完整权重（离线运行必需）。
