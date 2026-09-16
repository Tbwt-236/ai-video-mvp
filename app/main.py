import io
import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .models import Brief, ProjectEdit, RenderRequest
from .renderer import ROOT, font, render, scene_image
from .store import Store, now
from .storyboard import EXAMPLES, generate_storyboard, offline_storyboard

log = logging.getLogger("frame")


def create_app(data_dir=None):
    store = Store(Path(data_dir or os.getenv("VIDEO_DATA_DIR", ROOT / "data")))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-render")
    render_lock = threading.Lock()

    @asynccontextmanager
    async def lifespan(app):
        store.recover_jobs()
        if not store.projects():
            brief = Brief(**{k: v for k, v in EXAMPLES[0].items() if k != "label"})
            project = {**brief.model_dump(), **offline_storyboard(brief), "id": str(uuid4()),
                       "version": 1, "created_at": now(), "updated_at": now(), "example": True}
            store.save_project(project)
        yield
        executor.shutdown(wait=True)

    app = FastAPI(title="FRAME · AI Video MVP", lifespan=lifespan)
    app.state.store = store
    allowed_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    @app.middleware("http")
    async def local_guard(request: Request, call_next):
        if request.method in ("POST", "PUT", "DELETE", "PATCH"):
            origin = request.headers.get("origin")
            if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
                return JSONResponse({"detail": "仅接受同源请求"}, status_code=403)
            if not request.headers.get("content-type", "").startswith("application/json"):
                return JSONResponse({"detail": "请求必须使用 JSON"}, status_code=415)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "无效请求长度"}, status_code=400)
            if length > 32768:
                return JSONResponse({"detail": "请求内容过大"}, status_code=413)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        errors = [{"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse({"detail": "请检查输入内容、分镜字数和时长。", "errors": errors}, status_code=422)

    def get_project(pid):
        project = store.get_project(pid)
        if not project:
            raise HTTPException(404, "找不到这个项目")
        return project

    def get_job(jid):
        job = store.get_job(jid)
        if not job:
            raise HTTPException(404, "找不到这个导出任务")
        return job

    def public_job(job):
        return {k: v for k, v in job.items() if k != "snapshot"}

    @app.get("/api/config")
    def config():
        return {"ai_available": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
                "examples": EXAMPLES, "renderer": "动态文字短片 · H.264 MP4 · 720p · 24 fps"}

    @app.get("/api/health")
    def health():
        try:
            import imageio_ffmpeg
            version = imageio_ffmpeg.get_ffmpeg_version()
            font(20)
            return {"status": "ok", "ffmpeg": version}
        except Exception:
            return JSONResponse({"status": "error", "detail": "字体或 FFmpeg 不可用，请重新安装依赖。"}, status_code=503)

    @app.get("/api/projects")
    def projects():
        return store.projects()

    @app.post("/api/projects", status_code=201)
    def create_project(brief: Brief):
        try:
            board = generate_storyboard(brief)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        project = {**brief.model_dump(), **board, "id": str(uuid4()), "version": 1,
                   "created_at": now(), "updated_at": now(), "example": False}
        store.save_project(project)
        return project

    @app.get("/api/projects/{pid}")
    def project(pid: str):
        return get_project(pid)

    @app.put("/api/projects/{pid}")
    def edit_project(pid: str, edit: ProjectEdit):
        project = get_project(pid)
        changes = edit.model_dump(exclude={"version"})
        project.update(changes)
        project.update(version=edit.version+1, updated_at=now(), duration=sum(s.duration for s in edit.scenes))
        if not store.save_project(project, expected_version=edit.version):
            raise HTTPException(409, "项目已在其他窗口更新，请重新打开项目后编辑。")
        return project

    @app.get("/api/projects/{pid}/scenes/{index}.png")
    def preview(pid: str, index: int):
        project = get_project(pid)
        if not 0 <= index < len(project["scenes"]):
            raise HTTPException(404, "找不到这个分镜")
        buffer = io.BytesIO()
        scene_image(project, index).save(buffer, format="PNG")
        return Response(buffer.getvalue(), media_type="image/png")

    @app.get("/api/projects/{pid}/storyboard.json")
    def storyboard_download(pid: str):
        return Response(json.dumps(get_project(pid), ensure_ascii=False, indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="storyboard.json"'})

    def work(job):
        def progress(value, message):
            job.update(status="rendering", progress=value, message=message)
            store.save_job(job)
        try:
            progress(3, "准备画面与中文排版")
            directory = store.directory / "exports" / job["id"]
            render(job["snapshot"], directory, job["music"], progress)
            job.update(status="completed", progress=100, message="成片已就绪", completed_at=now(),
                       bytes=(directory/"video.mp4").stat().st_size)
        except Exception:
            log.exception("Video export failed: %s", job["id"])
            job.update(status="failed", error="视频合成失败，请重试。若持续失败，请检查磁盘空间与运行日志。")
        store.save_job(job)

    @app.post("/api/projects/{pid}/render")
    def export_video(pid: str, request: RenderRequest):
        with render_lock:
            project = get_project(pid)
            if request.version != project["version"]:
                raise HTTPException(409, "项目已更新，请保存并刷新分镜后重试。")
            jobs = store.jobs()
            for job in jobs:
                if (job["project_id"] == pid and job["version"] == request.version and job["music"] == request.music
                        and job["status"] in ("queued", "rendering", "completed")):
                    if job["status"] == "completed" and not (store.directory / "exports" / job["id"] / "video.mp4").is_file():
                        job.update(status="failed", error="成片文件已丢失，请重新导出。")
                        store.save_job(job)
                        continue
                    return public_job(job)
            if sum(j["status"] in ("queued", "rendering") for j in jobs) >= 3:
                raise HTTPException(429, "导出队列已满，请等待当前任务完成。")
            job = {"id": str(uuid4()), "project_id": pid, "version": project["version"],
                   "status": "queued", "progress": 0, "message": "等待渲染", "created_at": now(),
                   "music": request.music, "snapshot": project, "title": project["title"],
                   "duration": project["duration"], "aspect": project["aspect"]}
            store.save_job(job)
            executor.submit(work, job.copy())
            return public_job(job)

    @app.get("/api/projects/{pid}/jobs")
    def project_jobs(pid: str):
        get_project(pid)
        return [public_job(j) for j in store.jobs(pid)]

    @app.get("/api/jobs/{jid}")
    def job_status(jid: str):
        return public_job(get_job(jid))

    @app.get("/api/jobs/{jid}/video.mp4")
    def download(jid: str, download: bool = False):
        job = get_job(jid)
        if job["status"] != "completed":
            raise HTTPException(409, "视频还未完成，请稍后重试。")
        path = store.directory / "exports" / job["id"] / "video.mp4"
        if not path.is_file():
            raise HTTPException(404, "成片文件不存在，请修改分镜后重新导出。")
        return FileResponse(path, media_type="video/mp4", filename="frame-video.mp4" if download else None)

    @app.get("/api/jobs/{jid}/subtitles.srt")
    def subtitle_download(jid: str):
        job = get_job(jid)
        if job["status"] != "completed":
            raise HTTPException(409, "字幕尚未就绪")
        return FileResponse(store.directory / "exports" / job["id"] / "subtitles.srt", filename="subtitles.srt")

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app


app = create_app()
