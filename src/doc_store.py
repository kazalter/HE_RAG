from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR.parent / "data" / "app.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                current_version_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                deleted_at TEXT,
                FOREIGN KEY (current_version_id) REFERENCES document_versions(id)
            );

            CREATE TABLE IF NOT EXISTS document_versions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                stored_path TEXT NOT NULL,
                text_path TEXT,
                chunks_path TEXT,
                file_ext TEXT,
                file_size INTEGER,
                sha256 TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                chunk_count INTEGER DEFAULT 0,
                embedding_model TEXT,
                embedding_dim INTEGER,
                parse_error TEXT,
                created_at TEXT NOT NULL,
                indexed_at TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id)
            );

            CREATE TABLE IF NOT EXISTS document_chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                version_id TEXT NOT NULL,
                chroma_id TEXT NOT NULL UNIQUE,
                chunk_index INTEGER NOT NULL,
                section_title TEXT,
                char_count INTEGER,
                text_preview TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (document_id) REFERENCES documents(id),
                FOREIGN KEY (version_id) REFERENCES document_versions(id)
            );

            CREATE TABLE IF NOT EXISTS document_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                document_id TEXT,
                version_id TEXT,
                event_type TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_documents_status
                ON documents(status);
            CREATE INDEX IF NOT EXISTS idx_versions_document
                ON document_versions(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_version
                ON document_chunks(version_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_document
                ON document_chunks(document_id);
            """
        )


def document_count() -> int:
    with connect() as db:
        row = db.execute("SELECT COUNT(*) AS count FROM documents").fetchone()
        return int(row["count"])


def list_documents(include_deleted: bool = False) -> list[dict[str, Any]]:
    where = "" if include_deleted else "WHERE d.status != 'deleted'"
    with connect() as db:
        rows = db.execute(
            f"""
            SELECT
                d.id,
                d.title,
                d.current_version_id,
                d.status,
                d.created_at,
                d.updated_at,
                d.deleted_at,
                v.original_filename,
                v.file_ext,
                v.file_size,
                v.sha256,
                v.chunk_count,
                v.embedding_model,
                v.embedding_dim,
                v.indexed_at
            FROM documents d
            LEFT JOIN document_versions v ON v.id = d.current_version_id
            {where}
            ORDER BY d.updated_at DESC
            """
        ).fetchall()
        return [row_to_dict(row) for row in rows if row is not None]


def get_document(document_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM documents WHERE id = ?",
            (document_id,),
        ).fetchone()
        return row_to_dict(row)


def get_version(version_id: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM document_versions WHERE id = ?",
            (version_id,),
        ).fetchone()
        return row_to_dict(row)


def get_version_by_sha256(sha256: str) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute(
            """
            SELECT v.*, d.current_version_id
            FROM document_versions v
            JOIN documents d ON d.id = v.document_id
            WHERE v.sha256 = ?
            ORDER BY v.created_at DESC
            LIMIT 1
            """,
            (sha256,),
        ).fetchone()
        return row_to_dict(row)


def create_document(document_id: str, title: str, created_at: str | None = None) -> None:
    now = created_at or utc_now()
    with connect() as db:
        db.execute(
            """
            INSERT INTO documents (id, title, status, created_at, updated_at)
            VALUES (?, ?, 'active', ?, ?)
            """,
            (document_id, title, now, now),
        )


def create_version(
    *,
    version_id: str,
    document_id: str,
    original_filename: str,
    stored_path: str,
    file_ext: str,
    file_size: int,
    sha256: str,
    created_at: str | None = None,
) -> None:
    now = created_at or utc_now()
    with connect() as db:
        db.execute(
            """
            INSERT INTO document_versions (
                id, document_id, original_filename, stored_path, file_ext,
                file_size, sha256, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (
                version_id,
                document_id,
                original_filename,
                stored_path,
                file_ext,
                file_size,
                sha256,
                now,
            ),
        )


def mark_version_indexed(
    *,
    version_id: str,
    text_path: str,
    chunks_path: str,
    chunk_count: int,
    embedding_model: str,
    embedding_dim: int,
) -> None:
    now = utc_now()
    with connect() as db:
        db.execute(
            """
            UPDATE document_versions
            SET text_path = ?,
                chunks_path = ?,
                status = 'indexed',
                chunk_count = ?,
                embedding_model = ?,
                embedding_dim = ?,
                parse_error = NULL,
                indexed_at = ?
            WHERE id = ?
            """,
            (
                text_path,
                chunks_path,
                chunk_count,
                embedding_model,
                embedding_dim,
                now,
                version_id,
            ),
        )


def mark_version_failed(version_id: str, error: str) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE document_versions
            SET status = 'failed', parse_error = ?
            WHERE id = ?
            """,
            (error[:2000], version_id),
        )


def set_current_version(document_id: str, version_id: str) -> None:
    now = utc_now()
    with connect() as db:
        db.execute(
            """
            UPDATE documents
            SET current_version_id = ?,
                status = 'active',
                updated_at = ?,
                deleted_at = NULL
            WHERE id = ?
            """,
            (version_id, now, document_id),
        )


def archive_version(version_id: str) -> None:
    with connect() as db:
        db.execute(
            """
            UPDATE document_versions
            SET status = 'archived'
            WHERE id = ? AND status != 'deleted'
            """,
            (version_id,),
        )


def insert_chunks(chunks: list[dict[str, Any]]) -> None:
    if not chunks:
        return

    now = utc_now()
    with connect() as db:
        db.executemany(
            """
            INSERT INTO document_chunks (
                id, document_id, version_id, chroma_id, chunk_index,
                section_title, char_count, text_preview, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk["id"],
                    chunk["document_id"],
                    chunk["version_id"],
                    chunk["chroma_id"],
                    chunk["chunk_index"],
                    chunk.get("section_title", ""),
                    int(chunk.get("char_count", 0)),
                    chunk.get("text_preview", ""),
                    now,
                )
                for chunk in chunks
            ],
        )


