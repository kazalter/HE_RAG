# 通用 RAG 知识库系统 完善计划（作品集项目）

> 本文件是**活文档**：每完成一项就把 `[ ]` 改成 `[x]`，并在“当前进度”里记录。
> 定位：**作品集 / 简历展示项目**——一个做得扎实、能拿出去给人看的通用 RAG 知识库问答系统。
> 衡量标准不是论文，而是：**别人能照 README 快速跑起来、代码体现工程判断、有一张数据能说明效果**。

---

## 0. 当前进度速览（2026-05-31 起记录）

已有基础（代码已实现，已核对）：

- FastAPI 后端（`src/web.py`），Vue3 + Element Plus 前端（`frontend/`）
- 本地 Chroma 向量库（`data/chroma`，collection=`thesis_chunks`）
- SQLite 资料管理（`src/doc_store.py`：documents / document_versions / document_chunks / document_events 四表）
- 文档上传 / 替换 / 删除 + 自动切块索引（`src/doc_index.py`、`src/chunker.py`）
- 本地 `bge-small-zh-v1.5` embedding；DeepSeek 生成回答（`src/rag.py`）
- 前端已实现“展开引用来源”，回答下方可看命中 chunk

进度勾选（已落地的打 x）：

- [x] 工程基础部分文件：`.gitignore`、`requirements.txt`、本 `PLAN.md`
- [x] 阶段一 工程基础其余（README、启动说明）（§2）—— 已写 `README.md`
- [~] 阶段二 回答可信度（§3）—— 已完成：阈值拒答(§3.2)、评测集+run_eval(§3.3)、top_k 对比(§3.4 部分)、相关度展示(§3.1)；可选未做：BM25/reranker、chunk 大小对比、生成端质量评测(§3.5)
- [ ] 阶段三 资料管理（§4）
- [~] 阶段四 后端结构与安全（§5）—— 已完成：集中配置 `settings.py`(§5.2)、Key 环境变量优先(§5.3.2)；待补：embedding 单例复用(§5.1)、错误处理细化(§5.4)、轮换泄露 Key(§5.3.1，需用户操作)。注：§5.5 经查证 `deepseek-v4-flash/pro` 即官方当前 V4 ID，原代码无误，保持不变
- [ ] 阶段五 测试与质量保障（§6）

> 本轮（2026-06-01）落地：`src/settings.py` 集中配置、阈值拒答（默认 0.865 由评测标定）、
> 前端相关度展示与拒答提示、`eval/` 评测框架（首跑 hit@1=85.7% / hit@3=100% / 拒答准确率=100%）、
> `README.md`。前端构建通过、后端导入通过。

---

## 1. 项目目标

把当前“可运行的通用 RAG 演示系统”完善为一个**适合放进作品集的成熟小型项目**：

- **稳定、可复现**：新机器照 README 能跑起来；
- **代码体现工程判断**：集中配置、错误处理、Key 安全、有测试；
- **效果可量化**：回答可溯源、对无关问题会拒答，并有一份带数据的评测报告（亮点）。

衡量标准：

- 新机器按 README 能复现启动；
- 回答可溯源、对无关问题会拒答；
- README 里有一张能说明检索/拒答效果的数据表；
- 代码有基础测试，关键逻辑（阈值拒答）有回归保护。

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

## 3. 阶段二：提升 RAG 回答可信度（作品集亮点）

### 3.1 引用证据展示（已基本实现，做收尾）
后端 `/api/ask` 已返回命中 chunk、章节、来源、距离；前端已可展开。
收尾项：把“距离”转成更直观的“相关度”显示；拒答时也展示“最接近的片段”。

### 3.2 相似度阈值拒答（已实现）
- 基于归一化向量（已 `normalize_embeddings=True`），Chroma 默认 L2 距离与余弦单调相关，距离范围约 [0,2]。
- 最佳命中距离超过阈值 → 返回“资料中未检索到足够依据”，不强行生成。
- 阈值是可配置项（`src/settings.py`），用评测集距离分布标定（当前 0.865）。
验收：问无关问题时系统拒答；前端明确提示“依据不足”。

### 3.3 RAG 评测集
目录：
```
eval/
  questions.json
  run_eval.py
  report.md      # 自动生成
```
`questions.json` 每条含：问题、期望命中章节关键词、期望答案关键词、类型（fact/cross/irrelevant）、是否允许无答案。
**规模够用即可**（当前样例集已能验证质量；不必为撑场面凑题量）。
指标：`hit@1`、`hit@3`、章节命中率、无关问题拒答率。
验收：一键 `python -m eval.run_eval` 生成 `report.md`。

### 3.4 检索策略对比（**可选，作品集加分项**）
对同一评测集跑多组配置，产出一张对比表放进 README——这对作品集是很好的“我懂得权衡”信号。但**按工程调优来做，不必追学术严谨**：

| 配置 | hit@1 | hit@3 | 章节命中率 | 拒答准确率 | 备注 |
|---|---|---|---|---|---|
| 纯向量（基线，已有数据） | | | | | |
| top_k = 3/5/8（已可跑） | | | | | |
| + BM25 混合检索（可选） | | | | | |
| + reranker 重排（可选） | | | | | |
| chunk 大小对比（可选） | | | | | |

