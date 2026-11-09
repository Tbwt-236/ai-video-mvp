"""Read-only diagnostics. Never prints environment secrets or sends network requests."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import sqlite3
import sys

ROOT=Path(__file__).resolve().parent


def diagnose():
    checks=[]
    def add(name,ok,detail,optional=False):
        checks.append({"name":name,"ok":bool(ok),"detail":detail,"optional":optional})
    add("Python",sys.version_info>=(3,10),platform.python_version()+" / "+platform.system())
    for package in ["fastapi","uvicorn","Pillow","imageio-ffmpeg","httpx"]:
        try:add(package,True,importlib.metadata.version(package))
        except importlib.metadata.PackageNotFoundError:add(package,False,"尚未安装，请运行启动脚本。")
    if any(not check["ok"] for check in checks):
        return {"ready":False,"checks":checks}
    from run import load_env
    load_env()
    from app.renderer import font,run_ffmpeg
    from app.narration import available
    try:
        font(20).getbbox("你好，拾帧")
        add("中文字体",True,"可正常加载")
    except Exception:
        add("中文字体",False,"无法加载，请检查 assets/fonts 或 VIDEO_FONT 配置。")
    try:
        run_ffmpeg(["-version"],timeout=10)
        add("FFmpeg",True,"本地视频合成程序可用")
    except Exception:
        add("FFmpeg",False,"无法启动，请重新安装 requirements.txt 中的依赖。")
    data=Path(os.getenv("VIDEO_DATA_DIR",ROOT/"data")).expanduser()
    parent=data
    while not parent.exists() and parent!=parent.parent:parent=parent.parent
    add("数据位置",parent.is_dir() and os.access(parent,os.W_OK),str(data))
    try:
        free=shutil.disk_usage(parent).free
        add("磁盘空间",free>=512*1024**2,str(free//1024**2)+" MB 可用，1080p 导出至少预留 512 MB。")
    except OSError:
        add("磁盘空间",False,"无法读取磁盘空间。")
    database=data/"studio.sqlite3"
    if database.is_file():
        try:
            with sqlite3.connect(database.resolve().as_uri()+"?mode=ro",uri=True,timeout=5) as connection:
                result=connection.execute("PRAGMA quick_check").fetchone()[0]
            add("作品数据库",result=="ok","检查通过" if result=="ok" else "需要检查数据库，请先保留 data 备份。")
        except sqlite3.Error:
            add("作品数据库",False,"暂时无法读取，请关闭其他占用程序后再试。")
    else:
        add("作品数据库",True,"首次启动时自动创建")
    voice=available()
    add("中文配音",voice,"已安装本机婷婷语音" if voice else "当前不可用，可继续导出音乐与字幕。",optional=True)
    return {"ready":all(check["ok"] or check["optional"] for check in checks),"checks":checks}


def main():
    parser=argparse.ArgumentParser(description="FRAME environment diagnostics")
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args();result=diagnose()
    if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print("FRAME 运行检查 · "+("已就绪" if result["ready"] else "需要处理"))
        for check in result["checks"]:
            mark="通过" if check["ok"] else "可选" if check["optional"] else "检查"
            print("["+mark+"] "+check["name"]+"："+check["detail"])
    return 0 if result["ready"] else 1


if __name__=="__main__":
    raise SystemExit(main())
