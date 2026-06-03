# RAG 知识库问答系统 — 项目约定

> 全局环境约定见 `~/.claude/CLAUDE.md`（Windows / PowerShell）。本文件只记本项目特有、
> 且从代码不易一眼看出的约定。详细计划见 `PLAN.md`，使用说明见 `README.md`。

## 定位
**通用 RAG 知识库问答系统**，作品集 / 简历展示项目。样例资料只是当前演示数据。
取舍原则：**工程判断 > 学术严谨**——评测集够用即可，别为撑场面凑题量。

## 技术栈与结构
- 后端 FastAPI（`src/web.py`，入口 `python -m src.launcher`）。
- 前端 Vue3 + Tailwind（`frontend/`，已组件化，`src/components/`）。
- 本地 Chroma 向量库（`data/chroma`，collection 名 **`thesis_chunks`** 是历史遗留名，别改坏）。
- SQLite 资料管理 `src/doc_store.py`（documents / document_versions / document_chunks / document_events 四表）。
- 本地 `bge-small-zh-v1.5` embedding（`models/`）+ DeepSeek 生成。

## 运行 / 验证
- 后端：`run_web.bat`（dist 不存在会先 `npm run build`）或直接 `python -m src.launcher`。
- 一键建库流水线：`python -m src.pipeline`（或 `run_rag.bat`）。
- 测试：仓库根 `python -m pytest`（根 `conftest.py` 保证能 import src）。**改动后单测 + `cd frontend; npm run build` 都要过。**

## 关键约定（容易踩坑）
- **配置集中在 `src/settings.py`**——改路径 / 模型 / 默认参数只动这一处。
- **拒答阈值 0.865 是评测标定值，别随手改**：由 eval 距离分布定（可答 ≤0.862 / 无关 ≥0.869）。
  有回归测试 `test_rag.py::test_default_threshold_separates_eval_distribution` 锁定 [0.862, 0.869)。
  换样例资料后须重跑 `python -m eval.run_eval` 重新标定。
- **DeepSeek 模型 ID**：默认 `deepseek-v4-flash`（另有 `deepseek-v4-pro`）。
  `deepseek-chat` / `deepseek-reasoner` 是将于 2026-07-24 弃用的遗留别名，不要当默认。
- **Key 安全**：读取顺序 `DEEPSEEK_API_KEY` 环境变量 > `.rag_config.json`。
  `.rag_config.json` 已在 .gitignore，**绝不提交 Key**。
- **错误处理分层**：用户侧错误（类型不支持 / 缺 Key / 资料为空等）返回中文友好 `detail`，前端直接弹；
  系统侧错误（Chroma / DeepSeek 网络失败）用 `logger.exception` 记全栈，前端只回兜底文案，不外泄原始报错。
- 注释 / 文档 / commit message 用中文。
