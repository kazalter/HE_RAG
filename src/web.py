from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config as app_config
from . import doc_index as document_index
from . import doc_store as document_store
from . import settings
from .rag import (
    AVAILABLE_LLM_MODELS,
    INSUFFICIENT_EVIDENCE_MESSAGE,
    LLM_MODEL,
    answer_with_deepseek,
    has_sufficient_evidence,
    load_retriever,
    retrieve_chunks,
)


APP_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = APP_DIR.parent / "frontend" / "dist"
ASSETS_DIR = FRONTEND_DIST / "assets"
TOP_K = settings.DEFAULT_TOP_K


class RagState:
    def __init__(self) -> None:
        self.embedding_model = None
        self.collection = None
        self.index_lock = Lock()

    def load(self) -> None:
        self.embedding_model, self.collection = load_retriever()

    @property
    def ready(self) -> bool:
        return self.embedding_model is not None and self.collection is not None


state = RagState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    document_index.bootstrap_existing_documents()
    print("正在加载 RAG 检索器...")
    state.load()
    print("RAG 检索器加载完成。")
    yield


app = FastAPI(
    title="论文 RAG 问答 API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:7860",
        "http://localhost:7860",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")


class AskRequest(BaseModel):
    api_key: str = ""
    question: str = Field(min_length=1)
    top_k: int = Field(default=TOP_K, ge=1, le=6)
    model: str = Field(default=LLM_MODEL)


class ChunkResult(BaseModel):
    chunk_id: str
    document_id: str = ""
    version_id: str = ""
    source: str = ""
    section_title: str
    char_count: int
    distance: float
    relevance: float = 0.0
    text: str


class AskResponse(BaseModel):
    answer: str
    chunks: list[ChunkResult]
    refused: bool = False


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)
    title: str | None = None


class DocumentReplaceRequest(BaseModel):
    filename: str = Field(min_length=1)
    content_base64: str = Field(min_length=1)


class DocumentOperationResponse(BaseModel):
    ok: bool
    document_id: str | None = None
    version_id: str | None = None
    chunk_count: int | None = None
    message: str


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "ready": state.ready,
        "model": LLM_MODEL,
        "models": [
            {"value": value, "label": label}
            for value, label in AVAILABLE_LLM_MODELS.items()
        ],
        "top_k": settings.get_top_k(),
        "similarity_distance_threshold": settings.get_similarity_distance_threshold(),
        "document_count": len(document_store.list_documents()),
        "api_key_saved": app_config.has_deepseek_api_key(),
    }


@app.post("/api/ask", response_model=AskResponse)
def ask(payload: AskRequest) -> AskResponse:
    if not state.ready:
        raise HTTPException(status_code=503, detail="RAG 检索器还没有加载完成。")

    api_key = payload.api_key.strip() or app_config.get_deepseek_api_key()
    if not api_key:
        raise HTTPException(status_code=400, detail="DeepSeek API Key has not been saved.")

    try:
        with state.index_lock:
            chunks = retrieve_chunks(
                question=payload.question.strip(),
                embedding_model=state.embedding_model,
                collection=state.collection,
                top_k=payload.top_k,
            )
        for chunk in chunks:
            chunk["relevance"] = settings.distance_to_relevance(chunk["distance"])

        # 阈值拒答：检索不到足够相关的依据时，直接返回提示，不调用 LLM，降低幻觉。
        if not has_sufficient_evidence(chunks):
            return AskResponse(
                answer=INSUFFICIENT_EVIDENCE_MESSAGE,
                chunks=chunks,
                refused=True,
            )

        answer = answer_with_deepseek(
            question=payload.question.strip(),
            chunks=chunks,
            api_key=api_key,
            model=payload.model,
        )
        return AskResponse(answer=answer, chunks=chunks, refused=False)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return {
        "api_key_saved": app_config.has_deepseek_api_key(),
    }


@app.post("/api/settings/api-key")
def save_api_key(payload: ApiKeyRequest) -> dict[str, Any]:
    app_config.set_deepseek_api_key(payload.api_key)
    return {
        "ok": True,
        "api_key_saved": True,
    }


@app.delete("/api/settings/api-key")
def clear_api_key() -> dict[str, Any]:
    app_config.clear_deepseek_api_key()
    return {
        "ok": True,
        "api_key_saved": False,
    }


@app.get("/api/documents")
def list_documents() -> dict[str, Any]:
    return {
        "documents": document_store.list_documents(),
    }


@app.post("/api/documents", response_model=DocumentOperationResponse)
def create_document(payload: DocumentUploadRequest) -> DocumentOperationResponse:
    try:
        with state.index_lock:
            result = document_index.create_document_from_base64(
                original_filename=payload.filename,
                content_base64=payload.content_base64,
                title=payload.title,
            )
        return DocumentOperationResponse(
            ok=True,
            document_id=result["document_id"],
            version_id=result["version_id"],
            chunk_count=result["chunk_count"],
            message="Document uploaded and indexed.",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.put("/api/documents/{document_id}/replace", response_model=DocumentOperationResponse)
def replace_document(document_id: str, payload: DocumentReplaceRequest) -> DocumentOperationResponse:
    try:
        with state.index_lock:
            result = document_index.replace_document_from_base64(
                document_id=document_id,
                original_filename=payload.filename,
                content_base64=payload.content_base64,
            )
        return DocumentOperationResponse(
            ok=True,
            document_id=result["document_id"],
            version_id=result["version_id"],
            chunk_count=result["chunk_count"],
            message="Document replaced; old vectors were deleted.",
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.delete("/api/documents/{document_id}", response_model=DocumentOperationResponse)
def delete_document(document_id: str) -> DocumentOperationResponse:
    try:
        with state.index_lock:
            document_index.delete_document(document_id)
        return DocumentOperationResponse(
            ok=True,
            document_id=document_id,
            message="Document deleted; current vectors were removed.",
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = FRONTEND_DIST / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    return HTMLResponse(
        """
        <!doctype html>
        <html lang="zh-CN">
        <head><meta charset="utf-8"><title>论文 RAG 问答</title></head>
        <body style="font-family: Microsoft YaHei, sans-serif; padding: 32px;">
          <h1>前端还没有构建</h1>
          <p>请先进入 frontend 目录运行：</p>
          <pre>npm.cmd install
npm.cmd run build</pre>
          <p>然后重新启动后端服务。</p>
        </body>
        </html>
        """,
        status_code=200,
    )


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str):
    index_path = FRONTEND_DIST / "index.html"

    if index_path.exists():
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="前端还没有构建。")
