"""Run the local studio. Environment variables take precedence over .env."""
import os
from pathlib import Path

import uvicorn


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


if __name__ == "__main__":
    load_env()
    try:
        port = int(os.getenv("PORT", "8000"))
        if not 1<=port<=65535:raise ValueError()
    except ValueError:
        raise SystemExit("PORT 需要是 1–65535 的整数，例如 8000。请检查 .env 后重新启动。")
    print(f"\n  FRAME 拾帧 · http://127.0.0.1:{port}\n  按 Ctrl+C 停止服务\n")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="info")
