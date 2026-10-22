"""Cross-platform local launcher. Uses only the Python standard library."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT=Path(__file__).resolve().parent


def dependency_probe(python):
    code = """
import importlib.metadata
import pathlib
import re
import sys
requirements=pathlib.Path(sys.argv[1]).read_text()
problems=[]
for name,expected in re.findall(r'^([A-Za-z0-9_-]+)==([^\\s]+)$',requirements,re.M):
    try:actual=importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:actual='missing'
    if actual!=expected:problems.append(name+': '+actual+' -> '+expected)
try:
    import fastapi, uvicorn, PIL, imageio_ffmpeg, httpx
except Exception as error:
    problems.append('Import check: '+type(error).__name__)
if problems:print('\\n'.join(problems))
sys.exit(bool(problems))
"""
    return subprocess.run([str(python),"-c",code,str(ROOT/"requirements.txt")],capture_output=True,text=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description="FRAME local studio launcher")
    parser.add_argument("--check",action="store_true",help="Check the local environment without installing or starting")
    parser.add_argument("--install-only",action="store_true",help="Prepare the environment without starting the server")
    args=parser.parse_args(argv)
    if sys.version_info<(3,10):
        print("FRAME 需要 Python 3.10 或更新版本，推荐 Python 3.12。",file=sys.stderr)
        return 1
    environment=ROOT/".venv"
    python=environment/("Scripts/python.exe" if os.name=="nt" else "bin/python")
    if not python.is_file():
        if args.check:
            print("尚未创建本地环境。运行启动脚本可自动安装依赖。")
            return 1
        if environment.exists():
            print("现有 .venv 不完整。请移走 .venv 文件夹后重新启动；data 中的作品无需改动。",file=sys.stderr)
            return 1
        print("正在创建本地 Python 环境…",flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    result=dependency_probe(python)
    if result.returncode:
        print("需要安装或更新项目依赖：\n"+(result.stdout.strip() or "环境导入检查未通过。"),flush=True)
        if args.check:return 1
        print("首次安装需要联网，完成后本地模板可离线使用。",flush=True)
        installed=subprocess.run([str(python),"-m","pip","install","-r",str(ROOT/"requirements.txt")],cwd=ROOT)
        if installed.returncode:
            print("依赖安装未完成。请检查网络后重新启动，已保存作品不会受影响。",file=sys.stderr)
            return installed.returncode
        if dependency_probe(python).returncode:
            print("依赖仍未就绪，请运行 python doctor.py 查看检查结果。",file=sys.stderr)
            return 1
    if args.check or args.install_only:
        print("FRAME 本地依赖已就绪。")
        return 0
    try:
        return subprocess.call([str(python),str(ROOT/"run.py")],cwd=ROOT)
    except KeyboardInterrupt:
        return 0


if __name__=="__main__":
    raise SystemExit(main())
