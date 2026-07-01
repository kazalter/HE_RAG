from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from rank_bm25 import BM25Okapi
import jieba

from . import doc_store
from . import settings

logger = logging.getLogger("rag.bm25")

# 预编译正则，用于中文和英文单词分词清理，过滤掉各种标点符号
PUNCTUATION_RE = re.compile(r"[^\w\s\u4e00-\u9fa5]")


def clean_and_tokenize(text: str) -> list[str]:
    """对文本进行清洗并使用 jieba 精确分词。"""
    # 过滤掉非字母、数字和中文字符
    text_clean = PUNCTUATION_RE.sub(" ", text)
    # 精确模式分词
    words = jieba.cut(text_clean)
    # 过滤掉多余空白和空串
    return [w.strip() for w in words if w.strip()]


class BM25Retriever:
    """基于内存和 rank_bm25 的轻量级稀疏检索器，在项目启动或更新文档时更新。"""

    def __init__(self) -> None:
        self.bm25: BM25Okapi | None = None
        self.chunks: list[dict] = []
        self.initialized: bool = False

    def load(self) -> None:
        """从 SQLite 活跃版本及其物理 JSON 中加载全部 Chunks 构建 BM25 检索树。"""
        try:
            # 1. 查找所有未被逻辑删除文档的当前活跃版本
            docs = doc_store.list_documents(include_deleted=False)
            active_versions = []
            for doc in docs:
                version_id = doc.get("current_version_id")
                if version_id:
                    ver = doc_store.get_version(version_id)
                    if ver and ver.get("status") == "indexed" and ver.get("chunks_path"):
                        active_versions.append(ver)

            # 2. 读取对应版本的物理 chunks JSON 提取正文
            all_chunks = []
            for ver in active_versions:
                # 物理路径需转化为绝对路径或以 settings.ROOT_DIR 为基准
                chunks_path = Path(settings.ROOT_DIR) / ver["chunks_path"]
                if chunks_path.exists():
                    try:
                        chunks_data = json.loads(chunks_path.read_text(encoding="utf-8"))
                        for index, c in enumerate(chunks_data, start=1):
                            # 补全元数据与 RAG 接口对齐
                            raw_id = c.get("chunk_id") or f"chunk_{index:03d}"
                            if ":" not in raw_id:
                                chunk_id = f"{ver['id']}:{raw_id}"
                            else:
                                chunk_id = raw_id
                            all_chunks.append(
                                {
                                    "chunk_id": chunk_id,
                                    "document_id": ver["document_id"],
                                    "version_id": ver["id"],
                                    "source": c.get("source") or ver["original_filename"],
                                    "section_title": c.get("section_title", ""),
                                    "char_count": int(c.get("char_count") or len(c.get("text", ""))),
                                    "text": c.get("text", ""),
                                }
                            )
                    except Exception as err:
                        logger.error("读取物理 chunks JSON 失败: %s, 路径: %s", err, chunks_path)

            self.chunks = all_chunks
            if not self.chunks:
                self.bm25 = None
                self.initialized = True
                logger.warning("BM25 未加载任何文档 chunks，可能是知识库为空。")
                return

            # 3. 对 Chunks 做分词预热（合并章节标题和内容）
            corpus = []
            for chunk in self.chunks:
                combined_text = f"{chunk['section_title']}\n{chunk['text']}"
                corpus.append(clean_and_tokenize(combined_text))

            # 4. 初始化 BM25 检索实例
            self.bm25 = BM25Okapi(corpus)
            self.initialized = True
            logger.info("BM25 检索器初始化完成，共载入 %d 个切块。", len(self.chunks))
        except Exception as err:
            logger.exception("构建 BM25 检索器时发生异常: %s", err)
            self.bm25 = None
            self.initialized = False

    def retrieve(self, question: str, top_k: int = 3) -> list[dict]:
        """根据问题检索最相关的 Chunks，附带 'bm25_score' 并排序返回。"""
        if not self.initialized:
            self.load()

        if not self.bm25 or not self.chunks:
            return []

        tokens = clean_and_tokenize(question)
        if not tokens:
            # 降级：无意义提问返回前 top_k
            return [dict(c, bm25_score=0.0) for c in self.chunks[:top_k]]

        scores = self.bm25.get_scores(tokens)

        # 附带得分并按得分倒序
        results = []
        for chunk, score in zip(self.chunks, scores):
            c = chunk.copy()
            c["bm25_score"] = float(score)
            results.append(c)

        results.sort(key=lambda x: x["bm25_score"], reverse=True)
        return results[:top_k]


from threading import Lock

_retriever: BM25Retriever | None = None
_lock = Lock()


def get_bm25_retriever() -> BM25Retriever:
    """返回进程共享的 BM25 检索器单例。"""
    global _retriever
    if _retriever is None:
        with _lock:
            if _retriever is None:
                _retriever = BM25Retriever()
                _retriever.load()
    return _retriever


def reset_bm25_retriever() -> None:
    """重置 BM25 检索器，强制下一次调用重新 load。"""
    global _retriever
    with _lock:
        _retriever = None

