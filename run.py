"""Run the local studio. Environment variables take precedence over .env."""
import os
import socket
from pathlib import Path

import uvicorn
from app.instance import StudioInUse, StudioLock


def load_env():
    path = Path(__file__).parent / ".env"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in {"DEEPSEEK_API_KEY", "DEEPSEEK_MODEL", "VIDEO_FONT", "VIDEO_DATA_DIR", "PORT", "ALLOWED_HOSTS"}:
                os.environ.setdefault(key, value.strip().strip("\"'"))


def port_in_use(port):
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as connection:
        connection.settimeout(.3)
        return connection.connect_ex(("127.0.0.1",port))==0


def main():
    load_env()
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1<=port<=65535:raise ValueError()
    except ValueError:
        print("PORT 需要是 1–65535 的整数，例如 8000。请检查 .env 后重新启动。")
        return 1
    if port_in_use(port):
        print(f"端口 {port} 已被占用。若工作台已经启动，请直接打开 http://127.0.0.1:{port} 。")
        print("若是其他程序占用了端口，请在 .env 设置另一个 PORT 后重试。")
        return 1
    try:
        with StudioLock(Path(os.getenv("VIDEO_DATA_DIR",Path(__file__).resolve().parent/"data"))):
            pass
    except StudioInUse as exc:
        print(str(exc))
        return 1
    except OSError:
        print("作品目录暂时无法写入，请检查 VIDEO_DATA_DIR 的路径、访问权限和磁盘空间。")
        return 1
    print(f"\n  FRAME 拾帧 · http://127.0.0.1:{port}\n  按 Ctrl+C 停止服务\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
