import pytest

from app.process import RenderCancelled
from app.renderer import make_music
from test_studio import create, studio


def test_queue_keeps_all_active_jobs_and_orders_waiting_positions(studio):
    client,store=studio;p=create(client)
    for index,status in enumerate(["queued","rendering","queued","completed","cancelled","failed"]):
        store.save_job({"id":f"job-{index}","project_id":p["id"],"version":1,"status":status,
                        "progress":0,"created_at":f"2026-10-23T00:0{index}:00+00:00","snapshot":p})
    result=client.get("/api/jobs?limit=1").json()
    assert result["active"]==3 and len(result["jobs"])==4
    jobs={job["id"]:job for job in result["jobs"]}
    assert jobs["job-0"]["queue_position"]==1 and jobs["job-2"]["queue_position"]==2
    assert jobs["job-1"]["queue_position"] is None and "job-5" in jobs
    assert all("snapshot" not in job for job in result["jobs"])
    assert client.get("/api/jobs?limit=0").status_code==422
    assert client.get("/api/jobs?limit=101").status_code==422


def test_missing_historical_downloads_return_recoverable_errors(studio):
    client,store=studio;p=create(client)
    store.save_job({"id":"old-job","project_id":p["id"],"version":1,"status":"completed","created_at":"2026"})
    for name in ["subtitles.srt","storyboard.json","materials.zip","video.mp4"]:
        response=client.get("/api/jobs/old-job/"+name)
        assert response.status_code==404 and response.json()["detail"]


def test_music_generation_honors_cancellation(tmp_path):
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if calls==2:raise RenderCancelled()
    with pytest.raises(RenderCancelled):
        make_music(tmp_path/"music.wav",120,cancel)
    assert calls==2
