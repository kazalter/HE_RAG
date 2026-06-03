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
- [~] 阶段三 资料管理（§4）—— 已完成：文档详情抽屉（点资料查看）含版本历史展示(§4.1)、索引状态/失败原因展示(§4.2)、chunk 切块预览(§4.4)；后端 `GET /api/documents/{id}` + `doc_store.list_versions/list_chunks` + API 测试。待补：版本回滚(§4.1)、物理删除接前端(§4.3)、提取全文预览(§4.4)
- [~] 阶段四 后端结构与安全（§5）—— 已完成：集中配置 `settings.py`(§5.2)、Key 环境变量优先(§5.3.2)、错误处理细化(§5.4)、embedding 单例复用(§5.1)；待补：轮换泄露 Key(§5.3.1，需用户操作)。注：§5.5 经查证 `deepseek-v4-flash/pro` 即官方当前 V4 ID，原代码无误，保持不变
- [~] 阶段五 测试与质量保障（§6）—— 已完成：6.1 单测（chunker/doc_store/rag，含阈值标定回归）、6.2 API 测试（TestClient，含拒答路径）；共 29 用例通过。待补：6.4 smoke test（可选）

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

### 4.1 文档版本历史（展示已完成，回滚待补）
利用已有 `document_versions` 表，前端详情抽屉展示历史版本（状态、文件名、创建时间、chunk 数）。
后端 `doc_store.list_versions(document_id)`。**回滚尚未实现。**

### 4.2 索引过程状态（已完成）
详情抽屉展示每个版本的状态徽标（已索引/处理中/失败/历史版本），失败时展示
`document_versions.parse_error` 原因。注：当前建索引是同步完成，无中间态流式进度，
故以最终状态（indexed/pending/failed）呈现而非逐步推进。

### 4.3 删除策略
区分“从知识库移除（标记删除+删向量，已实现）”与“物理删除文件（`remove_files=True` 已实现，未接前端）”；前端弹窗说明影响范围。**物理删除接前端待补。**

### 4.4 文档预览（chunk 预览已完成，全文待补）
详情抽屉展示当前版本的 chunk 列表（序号、章节标题、字符数、预览），便于发现乱码、
目录误切、章节识别失败。后端 `doc_store.list_chunks(version_id)`。**提取全文预览待补。**

---

## 5. 阶段四：优化后端结构与安全

### 5.1 复用 embedding 模型（已完成）
新增 `src/embedding.py`：进程级线程安全懒加载单例 `get_embedding_model()`。
`rag.load_embedding_model` 委托给它（Web 启动 `load_retriever` 加载的即此单例），
`doc_index.index_version` 改用同一单例——上传/替换建索引时不再加载第二份模型。
顺带把 `rag.py` 顶部对 `sentence_transformers` 的导入移除（改为延迟加载），
`import rag` 不再拉起 torch，测试收集由 ~31s 降到 ~1.5s。
回归：`tests/test_embedding.py`（只加载一次 / reset 重载 / rag 委托）。
（chunker 批处理流水线与 query_db 调试脚本是独立进程，二次加载无影响，保持不变。）

### 5.2 集中配置 `src/settings.py`（已完成）
模型名、Chroma 路径、collection、本地模型路径、默认 LLM、默认 top_k、相似度阈值统一在 `settings.py`。
验收：改路径/模型只改一处。

### 5.3 API Key 安全（**按此顺序执行**）
1. **立刻更换当前 DeepSeek Key**（旧 Key 已以明文存在 `.rag_config.json`，视为已泄露）。
2. 读取优先级改为：环境变量 `DEEPSEEK_API_KEY` 优先，其次本地配置文件。（已实现）
3. **先写好 `.gitignore`（含 `.rag_config.json`）再执行 `git init`**，否则首次提交会把 Key 带进历史。（.gitignore 已就绪）
4. README 写明安全注意事项；后续可选系统 keyring。

### 5.4 错误处理（已完成）
用户侧错误（类型不支持/解码失败/缺 Key/资料为空/模型不支持）返回**中文友好 detail**（前端直接弹给用户）；系统侧错误（检索/Chroma、DeepSeek 网络调用失败）用 `logger.exception` 记全栈到服务端日志，前端只回兜底中文，不外泄原始错误。
- `rag.py` / `doc_index.py`：底层报错文案中文化；base64 解码失败 → `ValueError`；不支持类型校验前置到建记录之前，避免孤儿文档。
- `web.py`：`/api/ask` 拆分检索/生成两段错误处理（检索失败 500、Key/模型类 400、DeepSeek 失败 502）；上传/替换/删除区分 400/404/500 并记日志。
- 测试：`tests/test_api.py` 覆盖缺 Key/配置错/DeepSeek 失败三条路径；`tests/test_doc_index.py` 覆盖类型校验与解码报错。

### 5.5 模型名核对（已核对）
`deepseek-v4-flash`/`deepseek-v4-pro` 即 api.deepseek.com 2026 年官方当前模型 ID，默认用 `deepseek-v4-flash`；`deepseek-chat`/`deepseek-reasoner` 是将于 2026-07-24 弃用的遗留别名（映射到 v4），保留为备选。配置集中在 `src/settings.py`。

---

## 6. 阶段五：测试与质量保障

> pytest 9.0.3 / httpx 0.28.1 已装（在 requirements.txt 内）。测试在仓库根的
> `tests/` 下，一键 `python -m pytest` 运行（根 `conftest.py` 保证能 import src）。

### 6.1 单元测试（已完成）
- `tests/test_chunker.py`：章节识别 `is_heading`、目录清理 `remove_table_of_contents`、长段切分 `split_long_paragraph`、小 chunk 合并 `merge_small_chunks`（含硬边界/跨文件不合并）。
- `tests/test_doc_store.py`：用临时 SQLite 库（monkeypatch `connect`）测增删改、版本索引生命周期、sha256 查重、软删除隐藏。
- `tests/test_rag.py`：`best_distance`/`has_sufficient_evidence`、无 Key、非法模型、空检索；**含阈值标定回归**。

### 6.2 API 测试（已完成，用 FastAPI TestClient）
`tests/test_api.py`：不进 lifespan（不加载模型），monkeypatch 检索/生成桩。覆盖
`/api/health`（断言阈值=0.865）、`/api/documents` GET、`/api/ask` 未就绪 503、
**拒答路径**（距离>阈值→refused 且不触网）、正常生成路径。
**阈值回归**固化在 `test_rag.py::test_default_threshold_separates_eval_distribution`：
默认阈值必须落在 eval 边界 [0.862, 0.869) 内，谁改坏立刻报警。
待补（非必需）：`/api/documents` POST、`/replace`、`DELETE` 走的是 `doc_index` 真实建库链路，需本地模型，暂未纳入快测。

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
- embedding 模型复用（§5.1，已完成）
- 错误处理细化（§5.4，已完成）

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
