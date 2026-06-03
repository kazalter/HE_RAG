from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

import chromadb

from . import chunker
from . import doc_store as document_store
from . import embedding
from . import settings


APP_DIR = Path(__file__).resolve().parent
MATERIAL_DIR = settings.MATERIAL_DIR
TEXT_DIR = settings.TEXT_DIR
CHUNKS_DIR = settings.CHUNKS_DIR
DB_PATH = settings.CHROMA_PATH
COLLECTION_NAME = settings.COLLECTION_NAME
MODEL_NAME = settings.EMBEDDING_MODEL_NAME
SUPPORTED_EXTENSIONS = settings.SUPPORTED_EXTENSIONS


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def safe_name(name: str) -> str:
    cleaned = Path(name).name.strip() or "document"
    return re.sub(r'[<>:"/\\|?*\s]+', "_", cleaned).strip("_") or "document"


def decode_base64_content(content_base64: str) -> bytes:
    if "," in content_base64 and content_base64.lstrip().startswith("data:"):
        content_base64 = content_base64.split(",", 1)[1]
    try:
        return base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("文件内容解码失败，请重新上传。") from error


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_dirs(document_id: str) -> tuple[Path, Path, Path]:
    material_dir = MATERIAL_DIR / document_id
    text_dir = TEXT_DIR / document_id
    chunks_dir = CHUNKS_DIR / document_id
    material_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)
    return material_dir, text_dir, chunks_dir


def collection():
    client = chromadb.PersistentClient(path=str(DB_PATH))
    return client.get_or_create_collection(name=COLLECTION_NAME)


def delete_chroma_ids(chroma_ids: list[str]) -> None:
    if not chroma_ids:
        return
    try:
        collection().delete(ids=chroma_ids)
    except Exception as error:
        document_store.log_event("chroma_delete_failed", str(error))
        raise


def cleanup_version_files(version: dict[str, Any]) -> None:
    for key in ("stored_path", "text_path", "chunks_path"):
        raw_path = version.get(key)
        if not raw_path:
            continue
        path = Path(raw_path)
        if not path.is_absolute():
            path = APP_DIR.parent / path
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError as error:
            document_store.log_event(
                "file_cleanup_failed",
                f"{path}: {error}",
                version.get("document_id"),
                version.get("id"),
            )


def build_chunks_for_file(original_filename: str, stored_path: Path) -> tuple[str, list[dict[str, Any]], int]:
    text = chunker.extract_text(stored_path).strip()
    if not text:
        raise ValueError("无法从文件中提取到文本，请确认文件内容不为空且未损坏。")

    source = chunker.SourceDocument(path=Path(original_filename), text=text)
    chunks, section_count = chunker.build_chunks([source])
    return text, chunks, section_count


def write_version_outputs(
    *,
    document_id: str,
    version_id: str,
    text: str,
    chunks: list[dict[str, Any]],
) -> tuple[Path, Path]:
    _, text_dir, chunks_dir = ensure_dirs(document_id)
    text_path = text_dir / f"{version_id}.txt"
    chunks_path = chunks_dir / f"{version_id}.json"
    text_path.write_text(text, encoding="utf-8")
    chunks_path.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return text_path, chunks_path


