import socket
import sys
import webbrowser
from threading import Timer

import uvicorn


HOST = "127.0.0.1"
DEFAULT_PORT = 7860
MAX_PORT_TRIES = 20


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex((host, port)) != 0


def find_available_port(host: str, start_port: int) -> int:
    for port in range(start_port, start_port + MAX_PORT_TRIES):
        if is_port_available(host, port):
            return port

    raise RuntimeError(
        f"没有找到可用端口，请先关闭 {start_port}-{start_port + MAX_PORT_TRIES - 1} 范围内的旧服务。"
    )


def parse_port() -> int:
    if len(sys.argv) < 2:
        return DEFAULT_PORT

    try:
        return int(sys.argv[1])
    except ValueError:
        return DEFAULT_PORT


def main() -> None:
    preferred_port = parse_port()
    port = find_available_port(HOST, preferred_port)
    url = f"http://{HOST}:{port}"

    if port != preferred_port:
        print(f"端口 {preferred_port} 已被占用，自动改用端口 {port}。")

    print(f"Web 地址：{url}")
    Timer(1.5, lambda: webbrowser.open(url)).start()

    uvicorn.run(
        "src.web:app",
        host=HOST,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