实现要点：开关接进 `settings.py` / `run_eval.py`，一条命令切换跑表。
建议底线：把已有的 top_k 对比整理成表写进 README 即可；BM25/reranker 视精力可选。

### 3.5 生成端质量评测（可选）
检索命中 ≠ 回答正确。若有精力可补一个轻量生成评测（LLM-as-judge 给 faithfulness 打分，或人工抽查 30 条）。作品集非必需。

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

### 5.2 集中配置 `src/settings.py`（已完成）
模型名、Chroma 路径、collection、本地模型路径、默认 LLM、默认 top_k、相似度阈值统一在 `settings.py`。
验收：改路径/模型只改一处。

### 5.3 API Key 安全（**按此顺序执行**）
1. **立刻更换当前 DeepSeek Key**（旧 Key 已以明文存在 `.rag_config.json`，视为已泄露）。
2. 读取优先级改为：环境变量 `DEEPSEEK_API_KEY` 优先，其次本地配置文件。（已实现）
3. **先写好 `.gitignore`（含 `.rag_config.json`）再执行 `git init`**，否则首次提交会把 Key 带进历史。（.gitignore 已就绪）
4. README 写明安全注意事项；后续可选系统 keyring。

### 5.4 错误处理
用户侧错误（类型不支持/缺 Key/资料为空/依据不足）给中文友好提示；系统侧错误（模型加载/Chroma/DeepSeek 调用失败）记详细日志。

### 5.5 模型名核对（已核对）
`deepseek-v4-flash`/`deepseek-v4-pro` 即 api.deepseek.com 2026 年官方当前模型 ID，默认用 `deepseek-v4-flash`；`deepseek-chat`/`deepseek-reasoner` 是将于 2026-07-24 弃用的遗留别名（映射到 v4），保留为备选。配置集中在 `src/settings.py`。

---

## 6. 阶段五：测试与质量保障

> 注意：当前 `.venv` **未安装 pytest / httpx**，做本阶段前需先 `pip install pytest httpx`（已写入 requirements.txt）。

### 6.1 单元测试
`chunker` 章节识别/目录清理/长段切分/小 chunk 合并；`doc_store` 增删改；`rag` 无 Key/非法模型/空检索。

### 6.2 API 测试（用 FastAPI TestClient）
`/api/health`、`/api/documents`(GET/POST)、`/replace`、`DELETE`、`/api/ask`（含拒答路径）。
**重点：拒答路径回归测试**——固化 0.865 阈值的标定约束（eval 集里 answerable 能答、irrelevant 被拒），防止以后改资料/参数破坏边界。

### 6.3 前端构建检查
每次重要改动后 `cd frontend && npm run build` 必须通过。

### 6.4 Smoke Test `scripts/smoke_test.py`（可选）
检查依赖可导入、本地模型存在、Chroma 可读、SQLite 可开、前端 dist 存在、`/api/health` 正常。
作为录屏/截图前的一键自检；非必需。

---

## 7. 推荐执行顺序

**P1 已基本完成（地基 + 可信度核心）**
- README、requirements.txt、.gitignore（已完成）
- `settings.py` 集中配置（已完成）
- 相似度阈值拒答（已完成）
- 评测集 + `run_eval` 基线指标（已完成）
- API Key 改环境变量优先（已完成）

**P2 让项目完整 + 出展示数据**
- 阶段五基础测试（§6.1 单测 + §6.2 API 测试，含拒答回归）
- 检索策略对比表整理进 README（§3.4，至少 top_k 一组）
- 文档版本历史 / 索引状态（§4.1、§4.2）
- embedding 模型复用（§5.1）
- 错误处理细化（§5.4）

**P3 进一步提升（视精力）**
- 混合检索 / reranker（§3.4 可选项）
- 生成端质量评测（§3.5）
- 文档预览（§4.4）
- keyring 存 Key
- smoke test 自动化（§6.4）

---

## 8. 作品集展示要点

定位：**通用 RAG 知识库问答系统**，样例资料只是当前演示数据（可换课程资料、制度、手册、企业知识库）。

放进 README / 简历的亮点：

- 通用文档上传建库，支持 docx/pdf/txt/md；
- 本地 `bge-small-zh` 中文向量 + Chroma 检索 + DeepSeek 生成；
- **回答可溯源 + 阈值拒答**，降低幻觉，且阈值由评测集标定（非拍脑袋）；
- 完整资料生命周期：上传 / 替换 / 删除 / 重索引，SQLite 记录文档/版本/chunk；
- 一份带数据表的评测报告（hit@k、拒答准确率、检索策略对比）；
- 前后端分离、集中配置、Key 安全、有测试——体现工程判断。

建议 README 配几张截图 + 一段简短的 GIF/录屏，作品集看的人停留时间短，视觉先行。

---

## 9. 最小可交付版本（时间紧时的底线）

- README（含截图）、requirements.txt、.gitignore
- 回答引用来源（已有）+ 相似度阈值拒答（已有）
- 评测集 + 一次基线评测报告（已有）
- 至少一组检索策略对比（哪怕只是 top_k），整理进 README
- 一次完整前后端构建验证
- 基础测试：至少覆盖拒答路径回归（§6.2）

完成以上，即是一个干净、可复现、有数据支撑的作品集级 RAG 项目。
