# 通用 RAG 知识库系统 完善与毕业设计计划

> 本文件是**活文档**：每完成一项就把 `[ ]` 改成 `[x]`，并在“当前进度”里记录。
> 定位区分：本项目最终产出是**毕业论文 + 可演示系统**，不是单纯的 demo。
> 因此本计划在原“工程完善”基础上，**额外强化了论文所需的对比实验、评测与写作**。

---

## 0. 当前进度速览（2026-05-31 起记录）

已有基础（代码已实现，已核对）：

- FastAPI 后端（`src/web.py`），Vue3 + Element Plus 前端（`frontend/`）
- 本地 Chroma 向量库（`data/chroma`，collection=`thesis_chunks`）
- SQLite 资料管理（`src/doc_store.py`：documents / document_versions / document_chunks / document_events 四表）
- 文档上传 / 替换 / 删除 + 自动切块索引（`src/doc_index.py`、`src/chunker.py`）
- 本地 `bge-small-zh-v1.5` embedding；DeepSeek 生成回答（`src/rag.py`）
- 前端已实现“展开引用来源”，回答下方可看命中 chunk

本计划新增/改造的重点（相对旧版计划）：

1. **把“可选优化”升级为论文核心对比实验**（检索策略对比，见 §3.4）——这是“做系统”变“做研究”的关键。
2. **增加生成端质量评测**（不仅测检索 hit@k，还测回答是否忠于原文，见 §3.5）。
3. **评测集扩大到 40–60 题并分类**（事实型/跨章节型/无关型，见 §3.3）。
4. **新增“论文写作”工作流**（§10），边做边写。
5. **修正安全整改顺序**（先换 Key → 改环境变量 → 先写 .gitignore 再 git init，见 §5.3）。
6. **阈值用评测集标定，而非拍脑袋**（§3.2）。

进度勾选（已落地的打 x）：

- [x] 工程基础部分文件：`.gitignore`、`requirements.txt`、本 `PLAN.md`
- [x] 阶段一 工程基础其余（README、启动说明）（§2）—— 已写 `README.md`
- [~] 阶段二 可信度与评测（§3）—— 已完成：阈值拒答(§3.2)、评测集+run_eval(§3.3)、top_k 对比(§3.4 部分)、相关度展示(§3.1)；待补：BM25/reranker、chunk 大小对比、生成端 LLM-judge 跑数(§3.5 框架已就绪)
- [ ] 阶段三 资料管理（§4）
- [~] 阶段四 后端结构与安全（§5）—— 已完成：集中配置 `settings.py`(§5.2)、Key 环境变量优先(§5.3.2)；待补：embedding 单例复用(§5.1)、错误处理细化(§5.4)、轮换泄露 Key(§5.3.1，需用户操作)。注：§5.5 经查证 `deepseek-v4-flash/pro` 即官方当前 V4 ID，原代码无误，保持不变
- [ ] 阶段五 测试与展示保障（§6）
- [ ] 论文写作（§10）

> 本轮（2026-06-01）落地：`src/settings.py` 集中配置、阈值拒答（默认 0.9 由评测标定）、
> 前端相关度展示与拒答提示、`eval/` 评测框架（首跑 hit@1=85.7% / hit@3=100% / 拒答准确率=94.4%）、
> `README.md`。前端构建通过、后端导入通过。

---

## 1. 项目目标

把当前“可运行的通用 RAG 演示系统”完善为：

- **稳定、可复现、可演示**的小型 RAG 应用；
- 同时具备**可用数据说明效果**的实验支撑，能直接写进毕业论文。

衡量标准：

- 新机器按 README 能复现启动；
- 回答可溯源、对无关问题会拒答；
- 有一份带数据表格的检索/生成评测报告；
- 论文“系统设计 + 实验分析”两章有素材可写。

---

## 2. 阶段一：补齐工程基础

### 2.1 README.md
让别人能快速理解、安装、启动、演示。内容：简介、技术栈、目录结构、环境要求、后端启动、前端构建、DeepSeek Key 配置、上传问答流程、常见问题、截图。
验收：新用户照 README 能在本机跑起来。

### 2.2 依赖声明（已完成）
- `requirements.txt`（后端，版本对齐当前 .venv）✅
- 说明 Python 版本（当前 3.12.13）
- 前端依赖留在 `frontend/package.json`
验收：新环境装完依赖能启动后端。

### 2.3 .gitignore（已完成，**必须在第一次 git commit 之前建好**）✅
忽略：`.venv/`、`__pycache__/`、`*.pyc`、`frontend/node_modules/`、`frontend/dist/`、`.rag_config.json`、`data/chroma/`、`data/app.db`、`data/material|text|chunks/`、`models/`、日志。
验收：API Key 与大体积运行数据不会进 Git。