def index_version(
    *,
    document_id: str,
    version_id: str,
    original_filename: str,
    stored_path: Path,
) -> dict[str, Any]:
    text, chunks, _section_count = build_chunks_for_file(original_filename, stored_path)
    text_path, chunks_path = write_version_outputs(
        document_id=document_id,
        version_id=version_id,
        text=text,
        chunks=chunks,
    )

    # 复用进程级共享单例：Web 端检索已加载的模型在此直接复用，不再加载第二份。
    model = embedding.get_embedding_model()
    texts = [chunk["text"] for chunk in chunks]
    embeddings = model.encode(texts, normalize_embeddings=True).tolist()
    embedding_dim = len(embeddings[0]) if embeddings else 0

    chroma_ids = [f"{version_id}:chunk_{index:03d}" for index in range(1, len(chunks) + 1)]
    metadatas = []
    db_chunks = []
    for index, (chunk, chroma_id) in enumerate(zip(chunks, chroma_ids), start=1):
        chunk["chunk_id"] = chroma_id
        metadatas.append(
            {
                "chunk_id": chroma_id,
                "document_id": document_id,
                "version_id": version_id,
                "source": original_filename,
                "section_title": chunk.get("section_title", ""),
                "char_count": int(chunk.get("char_count", 0)),
            }
        )
        db_chunks.append(
            {
                "id": new_id("chk"),
                "document_id": document_id,
                "version_id": version_id,
                "chroma_id": chroma_id,
                "chunk_index": index,
                "section_title": chunk.get("section_title", ""),
                "char_count": int(chunk.get("char_count", 0)),
                "text_preview": chunk.get("text", "")[:240],
            }
        )

    if chroma_ids:
        collection().add(
            ids=chroma_ids,
            documents=texts,
            metadatas=metadatas,
            embeddings=embeddings,
        )

    document_store.insert_chunks(db_chunks)
    document_store.mark_version_indexed(
        version_id=version_id,
        text_path=str(text_path.relative_to(APP_DIR.parent)),
        chunks_path=str(chunks_path.relative_to(APP_DIR.parent)),
        chunk_count=len(chunks),
        embedding_model=MODEL_NAME,
        embedding_dim=embedding_dim,
    )

    return {
        "text_path": text_path,
        "chunks_path": chunks_path,
        "chunk_count": len(chunks),
        "embedding_dim": embedding_dim,
        "chroma_ids": chroma_ids,
    }


def validate_extension(clean_filename: str) -> str:
    file_ext = Path(clean_filename).suffix.lower()
    if file_ext not in SUPPORTED_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise ValueError(f"不支持的文件类型：{file_ext or '（无扩展名）'}。仅支持 {allowed}。")
    return file_ext


def create_document_from_bytes(
    *,
    original_filename: str,
    content: bytes,
    title: str | None = None,
) -> dict[str, Any]:
    # 先校验类型，避免不支持的文件留下没有版本的孤儿 document 记录。
    validate_extension(safe_name(original_filename))

    document_id = new_id("doc")
    document_store.create_document(document_id, title or Path(original_filename).stem or original_filename)
    return add_version_from_bytes(
        document_id=document_id,
        original_filename=original_filename,
        content=content,
        make_current=True,
    )


def add_version_from_bytes(
    *,
    document_id: str,
    original_filename: str,
    content: bytes,
    make_current: bool,
) -> dict[str, Any]:
    document = document_store.get_document(document_id)
    if document is None or document["status"] == "deleted":
        raise KeyError(f"Document not found: {document_id}")

    clean_filename = safe_name(original_filename)
    file_ext = validate_extension(clean_filename)

    version_id = new_id("ver")
    material_dir, _, _ = ensure_dirs(document_id)
    stored_path = material_dir / f"{version_id}_{clean_filename}"
    stored_path.write_bytes(content)

    document_store.create_version(
        version_id=version_id,
        document_id=document_id,
        original_filename=clean_filename,
        stored_path=str(stored_path.relative_to(APP_DIR.parent)),
        file_ext=file_ext,
        file_size=len(content),
        sha256=sha256_bytes(content),
    )

    old_version_id = document.get("current_version_id")
    try:
        index_result = index_version(
            document_id=document_id,
            version_id=version_id,
            original_filename=clean_filename,
            stored_path=stored_path,
        )

        if make_current:
            if old_version_id:
                old_ids = document_store.get_chroma_ids_for_version(old_version_id)
                delete_chroma_ids(old_ids)
                document_store.delete_chunks_for_version(old_version_id)
                document_store.archive_version(old_version_id)

            document_store.set_current_version(document_id, version_id)
            document_store.log_event(
                "document_replaced" if old_version_id else "document_created",
                f"{clean_filename}, {index_result['chunk_count']} chunks",
                document_id,
                version_id,
            )

        return {
            "document_id": document_id,
            "version_id": version_id,
            "filename": clean_filename,
            "chunk_count": index_result["chunk_count"],
            "embedding_dim": index_result["embedding_dim"],
        }
    except Exception as error:
        document_store.mark_version_failed(version_id, str(error))
        document_store.log_event("index_failed", str(error), document_id, version_id)
        cleanup_version_files({"stored_path": stored_path, "document_id": document_id, "id": version_id})
        raise


