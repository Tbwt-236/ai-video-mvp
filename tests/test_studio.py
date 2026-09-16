import importlib
import json
import subprocess
import threading
import time

import imageio_ffmpeg
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Brief
from app.store import Store, now
from app.storyboard import generate_storyboard, offline_storyboard


@pytest.fixture
def studio(tmp_path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    app = create_app(tmp_path)
    with TestClient(app) as client:
        yield client, app.state.store


def create(client, **extra):
    response = client.post("/api/projects", json={"prompt": "做一支城市漫游的短片", **extra})
    assert response.status_code == 201, response.text
    return response.json()


def edit_body(project, **extra):
    return {key: project[key] for key in ["title", "style", "aspect", "scenes", "version"]} | extra


def wait_job(client, jid):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        job = client.get(f"/api/jobs/{jid}").json()
        if job["status"] in ["completed", "failed"]:
            return job
        time.sleep(.1)
    pytest.fail("render timed out")


def test_create_edit_persist_and_conflict(studio):
    client, store = studio
    assert client.get("/api/health").json()["status"] == "ok"
    project = create(client, duration=30, style="tech")
    assert sum(s["duration"] for s in project["scenes"]) == 30
    assert project["source"] == "template"
    payload = edit_body(project, title="修改后的作品")
    updated = client.put(f"/api/projects/{project['id']}", json=payload)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert client.put(f"/api/projects/{project['id']}", json=payload).status_code == 409
    assert Store(store.directory).get_project(project["id"])["title"] == "修改后的作品"
    assert client.get(f"/api/projects/{project['id']}/storyboard.json").json()["version"] == 2
    assert client.get(f"/api/projects/{project['id']}/scenes/0.png").headers["content-type"] == "image/png"
    assert client.get(f"/api/projects/{project['id']}/scenes/-1.png").status_code == 404


@pytest.mark.parametrize("payload", [
    {"prompt": "    "}, {"prompt": "a"*801}, {"prompt": "测试一个短片", "duration": 200},
    {"prompt": "测试一个短片", "aspect": "invalid"}, {"prompt": "测试一个短片", "mode": "fake"},
])
def test_bad_briefs(studio, payload):
    client, _ = studio
    assert client.post("/api/projects", json=payload).status_code == 422


def test_invalid_scenes_and_missing_project(studio):
    client, _ = studio
    p = create(client)
    base = edit_body(p)
    assert client.put(f"/api/projects/{p['id']}", json=base | {"title": " "}).status_code == 422
    assert client.put(f"/api/projects/{p['id']}", json=base | {"scenes": []}).status_code == 422
    long = [{"heading": "标题", "caption": "字幕", "duration": 20}] * 4
    assert client.put(f"/api/projects/{p['id']}", json=base | {"scenes": long}).status_code == 422
    assert client.get("/api/projects/no-such-project").status_code == 404
    assert client.get("/api/jobs/no-such-job/video.mp4").status_code == 404


def test_ai_mode_never_silently_falls_back(studio):
    client, _ = studio
    assert not client.get("/api/config").json()["ai_available"]
    response = client.post("/api/projects", json={"prompt": "写一个独立咖啡馆短片", "mode": "ai"})
    assert response.status_code == 400
    assert "密钥" in response.json()["detail"]


def test_ai_adapter_schema_and_auth(monkeypatch):
    from app import storyboard
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-only-key")
    captured = {}

    class Response:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"title": "AI 编写", "scenes": [
                {"heading": f"画面{i}", "caption": "有意义的中文内容"} for i in range(3)]})}}]}

    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            captured.update(url=url, **kwargs)
            return Response()

    monkeypatch.setattr(storyboard.httpx, "Client", Client)
    result = generate_storyboard(Brief(prompt="写一个独立咖啡馆短片", mode="ai"))
    assert result["source"] == "deepseek"
    assert sum(s["duration"] for s in result["scenes"]) == 15
    assert captured["url"] == "https://api.deepseek.com/chat/completions"
    assert captured["json"]["response_format"] == {"type": "json_object"}
    Response.status_code = 401
    with pytest.raises(ValueError, match="密钥无效"):
        generate_storyboard(Brief(prompt="写一个独立咖啡馆短片", mode="ai"))


@pytest.mark.parametrize("duration", [15, 30, 45, 60])
def test_template_durations(duration):
    brief = Brief(prompt="一款全新的学习工具宣传短片", duration=duration)
    result = offline_storyboard(brief)
    assert sum(s["duration"] for s in result["scenes"]) == duration
    assert all(2 <= s["duration"] <= 20 for s in result["scenes"])


