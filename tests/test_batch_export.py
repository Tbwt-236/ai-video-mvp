import importlib
import sqlite3
import subprocess
import threading

import imageio_ffmpeg
import pytest

from app.process import RenderCancelled
from test_merchant import upload
from test_studio import create, edit_body, studio, wait_job


def target(project):
    return {"project_id":project["id"], "version":project["version"]}


def test_batch_exports_three_real_ratios_and_reuses_finished_jobs(studio):
    client, store = studio
    project = create(client)
    project = client.put(f"/api/projects/{project['id']}", json=edit_body(project, scenes=[
        {"heading":"一份内容，多种画幅", "caption":"批量导出仍能独立编辑。", "duration":2, "motion":"still"}
    ])).json()
    copies = client.post(f"/api/projects/{project['id']}/variants", json=edit_body(project,
        aspects=["9:16","16:9","1:1"])).json()
    payload = {"projects":[target(item) for item in copies], "settings":{"music":False,"quality":"1080p"}}
    response = client.post("/api/render-batch", json=payload)
    assert response.status_code == 200, response.text
    jobs = response.json()["jobs"]
    assert [job["project_id"] for job in jobs] == [item["id"] for item in copies]
    for job,size in zip(jobs, [(1080,1920),(1920,1080),(1080,1080)]):
        done = wait_job(client, job["id"])
        assert done["status"] == "completed" and done["missing_files"] == [], done
        assert (done["width"],done["height"]) == size
        video = store.directory / "exports" / job["id"] / "video.mp4"
        result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-v","error","-i",str(video),"-f","null","-"],
                                capture_output=True,timeout=30)
        assert result.returncode == 0 and not result.stderr
    again = client.post("/api/render-batch",json=payload).json()["jobs"]
    assert [job["id"] for job in again] == [job["id"] for job in jobs]
    assert len(store.jobs()) == 3
    assert client.get(f"/api/projects/{project['id']}").json() == project


def test_batch_validates_every_project_before_starting_any_job(studio):
    client, store = studio
    projects = [create(client) for _ in range(3)]
    payload = {"projects":[target(item) for item in projects], "settings":{"music":False}}
    latest = client.put(f"/api/projects/{projects[2]['id']}", json=edit_body(projects[2],title="另一窗口已修改")).json()
    assert client.post("/api/render-batch",json=payload).status_code == 409
    assert store.jobs() == []
    asset = upload(client,latest).json()["asset_id"]
    latest["scenes"][0]["asset_id"] = asset
    latest = client.put(f"/api/projects/{latest['id']}",json=edit_body(latest)).json()
    (store.directory / "assets" / latest["id"] / f"{asset}.jpg").unlink()
    payload["projects"][2] = target(latest)
    blocked = client.post("/api/render-batch",json=payload)
    assert blocked.status_code == 400 and "照片" in blocked.json()["detail"]
    assert store.jobs() == []


def test_batch_capacity_reservation_is_all_or_nothing_and_counts_reused_jobs_once(studio,monkeypatch):
    client, store = studio
    main = importlib.import_module("app.main")
    entered, release = threading.Event(), threading.Event()
    def blocked(*args):
        entered.set()
        release.wait(10)
        raise RenderCancelled()
    monkeypatch.setattr(main,"render",blocked)
    projects = [create(client) for _ in range(4)]
    try:
        first = client.post(f"/api/projects/{projects[0]['id']}/render",json={"version":1,"music":False}).json()
        assert entered.wait(2)
        response = client.post("/api/render-batch",json={"projects":[target(item) for item in projects[1:]],"settings":{"music":False}})
        assert response.status_code == 429 and "未新增任务" in response.json()["detail"]
        assert len(store.jobs()) == 1
        payload = {"projects":[target(item) for item in projects[:3]],"settings":{"music":False}}
        accepted = client.post("/api/render-batch",json=payload)
        assert accepted.status_code == 200,accepted.text
        jobs = accepted.json()["jobs"]
        assert jobs[0]["id"] == first["id"] and len(store.jobs()) == 3
        repeated = client.post("/api/render-batch",json=payload).json()["jobs"]
        assert [j["id"] for j in repeated] == [j["id"] for j in jobs]
        assert client.get("/api/jobs").json()["active"] == 3
    finally:
        release.set()


@pytest.mark.parametrize("kind", ["empty","duplicate","too_many","bad_id"])
def test_invalid_batches_never_create_jobs(studio,kind):
    client, store = studio
    project = create(client)
    items = {"empty":[],"duplicate":[target(project)]*2,"too_many":[target(project)]*4,
             "bad_id":[{"project_id":"../no", "version":1}]}[kind]
    assert client.post("/api/render-batch",json={"projects":items}).status_code == 422
    assert store.jobs() == []


def test_batch_database_reservation_rolls_back_on_conflict(studio):
    _, store = studio
    existing = {"id":"reserved", "project_id":"project", "status":"failed", "created_at":"2026"}
    store.save_job(existing)
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_jobs([{**existing,"id":"should-not-exist"},existing])
    assert store.get_job("should-not-exist") is None
    assert store.get_job(existing["id"]) == existing