### 2.4 统一启动说明
保留 `run_web.bat`、`run_rag.bat`；README 补命令行：`python -m src.pipeline`、`python -m src.launcher`、前端 `npm install && npm run build`。

---

## 3. 阶段二：提升 RAG 回答可信度（论文核心）

### 3.1 引用证据展示（已基本实现，做收尾）
后端 `/api/ask` 已返回命中 chunk、章节、来源、距离；前端已可展开。
收尾项：把“距离”转成更直观的“相关度”显示；拒答时也展示“最接近的片段”。

### 3.2 相似度阈值拒答
- 基于归一化向量（已 `normalize_embeddings=True`），Chroma 默认 L2 距离与余弦单调相关，距离范围约 [0,2]。
- 最佳命中距离超过阈值 → 返回“资料中未检索到足够依据”，不强行生成。
- **阈值做成可配置项（`src/settings.py`），并用评测集里“无关问题”的距离分布来标定，不要写死。**
验收：问无关问题时系统拒答；前端明确提示“依据不足”。

### 3.3 RAG 评测集（扩大 + 分类）
目录：
```
eval/
  questions.json
  run_eval.py
  report.md      # 自动生成
```
`questions.json` 每条含：问题、期望命中章节关键词、期望答案关键词、类型（fact/cross/irrelevant）、是否允许无答案。
**规模：40–60 题**，三类各占一定比例（无关型用于测拒答）。
指标：`hit@1`、`hit@3`、章节命中率、无关问题拒答率。
验收：一键 `python -m eval.run_eval` 生成 `report.md`。

### 3.4 检索策略对比实验（**从“可选”提升为论文主体**）
对同一评测集，跑多组配置，产出对比表（写进论文实验章节）：

| 配置 | hit@1 | hit@3 | 章节命中率 | 拒答准确率 | 备注 |
|---|---|---|---|---|---|
| 纯向量（基线） | | | | | |
| + BM25 混合检索 | | | | | |
| + reranker 重排 | | | | | |
| chunk 大小 256/512/1024 | | | | | |
| top_k = 3/5/8 | | | | | |

实现要点：把可切换的开关接进 `settings.py` / `run_eval.py`，一条命令切换跑表。
验收：至少完成“纯向量 vs 一种增强（混合或 reranker）” + “两种 chunk 大小”的对比，指标有差异并能解释。

### 3.5 生成端质量评测（新增）
检索命中 ≠ 回答正确。补一个轻量生成评测：
- 方式 A：LLM-as-judge，让模型给每条回答的 faithfulness（是否忠于检索片段）/相关性打 1–5 分；
- 方式 B：人工对 30 条回答打分。
验收：报告里同时有“检索质量”和“回答质量”两组数据。

---

## 4. 阶段三：增强资料管理

### 4.1 文档版本历史
利用已有 `document_versions` 表，前端展示历史版本（状态、文件名、索引时间、chunk 数），支持回滚。

### 4.2 索引过程状态
上传后显示：已接收→解析中→切块中→向量化中→完成/失败；失败给可读原因（`document_versions.parse_error` 已存）。

### 4.3 删除策略
区分“从知识库移除（标记删除+删向量，已实现）”与“物理删除文件（`remove_files=True` 已实现，未接前端）”；前端弹窗说明影响范围。

### 4.4 文档预览
展示提取全文、chunk 列表、章节标题/字符数/预览，便于发现乱码、目录误切、章节识别失败。

---

## 5. 阶段四：优化后端结构与安全

### 5.1 复用 embedding 模型
当前检索与索引各自加载模型。改为统一 `EmbeddingService` 单例，启动加载一次，索引/检索共用。
（注意：`web.py` 已用 `state` 持有检索模型，但 `doc_index.index_version` 仍单独 `load_embedding_model`，需打通。）

### 5.2 集中配置 `src/settings.py`
现状：模型名、Chroma 路径、collection、本地模型路径在 `rag.py`/`chunker.py`/`doc_index.py`/`query_db.py` **重复定义**。
集中：根目录、数据目录、Chroma 路径、collection 名、embedding 模型名、本地模型路径、默认 LLM、默认 top_k、相似度阈值。
验收：改路径/模型只改一处。

### 5.3 API Key 安全（**按此顺序执行**）
1. **立刻更换当前 DeepSeek Key**（旧 Key 已以明文存在 `.rag_config.json`，视为已泄露）。
2. 读取优先级改为：环境变量 `DEEPSEEK_API_KEY` 优先，其次本地配置文件。
3. **先写好 `.gitignore`（含 `.rag_config.json`）再执行 `git init`**，否则首次提交会把 Key 带进历史。（.gitignore 已就绪）
4. README 写明安全注意事项；后续可选系统 keyring。