def create_document_from_base64(
    *,
    original_filename: str,
    content_base64: str,
    title: str | None = None,
) -> dict[str, Any]:
    return create_document_from_bytes(
        original_filename=original_filename,
        content=decode_base64_content(content_base64),
        title=title,
    )


def replace_document_from_base64(
    *,
    document_id: str,
    original_filename: str,
    content_base64: str,
) -> dict[str, Any]:
    return add_version_from_bytes(
        document_id=document_id,
        original_filename=original_filename,
        content=decode_base64_content(content_base64),
        make_current=True,
    )


def delete_document(document_id: str, remove_files: bool = False) -> None:
    document = document_store.get_document(document_id)
    if document is None or document["status"] == "deleted":
        raise KeyError(f"Document not found: {document_id}")

    version_id = document.get("current_version_id")
    if version_id:
        chroma_ids = document_store.get_chroma_ids_for_version(version_id)
        delete_chroma_ids(chroma_ids)
        document_store.delete_chunks_for_version(version_id)

    document_store.mark_document_deleted(document_id)
    document_store.log_event("document_deleted", "Document marked as deleted", document_id, version_id)

    if remove_files:
        material_path = MATERIAL_DIR / document_id
        text_path = TEXT_DIR / document_id
        chunks_path = CHUNKS_DIR / document_id
        for path in (material_path, text_path, chunks_path):
            if path.exists() and path.is_dir():
                shutil.rmtree(path)


def bootstrap_existing_documents() -> None:
    document_store.init_db()

    material_files = []
    if MATERIAL_DIR.exists():
        for path in MATERIAL_DIR.rglob("*"):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS and not path.name.startswith("~$"):
                material_files.append(path)

    for material_path in sorted(material_files, key=lambda item: item.name.lower()):
        file_hash = sha256_file(material_path)
        existing_version = document_store.get_version_by_sha256(file_hash)

        if existing_version and existing_version.get("status") == "indexed" and existing_version.get("current_version_id"):
            continue

        if existing_version:
            document_id = existing_version["document_id"]
            version_id = existing_version["id"]
        else:
            document_id = new_id("doc")
            version_id = new_id("ver")
            document_store.create_document(document_id, material_path.stem)
            document_store.create_version(
                version_id=version_id,
                document_id=document_id,
                original_filename=material_path.name,
                stored_path=str(material_path.relative_to(APP_DIR.parent)),
                file_ext=material_path.suffix.lower(),
                file_size=material_path.stat().st_size,
                sha256=file_hash,
            )

        chunk_path = find_existing_chunk_file(material_path)
        chunk_count = 0
        db_chunks: list[dict[str, Any]] = []
        document_store.delete_chunks_for_version(version_id)
        if chunk_path and chunk_path.exists():
            try:
                existing_chunks = json.loads(chunk_path.read_text(encoding="utf-8"))
                for index, chunk in enumerate(existing_chunks, start=1):
                    chroma_id = chunk.get("chunk_id") or f"chunk_{index:03d}"
                    db_chunks.append(
                        {
                            "id": new_id("chk"),
                            "document_id": document_id,
                            "version_id": version_id,
                            "chroma_id": chroma_id,
                            "chunk_index": index,
                            "section_title": chunk.get("section_title", ""),
                            "char_count": int(chunk.get("char_count", 0)),
                            "text_preview": chunk.get("text", "")[:240],
                        }
                    )
                chunk_count = len(existing_chunks)
            except Exception as error:
                document_store.log_event("bootstrap_chunk_failed", str(error), document_id, version_id)

        document_store.insert_chunks(db_chunks)
        document_store.mark_version_indexed(
            version_id=version_id,
            text_path=str(find_existing_text_file(material_path) or ""),
            chunks_path=str(chunk_path or ""),
            chunk_count=chunk_count,
            embedding_model=MODEL_NAME,
            embedding_dim=0,
        )
        document_store.set_current_version(document_id, version_id)
        document_store.log_event("bootstrap_document", material_path.name, document_id, version_id)


def find_existing_chunk_file(material_path: Path) -> Path | None:
    candidate = CHUNKS_DIR / chunker.output_name("chunks", material_path, ".json")
    if candidate.exists():
        return candidate
    return None


def find_existing_text_file(material_path: Path) -> Path | None:
    candidate = TEXT_DIR / chunker.output_name("thesis", material_path, ".txt")
    if candidate.exists():
        return candidate
    return None
