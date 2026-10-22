import importlib
import io
import struct
import subprocess
import sys
import threading
import time
import wave
from collections import namedtuple

import imageio_ffmpeg
import pytest
from PIL import Image

from app.process import RenderCancelled, run_process
from test_studio import create, edit_body, studio, wait_job
from test_merchant import upload


@pytest.mark.parametrize("aspect,size",[("9:16",(1080,1920)),("16:9",(1920,1080)),("1:1",(1080,1080))])
def test_1080p_real_video_cover_and_distinct_settings(studio,aspect,size):
    client,store=studio;p=create(client,aspect=aspect)
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,scenes=[{"heading":"清晰成片","caption":"检查画幅和完整解码。","duration":2,"motion":"still"}])).json()
    body={"version":p["version"],"music":False,"quality":"1080p"}
    check=client.post(f"/api/projects/{p['id']}/preflight",json=body).json()
    assert check["ready"] and (check["width"],check["height"])==size
    job=wait_job(client,client.post(f"/api/projects/{p['id']}/render",json=body).json()["id"])
    assert job["status"]=="completed",job
    assert (job["width"],job["height"])==size
    path=store.directory/"exports"/job["id"]/"video.mp4"
    frames=imageio_ffmpeg.read_frames(str(path));meta=next(frames);next(frames);frames.close()
    assert meta["size"]==size
    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-v","error","-i",str(path),"-f","null","-"],capture_output=True,timeout=30)
    assert result.returncode==0 and not result.stderr
    with Image.open(store.directory/"exports"/job["id"]/"cover.png") as cover:
        assert cover.size==size
    snapshot=client.get(f"/api/jobs/{job['id']}/storyboard.json").json()
    assert snapshot["export_settings"]["quality"]=="1080p"
    assert client.post(f"/api/projects/{p['id']}/render",json=body).json()["id"]==job["id"]
    assert client.post(f"/api/jobs/{job['id']}/cancel",json={}).status_code==409
    lower=client.post(f"/api/projects/{p['id']}/render",json=body | {"quality":"720p"}).json()
    assert lower["id"]!=job["id"]
    assert wait_job(client,lower["id"])["status"]=="completed"


def test_cancel_queued_and_running_jobs_leaves_projects_intact(studio,monkeypatch):
    client,store=studio;main=importlib.import_module("app.main")
    entered=threading.Event();called=[]
    def rendering(*args):
        called.append(args[0]["id"]);entered.set()
        directory=args[1];directory.mkdir(parents=True,exist_ok=True)
        (directory/"video.part.mp4").write_bytes(b"partial")
        for _ in range(300):
            args[-1]()
            time.sleep(.01)
        raise AssertionError("Cancellation did not reach renderer")
    monkeypatch.setattr(main,"render",rendering)
    p=create(client);q=create(client)
    first=client.post(f"/api/projects/{p['id']}/render",json={"version":1}).json()
    assert entered.wait(2)
    second=client.post(f"/api/projects/{q['id']}/render",json={"version":1}).json()
    assert client.post(f"/api/jobs/{second['id']}/cancel",json={}).json()["status"]=="cancelled"
    assert client.post(f"/api/jobs/{second['id']}/cancel",json={}).json()["status"]=="cancelled"
    assert client.post(f"/api/jobs/{first['id']}/cancel",json={}).status_code==200
    assert wait_job(client,first["id"])["status"]=="cancelled"
    assert called==[p["id"]]
    assert not (store.directory/"exports"/first["id"]).exists()
    assert client.get(f"/api/projects/{p['id']}").json()["version"]==1
    assert client.get(f"/api/jobs/{first['id']}/video.mp4").status_code==409


def test_subprocess_cancellation_and_timeout_are_bounded():
    calls=0
    def cancel():
        nonlocal calls
        calls+=1
        if calls>2:raise RenderCancelled()
    started=time.monotonic()
    with pytest.raises(RenderCancelled):
        run_process([sys.executable,"-c","import time; time.sleep(30)"],cancel=cancel)
    assert time.monotonic()-started<3
    with pytest.raises(subprocess.TimeoutExpired):
        run_process([sys.executable,"-c","import time; time.sleep(30)"],timeout=.1)
    completed=run_process([sys.executable,"-c","print('finished')"])
    assert completed.stdout.strip()==b"finished" and completed.returncode==0


def test_preflight_blocks_missing_photos_and_low_disk(studio,monkeypatch):
    client,store=studio;p=create(client)
    asset=upload(client,p).json()["asset_id"]
    p["scenes"][0]["asset_id"]=asset
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p)).json()
    body={"version":p["version"],"music":False}
    check=client.post(f"/api/projects/{p['id']}/preflight",json=body).json()
    assert check["ready"] and any("偏小" in w for w in check["warnings"])
    (store.directory/"assets"/p["id"]/f"{asset}.jpg").unlink()
    check=client.post(f"/api/projects/{p['id']}/preflight",json=body).json()
    assert not check["ready"] and "第 1 幕" in check["blocking"][0]
    assert client.post(f"/api/projects/{p['id']}/render",json=body).status_code==400
    checks=importlib.import_module("app.checks");usage=namedtuple("Usage","total used free")
    monkeypatch.setattr(checks.shutil,"disk_usage",lambda _:usage(100,90,10))
    q=create(client)
    check=client.post(f"/api/projects/{q['id']}/preflight",json={"version":1}).json()
    assert not check["ready"] and any("磁盘" in item for item in check["blocking"])


def test_voice_preview_rate_and_temporary_cleanup(studio,monkeypatch):
    client,store=studio;main=importlib.import_module("app.main")
    monkeypatch.setattr(main,"narration_available",lambda:True)
    spoken=[]
    def voice(text,path,convert,rate=210):
        spoken.append((text,rate))
        with wave.open(str(path),"wb") as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(22050)
            out.writeframes(struct.pack("<h",1200)*22050)
        return 1
    monkeypatch.setattr(main,"synthesize",voice)
    response=client.post("/api/narration/preview",json={"text":"欢迎到店。","speech_rate":170})
    assert response.status_code==200 and response.headers["content-type"]=="audio/wav"
    with wave.open(io.BytesIO(response.content)) as sound:
        assert sound.getnframes()==22050
    assert spoken==[("欢迎到店。",170)] and not list(store.directory.glob("voice-preview-*"))
    assert client.post("/api/narration/preview",json={"text":" ","speech_rate":170}).status_code==422
    assert client.post("/api/narration/preview",json={"text":"你好","speech_rate":500}).status_code==422


@pytest.mark.parametrize("extra",[{"quality":"4k"},{"music_volume":2},{"speech_rate":400}])
def test_invalid_export_settings(studio,extra):
    client,_=studio;p=create(client)
    assert client.post(f"/api/projects/{p['id']}/render",json={"version":1,**extra}).status_code==422