### 5.4 错误处理
用户侧错误（类型不支持/缺 Key/资料为空/依据不足）给中文友好提示；系统侧错误（模型加载/Chroma/DeepSeek 调用失败）记详细日志。

### 5.5 模型名核对（已核对）
`deepseek-v4-flash`/`deepseek-v4-pro` 即 api.deepseek.com 2026 年官方当前模型 ID，默认用 `deepseek-v4-flash`；`deepseek-chat`/`deepseek-reasoner` 是将于 2026-07-24 弃用的遗留别名（映射到 v4），保留为备选。配置集中在 `src/settings.py`。

---

## 6. 阶段五：测试与展示保障

> 注意：当前 `.venv` **未安装 pytest / httpx**，做本阶段前需先 `pip install pytest httpx`（已写入 requirements.txt）。

### 6.1 单元测试
`chunker` 章节识别/目录清理/长段切分/小 chunk 合并；`doc_store` 增删改；`rag` 无 Key/非法模型/空检索。

### 6.2 API 测试
`/api/health`、`/api/documents`(GET/POST)、`/replace`、`DELETE`、`/api/ask`（含拒答路径）。用 FastAPI TestClient。

### 6.3 前端构建检查
每次重要改动后 `cd frontend && npm run build` 必须通过。

### 6.4 Smoke Test `scripts/smoke_test.py`
检查依赖可导入、本地模型存在、Chroma 可读、SQLite 可开、前端 dist 存在、`/api/health` 正常。
验收：演示前一键确认系统可用。

---

## 7. 推荐执行顺序

**P1 立刻做（地基 + 可信度核心 + 论文起步）**
- README、requirements.txt（已完成）、.gitignore（已完成）
- `settings.py` 集中配置
- 相似度阈值拒答
- 评测集 + `run_eval`（先把基线指标跑出来）
- API Key 改环境变量优先

**P2 让项目完整 + 出实验数据**
- 检索策略对比实验（§3.4）→ 出对比表
- 生成端质量评测（§3.5）
- 文档版本历史 / 索引状态
- embedding 模型复用
- 基础测试

**P3 进一步提升**
- 混合检索 / reranker（若 P2 未做满）
- 多轮追问（问题改写）
- keyring 存 Key
- smoke test 自动化
- 打包发布说明

---

## 8. 答辩展示建议

定位：**通用 RAG 知识库问答系统**，论文资料只是当前样例（可换课程资料、制度、手册、企业知识库）。

亮点：通用文档上传建库；支持 docx/pdf/txt/md；bge-small-zh 中文向量；Chroma 检索；DeepSeek 生成；**回答可溯源 + 阈值拒答降低幻觉**；上传/替换/删除/重索引；SQLite 记录文档/版本/chunk；前后端分离可扩展。

演示流程：说定位 → 资料列表 → 上传建库 → 提样例内问题（看回答+展开来源）→ 提无关问题（看拒答）→ 替换资料重索引 → 讲 RAG 流程（解析→切分→embedding→检索→生成）→ 讲扩展方向。

---

## 9. “创新点 / 贡献”准备（答辩必问）

纯通用 RAG = 拼装标准组件，易被问住。**提前备好一个特色答案**，至少选一个坐实：

1. **中文论文场景下不同检索策略的对比分析**（最稳，§3.4 做完即有）；
2. **引用溯源 + 阈值拒答** 组合成的“可信问答”机制及其评测；
3. 针对中文学位论文结构（摘要/章节/参考文献）的**章节感知切块**（`chunker.py` 已有 heading/TOC 处理，可作为工程贡献写）。

---

## 10. 论文写作工作流（新增，与开发并行）

- **现在就能写**：绪论、相关技术（RAG/向量检索/embedding/LLM）、系统设计与实现（代码已定型）。
- **等评测出数后写**：实验与分析（§3.3–3.5 的表格 + 讨论）。
- 建议结构：绪论 → 相关技术 → 需求分析 → 系统设计 → 系统实现 → 实验与评测 → 总结展望。
- 节奏：每完成一个开发阶段，立刻把对应章节初稿补上，避免最后集中赶。

---

## 11. 最小可交付版本（时间紧时的底线）

- README、requirements.txt、.gitignore
- 回答引用来源（已有）+ 相似度阈值拒答
- 40 题评测集 + 一次基线评测报告
- 至少一组检索策略对比（哪怕只是 top_k 或 chunk 大小）
- 一次完整前后端构建验证
- 系统设计章节 + 实验章节初稿

完成以上，即可支撑一次合格的毕业设计答辩。
