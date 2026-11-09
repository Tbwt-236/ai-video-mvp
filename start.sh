#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "需要先安装 Python 3.10 或更新版本，推荐 Python 3.12。"
  exit 1
fi
exec python3 bootstrap.py
