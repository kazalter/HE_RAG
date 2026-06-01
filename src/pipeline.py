from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CHUNK_SCRIPT = BASE_DIR / "chunker.py"
FRONTEND_DIR = BASE_DIR.parent / "frontend"
FRONTEND_DIST_INDEX = FRONTEND_DIR / "dist" / "index.html"
START_WEB_SCRIPT = BASE_DIR / "launcher.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="一键构建 RAG 知识库：提取文档、生成 chunks、写入向量库，并可启动 Web。"
    )
    parser.add_argument(
        "--material-dir",
        default=str(BASE_DIR.parent / "data" / "material"),
        help="资料目录，默认是 ./data/material",
    )
    parser.add_argument(
        "--text-dir",
        default=str(BASE_DIR.parent / "data" / "text"),
        help="提取文本输出目录，默认是 ./data/text",
    )
    parser.add_argument(
        "--chunks-dir",
        default=str(BASE_DIR.parent / "data" / "chunks"),
        help="chunk JSON 输出目录，默认是 ./data/chunks",
    )
    parser.add_argument(
        "--db-path",
        default=str(BASE_DIR.parent / "data" / "chroma"),
        help="Chroma 向量库目录，默认是 ./data/chroma",
    )
    parser.add_argument(
        "--collection-name",
        default="thesis_chunks",
        help="Chroma collection 名称，默认是 thesis_chunks",
    )
    parser.add_argument(
        "--skip-embedding",
        action="store_true",
        help="只生成文本和 chunks，不写入向量库。",
    )
    parser.add_argument(
        "--skip-frontend-build",
        action="store_true",
        help="不自动构建前端。",
    )
    parser.add_argument(
        "--skip-web",
        action="store_true",
        help="只构建 RAG 知识库，不启动 Web。",
    )
    parser.add_argument(
        "--port",
        default="7860",
        help="启动 Web 时优先使用的端口，默认 7860。",
    )
    return parser.parse_args()


def run_command(command: list[str], cwd: Path) -> None:
    print()
    print(">>> " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd), check=True)


def build_knowledge_base(args: argparse.Namespace) -> None:
    if not CHUNK_SCRIPT.exists():
        raise FileNotFoundError(f"找不到核心切割脚本：{CHUNK_SCRIPT}")

    command = [
        sys.executable,
        str(CHUNK_SCRIPT),
        "--material-dir",
        args.material_dir,
        "--text-dir",
        args.text_dir,
        "--chunks-dir",
        args.chunks_dir,
        "--db-path",
        args.db_path,
        "--collection-name",
        args.collection_name,
    ]

    if args.skip_embedding:
        command.append("--skip-embedding")

    run_command(command, BASE_DIR.parent)


def build_frontend_if_needed(skip_frontend_build: bool) -> None:
    if skip_frontend_build or FRONTEND_DIST_INDEX.exists():
        return

    if not FRONTEND_DIR.exists():
        print("未发现 frontend 目录，跳过前端构建。")
        return

    node_modules = FRONTEND_DIR / "node_modules"
    if not node_modules.exists():
        run_command(["npm.cmd", "install"], FRONTEND_DIR)

    run_command(["npm.cmd", "run", "build"], FRONTEND_DIR)


def start_web(port: str) -> None:
    if not START_WEB_SCRIPT.exists():
        raise FileNotFoundError(f"找不到 Web 启动脚本：{START_WEB_SCRIPT}")

    run_command([sys.executable, "-m", "src.launcher", port], BASE_DIR.parent)


def main() -> None:
    args = parse_args()

    print("========== RAG 自动化流程开始 ==========", flush=True)
    print(f"资料目录：{args.material_dir}", flush=True)
    print(f"文本目录：{args.text_dir}", flush=True)
    print(f"Chunks 目录：{args.chunks_dir}", flush=True)
    print(f"向量库目录：{args.db_path}", flush=True)
    print(f"Collection：{args.collection_name}", flush=True)

    build_knowledge_base(args)
    print()
    print("RAG 知识库已构建完成。")

    if args.skip_web:
        print("已按参数要求跳过 Web 启动。")
        return

    build_frontend_if_needed(args.skip_frontend_build)
    print()
    print("正在启动 Web RAG 问答服务...")
    start_web(args.port)


if __name__ == "__main__":
    main()