def list_versions(document_id: str) -> list[dict[str, Any]]:
    """返回某文档的全部版本，最新在前（供前端展示版本历史 / 索引状态）。"""
    with connect() as db:
        rows = db.execute(
            """
            SELECT id, document_id, original_filename, file_ext, file_size,
                   status, chunk_count, embedding_model, embedding_dim,
                   parse_error, created_at, indexed_at
            FROM document_versions
            WHERE document_id = ?
            ORDER BY created_at DESC
            """,
            (document_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows if row is not None]


def list_chunks(version_id: str) -> list[dict[str, Any]]:
    """返回某版本的全部 chunk（章节标题/字符数/预览），按切块顺序，供文档预览。"""
    with connect() as db:
        rows = db.execute(
            """
            SELECT chunk_index, section_title, char_count, text_preview, chroma_id
            FROM document_chunks
            WHERE version_id = ?
            ORDER BY chunk_index
            """,
            (version_id,),
        ).fetchall()
        return [row_to_dict(row) for row in rows if row is not None]


def get_chroma_ids_for_version(version_id: str) -> list[str]:
    with connect() as db:
        rows = db.execute(
            """
            SELECT chroma_id
            FROM document_chunks
            WHERE version_id = ?
            ORDER BY chunk_index
            """,
            (version_id,),
        ).fetchall()
        return [str(row["chroma_id"]) for row in rows]


def delete_chunks_for_version(version_id: str) -> None:
    with connect() as db:
        db.execute(
            "DELETE FROM document_chunks WHERE version_id = ?",
            (version_id,),
        )


def mark_document_deleted(document_id: str) -> None:
    now = utc_now()
    with connect() as db:
        db.execute(
            """
            UPDATE documents
            SET status = 'deleted', deleted_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now, now, document_id),
        )
        db.execute(
            """
            UPDATE document_versions
            SET status = 'deleted'
            WHERE document_id = ? AND status != 'deleted'
            """,
            (document_id,),
        )


def log_event(
    event_type: str,
    message: str,
    document_id: str | None = None,
    version_id: str | None = None,
) -> None:
    with connect() as db:
        db.execute(
            """
            INSERT INTO document_events (
                document_id, version_id, event_type, message, created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, version_id, event_type, message, utc_now()),
        )
