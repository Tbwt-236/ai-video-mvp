import io
import copy
import json
import logging
import os
import threading
import shutil
import zipfile
import tempfile
from urllib.parse import unquote
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.concurrency import run_in_threadpool
from starlette.background import BackgroundTask

from .models import Brief, MerchantBrief, PreviewRequest, ProjectEdit, ProjectState, RenderRequest, VersionRequest, VoicePreview
from .assets import MAX_UPLOAD, list_photos, photo_path, save_photo
from .merchant import catalog as merchant_catalog, merchant_storyboard
from .narration import NarrationError, available as narration_available, synthesize
from .renderer import ROOT, font, render, scene_image, run_ffmpeg
from .process import RenderCancelled
from .checks import export_check
from .portability import MAX_PACKAGE, export_package, import_package
from .store import Store, now
from .storyboard import EXAMPLES, generate_storyboard, offline_storyboard

log = logging.getLogger("frame")


def create_app(data_dir=None):
    store = Store(Path(data_dir or os.getenv("VIDEO_DATA_DIR", ROOT / "data")))
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="video-render")
    render_lock = threading.Lock()
    upload_lock = threading.Lock()
    voice_lock = threading.Lock()
    import_lock = threading.Lock()
    controls = {}

    @asynccontextmanager
    async def lifespan(app):
        store.recover_jobs()
        if not store.projects(include_archived=True):
            brief = Brief(**{k: v for k, v in EXAMPLES[0].items() if k != "label"})
            project = {**brief.model_dump(), **offline_storyboard(brief), "id": str(uuid4()),
                       "version": 1, "created_at": now(), "updated_at": now(), "example": True}
            store.save_project(project)
        yield
        for event, _ in list(controls.values()):
            event.set()
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
            upload = request.method == "POST" and request.url.path.startswith("/api/projects/") and request.url.path.endswith("/assets")
            importing = request.method == "POST" and request.url.path == "/api/projects/import"
            content_type = request.headers.get("content-type", "").split(";")[0]
            if upload and content_type not in {"image/jpeg", "image/png", "image/webp"}:
                return JSONResponse({"detail": "请选择 JPG、PNG 或 WebP 照片"}, status_code=415)
            if importing and content_type not in {"application/zip", "application/x-zip-compressed", "application/octet-stream"}:
                return JSONResponse({"detail": "请选择 FRAME 作品 ZIP"}, status_code=415)
            if not upload and not importing and content_type != "application/json":
                return JSONResponse({"detail": "请求必须使用 JSON"}, status_code=415)
            try:
                length = int(request.headers.get("content-length", "0"))
            except ValueError:
                return JSONResponse({"detail": "无效请求长度"}, status_code=400)
            if length > (MAX_UPLOAD if upload else MAX_PACKAGE if importing else 32768):
                return JSONResponse({"detail": "请求内容过大"}, status_code=413)
            if not upload and not importing:
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 32768:
                        return JSONResponse({"detail": "请求内容过大"}, status_code=413)
                request._body = bytes(body)
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
                "examples": EXAMPLES, "merchant_catalog": merchant_catalog(),
                "renderer": "门店照片短片 · H.264 MP4 · 720p / 1080p · 24 fps",
                "narration_available": narration_available(),
                "narration_note": "本机中文语音 · 朗读画面字幕" if narration_available() else "本机未提供中文配音，仍可导出照片、字幕与音乐"}

    @app.get("/api/health")
    def health():
        try:
            import imageio_ffmpeg
            version = imageio_ffmpeg.get_ffmpeg_version()
            font(20)
            return {"status": "ok", "ffmpeg": version}
        except Exception:
            return JSONResponse({"status": "error", "detail": "字体或 FFmpeg 不可用，请重新安装依赖。"}, status_code=503)

    @app.post("/api/narration/preview")
    def voice_preview(request: VoicePreview):
        if not narration_available():
            raise HTTPException(400, "本机中文配音不可用，可关闭配音后继续制作。")
        if not voice_lock.acquire(blocking=False):
            raise HTTPException(429, "另一段试听正在准备，请稍后再试。")
        try:
            with tempfile.TemporaryDirectory(prefix="voice-preview-", dir=store.directory) as temporary:
                path = Path(temporary) / "preview.wav"
                synthesize(request.text, path, run_ffmpeg, rate=request.speech_rate)
                return Response(path.read_bytes(), media_type="audio/wav")
        except NarrationError as exc:
            raise HTTPException(400, str(exc)) from exc
        finally:
            voice_lock.release()

    @app.get("/api/projects")
    def projects(include_archived: bool = False):
        return store.projects(include_archived=include_archived)

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

    @app.post("/api/projects/import", status_code=201)
    async def project_import(request: Request):
        if not import_lock.acquire(blocking=False):
            raise HTTPException(429, "另一份作品正在导入，请稍后再试。")
        try:
            with tempfile.TemporaryDirectory(prefix="package-upload-",dir=store.directory) as temporary:
                path=Path(temporary)/"upload.zip"
                size=0
                with path.open("wb") as output:
                    async for chunk in request.stream():
                        size+=len(chunk)
                        if size>MAX_PACKAGE:
                            raise HTTPException(413, "作品包不能超过 350 MB")
                        output.write(chunk)
                try:
                    return await run_in_threadpool(import_package,store,path)
                except ValueError as exc:
                    raise HTTPException(400, str(exc)) from exc
        finally:
            import_lock.release()

    @app.get("/api/projects/{pid}/package.zip")
    def project_package(pid: str):
        project=get_project(pid)
        temporary=tempfile.mkdtemp(prefix="project-export-",dir=store.directory)
        path=Path(temporary)/"frame-project.zip"
        try:
            with upload_lock:
                export_package(store,project,path)
        except ValueError as exc:
            shutil.rmtree(temporary,ignore_errors=True)
            raise HTTPException(400, str(exc)) from exc
        except Exception:
            shutil.rmtree(temporary,ignore_errors=True)
            raise
        return FileResponse(path,media_type="application/zip",filename="frame-project.zip",
                            background=BackgroundTask(shutil.rmtree,temporary,ignore_errors=True))

    @app.post("/api/projects/{pid}/duplicate", status_code=201)
    def duplicate_project(pid: str, request: VersionRequest):
        original = get_project(pid)
        if original["version"] != request.version:
            raise HTTPException(409, "作品已更新，请重新打开后复制。")
        project = copy.deepcopy(original)
        project.update(id=str(uuid4()), title=original["title"][:27]+" · 副本", version=1,
                       archived=False, created_at=now(), updated_at=now())
        source = store.directory / "assets" / original["id"]
        with upload_lock:
            if source.is_dir():
                shutil.copytree(source, store.directory / "assets" / project["id"])
        store.save_project(project)
        return project

    @app.post("/api/projects/{pid}/archive")
    def archive_project(pid: str, request: ProjectState):
        project = get_project(pid)
        project.update(archived=request.archived, updated_at=now(), version=request.version+1)
        if not store.save_project(project, expected_version=request.version):
            raise HTTPException(409, "作品已更新，请刷新后再试。")
        return project

    @app.post("/api/merchant-projects", status_code=201)
    def create_merchant(brief: MerchantBrief):
        project = {**brief.model_dump(include={"style", "aspect", "duration", "example"}),
                   **merchant_storyboard(brief), "mode": "template", "id": str(uuid4()),
                   "version": 1, "created_at": now(), "updated_at": now()}
        store.save_project(project)
        return project

    @app.post("/api/projects/{pid}/assets", status_code=201)
    async def upload_photo(pid: str, request: Request):
        project = get_project(pid)
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_UPLOAD:
                raise HTTPException(413, "照片不能超过 8 MB")
        def save():
            with upload_lock:
                return save_photo(content, store.directory / "assets" / project["id"],
                                  unquote(request.headers.get("x-file-name", "门店照片")))
        try:
            return await run_in_threadpool(save)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.get("/api/projects/{pid}/assets")
    def photos(pid: str):
        project = get_project(pid)
        return list_photos(store.directory / "assets" / project["id"])

    @app.get("/api/projects/{pid}/assets/{aid}.jpg")
    def photo(pid: str, aid: str):
        project = get_project(pid)
        path = photo_path(store.directory / "assets" / project["id"], aid)
        if path is None:
            raise HTTPException(404, "找不到这张照片")
        return FileResponse(path, media_type="image/jpeg")

    @app.put("/api/projects/{pid}")
    def edit_project(pid: str, edit: ProjectEdit):
        project = get_project(pid)
        for scene in edit.scenes:
            if scene.asset_id and not (store.directory / "assets" / project["id"] / f"{scene.asset_id}.jpg").is_file():
                raise HTTPException(400, "照片不存在或不属于当前作品，请重新上传")
        changes = edit.model_dump(exclude={"version"})
        if "merchant" not in edit.model_fields_set:
            changes.pop("merchant", None)
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
        scene_image(project, index, asset_dir=store.directory / "assets" / project["id"]).save(buffer, format="PNG")
        return Response(buffer.getvalue(), media_type="image/png")

    @app.post("/api/projects/{pid}/preview")
    def draft_preview(pid: str, edit: PreviewRequest):
        project = get_project(pid)
        if edit.index >= len(edit.scenes):
            raise HTTPException(404, "找不到这个分镜")
        directory = store.directory / "assets" / project["id"]
        for scene in edit.scenes:
            if scene.asset_id and photo_path(directory, scene.asset_id) is None:
                raise HTTPException(400, "照片不存在或不属于当前作品")
        changes = edit.model_dump(exclude={"version", "index"})
        if "merchant" not in edit.model_fields_set:
            changes.pop("merchant", None)
        project.update(changes)
        buffer = io.BytesIO()
        scene_image(project, edit.index, asset_dir=directory).save(buffer, format="PNG")
        return Response(buffer.getvalue(), media_type="image/png")

    @app.get("/api/projects/{pid}/storyboard.json")
    def storyboard_download(pid: str):
        return Response(json.dumps(get_project(pid), ensure_ascii=False, indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="storyboard.json"'})

    def work(job, event):
        def check_cancel():
            if event.is_set():
                raise RenderCancelled()
        def progress(value, message):
            with render_lock:
                check_cancel()
                job.update(status="rendering", progress=value, message=message)
                store.save_job(job)
        directory = store.directory / "exports" / job["id"]
        try:
            progress(3, "准备画面与中文排版")
            metadata = render(job["snapshot"], directory, job["music"], progress,
                              store.directory / "assets" / job["project_id"], job.get("narration", False),
                              job["quality"],job["speech_rate"],job["music_volume"],check_cancel)
            job.update(status="completed", progress=100, message="成片已就绪", completed_at=now(),
                       bytes=(directory/"video.mp4").stat().st_size, **metadata)
        except RenderCancelled:
            job.update(status="cancelled", message="导出已取消，作品和照片仍然保留")
        except NarrationError as exc:
            job.update(status="failed", error=str(exc))
        except Exception:
            log.exception("Video export failed: %s", job["id"])
            job.update(status="failed", error="视频合成失败，请重试。若持续失败，请检查磁盘空间与运行日志。")
        finally:
            with render_lock:
                if event.is_set():
                    job.update(status="cancelled", message="导出已取消，作品和照片仍然保留")
                if job["status"] in ("cancelled", "failed"):
                    shutil.rmtree(directory, ignore_errors=True)
                store.save_job(job)
                controls.pop(job["id"], None)

    @app.post("/api/projects/{pid}/preflight")
    def preflight(pid: str, request: RenderRequest):
        project = get_project(pid)
        if project["version"] != request.version:
            raise HTTPException(409, "作品已更新，请保存或重新打开后检查。")
        return export_check(project, store.directory, request, narration_available())

    @app.post("/api/projects/{pid}/render")
    def export_video(pid: str, request: RenderRequest):
        with render_lock:
            project = get_project(pid)
            if request.version != project["version"]:
                raise HTTPException(409, "项目已更新，请保存并刷新分镜后重试。")
            if request.narration and not narration_available():
                raise HTTPException(400, "此设备未提供本机中文配音，请关闭配音后导出。macOS 可在系统设置中安装婷婷语音。")
            checks = export_check(project, store.directory, request, narration_available())
            if not checks["ready"]:
                raise HTTPException(400, " ".join(checks["blocking"]))
            jobs = store.jobs()
            for job in jobs:
                if (job["project_id"] == pid and job["version"] == request.version and job["music"] == request.music
                        and job.get("narration", False) == request.narration
                        and job.get("quality", "720p") == request.quality
                        and job.get("speech_rate", 210) == request.speech_rate
                        and job.get("music_volume", .5) == request.music_volume
                        and job["status"] in ("queued", "rendering", "completed")):
                    if job["status"] == "completed" and not (store.directory / "exports" / job["id"] / "video.mp4").is_file():
                        job.update(status="failed", error="成片文件已丢失，请重新导出。")
                        store.save_job(job)
                        continue
                    return public_job(job)
            if sum(j["status"] in ("queued", "rendering", "cancelling") for j in jobs) >= 3:
                raise HTTPException(429, "导出队列已满，请等待当前任务完成。")
            job = {"id": str(uuid4()), "project_id": pid, "version": project["version"],
                   "status": "queued", "progress": 0, "message": "等待渲染", "created_at": now(),
                   "music": request.music, "narration": request.narration, "materials": True, "snapshot": project, "title": project["title"],
                   "quality":request.quality,"speech_rate":request.speech_rate,"music_volume":request.music_volume,
                   "duration": project["duration"], "aspect": project["aspect"]}
            store.save_job(job)
            event = threading.Event()
            future = executor.submit(work, job.copy(), event)
            controls[job["id"]] = (event, future)
            return public_job(job)

    @app.post("/api/jobs/{jid}/cancel")
    def cancel_job(jid: str):
        with render_lock:
            job = get_job(jid)
            if job["status"] in ("completed", "failed"):
                raise HTTPException(409, "任务已经结束，无需取消。")
            if job["status"] == "cancelled":
                return public_job(job)
            control = controls.get(jid)
            if control is None:
                raise HTTPException(409, "任务已中断，请重新打开作品。")
            event, future = control
            event.set()
            if future.cancel():
                job.update(status="cancelled", message="导出已取消，作品和照片仍然保留")
                controls.pop(jid, None)
            else:
                job.update(status="cancelling", message="正在取消并清理临时文件…")
            store.save_job(job)
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

    @app.get("/api/jobs/{jid}/materials/{name}")
    def material_download(jid: str, name: str):
        if name not in {"cover.png", "post.txt", "storyboard.json"}:
            raise HTTPException(404, "找不到这个文件")
        job = get_job(jid)
        if job["status"] != "completed":
            raise HTTPException(409, "素材尚未就绪")
        path = store.directory / "exports" / job["id"] / name
        if not path.is_file():
            raise HTTPException(404, "旧版任务没有这份素材，请修改并重新导出")
        return FileResponse(path, filename=name)

    @app.get("/api/jobs/{jid}/storyboard.json")
    def job_storyboard(jid: str):
        job = get_job(jid)
        path = store.directory / "exports" / job["id"] / "storyboard.json"
        if job["status"] == "completed" and path.is_file():
            return FileResponse(path, filename="storyboard.json")
        return Response(json.dumps(job["snapshot"], ensure_ascii=False, indent=2), media_type="application/json",
                        headers={"Content-Disposition": 'attachment; filename="storyboard.json"'})

    @app.get("/api/jobs/{jid}/materials.zip")
    def bundle_download(jid: str):
        job = get_job(jid)
        if job["status"] != "completed":
            raise HTTPException(409, "成片尚未完成，请稍后下载")
        directory = store.directory / "exports" / job["id"]
        names = ["video.mp4", "subtitles.srt", "cover.png", "post.txt", "storyboard.json"]
        if not all((directory / name).is_file() for name in names):
            raise HTTPException(404, "素材不完整，请保存分镜并重新导出")
        path = directory / "materials.zip"
        if not path.is_file():
            temp = directory / f"materials-{uuid4().hex}.part"
            try:
                with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                    for name in names:
                        bundle.write(directory / name, name)
                temp.replace(path)
            finally:
                temp.unlink(missing_ok=True)
        return FileResponse(path, media_type="application/zip", filename="frame-materials.zip")

    app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")
    return app


app = create_app()