def test_local_origin_and_files(studio):
    client, _ = studio
    assert client.post("/api/projects", json={"prompt": "测试一个短片"}, headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/projects", content="test").status_code == 415
    assert client.post("/api/projects", content="x"*33000, headers={"Content-Type": "application/json"}).status_code == 413
    for path in ["/.env", "/data/studio.sqlite3", "/app/main.py", "/requirements.txt"]:
        assert client.get(path).status_code == 404
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/").status_code == 200


def test_restart_recovers_unfinished_tasks(tmp_path):
    store = Store(tmp_path)
    store.save_job({"id": "interrupted", "project_id": "p", "status": "rendering", "created_at": now()})
    with TestClient(create_app(tmp_path)) as client:
        job = client.get("/api/jobs/interrupted").json()
        assert job["status"] == "failed"
        assert "重启" in job["error"]


def test_queue_dedup_failure_and_immutable_snapshot(studio, monkeypatch):
    client, store = studio
    main = importlib.import_module("app.main")
    release = threading.Event()

    def blocked_render(*args):
        release.wait(10)
        raise RuntimeError("deliberate test failure")

    monkeypatch.setattr(main, "render", blocked_render)
    try:
        projects = [create(client) for _ in range(4)]
        jobs = []
        for project in projects[:3]:
            response = client.post(f"/api/projects/{project['id']}/render", json={"version": 1})
            assert response.status_code == 200
            jobs.append(response.json())
        p = projects[0]
        assert client.post(f"/api/projects/{p['id']}/render", json={"version": 1}).json()["id"] == jobs[0]["id"]
        assert client.post(f"/api/projects/{projects[3]['id']}/render", json={"version": 1}).status_code == 429
        assert client.get(f"/api/jobs/{jobs[0]['id']}/video.mp4").status_code == 409
        client.put(f"/api/projects/{p['id']}", json=edit_body(p, title="新版本"))
        assert store.get_job(jobs[0]["id"])["snapshot"]["title"] == p["title"]
        assert client.post(f"/api/projects/{p['id']}/render", json={"version": 1}).status_code == 409
    finally:
        release.set()
    assert wait_job(client, jobs[0]["id"])["status"] == "failed"


@pytest.mark.parametrize("aspect,style,music,size", [
    ("9:16", "cinema", True, (720,1280)),
    ("16:9", "editorial", False, (1280,720)),
    ("1:1", "tech", True, (720,720)),
])
def test_real_mp4_export_and_range_requests(studio, aspect, style, music, size):
    client, store = studio
    p = create(client, aspect=aspect, style=style)
    scenes = [{"heading": "测试中文画面", "caption": "中文、English、数字 123 正常显示。", "duration": 2},
              {"heading": "第二个镜头", "caption": "字幕和总时长应与分镜一致。", "duration": 2}]
    p = client.put(f"/api/projects/{p['id']}", json=edit_body(p, scenes=scenes)).json()
    job = client.post(f"/api/projects/{p['id']}/render", json={"version": p["version"], "music": music}).json()
    job = wait_job(client, job["id"])
    assert job["status"] == "completed", job
    path = store.directory / "exports" / job["id"] / "video.mp4"
    frames = imageio_ffmpeg.read_frames(str(path))
    metadata = next(frames)
    next(frames)  # Decode an actual frame, not merely the MP4 container.
    frames.close()
    assert metadata["size"] == size
    assert metadata["fps"] == 24
    assert abs(metadata["duration"] - 4) < .1
    decoded = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "error", "-i", str(path), "-f", "null", "-"], capture_output=True, timeout=30)
    assert decoded.returncode == 0, decoded.stderr
    ranged = client.get(f"/api/jobs/{job['id']}/video.mp4", headers={"Range": "bytes=0-99"})
    assert ranged.status_code == 206 and len(ranged.content) == 100
    download = client.get(f"/api/jobs/{job['id']}/video.mp4?download=true")
    assert "attachment" in download.headers["content-disposition"]
    subtitles = client.get(f"/api/jobs/{job['id']}/subtitles.srt").text
    assert "00:00:02,000 --> 00:00:04,000" in subtitles
    assert "测试中文画面" in subtitles
    duplicate = client.post(f"/api/projects/{p['id']}/render", json={"version": p["version"], "music": music}).json()
    assert duplicate["id"] == job["id"]
    if aspect == "1:1":
        # A missing artifact must not trap the user behind a completed cache entry.
        path.unlink()
        replacement = client.post(f"/api/projects/{p['id']}/render", json={"version": p["version"], "music": music}).json()
        assert replacement["id"] != job["id"]
        assert wait_job(client, replacement["id"])["status"] == "completed"
