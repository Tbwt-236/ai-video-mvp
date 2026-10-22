import importlib
import io
import math
import struct
import wave

import imageio_ffmpeg
import pytest
from PIL import Image

from test_studio import create, edit_body, studio, wait_job


def photo_bytes(format="PNG"):
    output = io.BytesIO()
    photo = Image.new("RGB", (240, 320), (240, 30, 20))
    exif = Image.Exif()
    exif[270] = "private original description"
    photo.save(output, format, exif=exif)
    return output.getvalue()


def upload(client, project, content=None):
    return client.post(f"/api/projects/{project['id']}/assets", content=content or photo_bytes(),
                       headers={"Content-Type": "image/png"})


@pytest.mark.parametrize("duration", [15, 30, 45, 60])
def test_merchant_uses_supplied_facts_only(studio, duration):
    client, _ = studio
    facts = {"store_name": "雨后咖啡", "product": "燕麦拿铁", "selling_point": "窗边有座位", "address": "试验路 20 号", "duration": duration}
    response = client.post("/api/merchant-projects", json=facts)
    assert response.status_code == 201
    p = response.json()
    assert p["source"] == "merchant_template"
    assert sum(s["duration"] for s in p["scenes"]) == duration
    captions = " ".join(s["caption"] for s in p["scenes"])
    assert all(v in captions for k, v in facts.items() if k not in {"duration", "store_name"})
    assert "优惠" not in captions and "限时" not in captions
    assert p["merchant"]["offer"] == ""
    for key in ["store_name", "product", "selling_point", "address", "cta"]:
        assert client.post("/api/merchant-projects", json=facts | {key: "  "}).status_code == 422


@pytest.mark.parametrize("format", ["PNG", "JPEG", "WEBP"])
def test_photo_normalized_and_isolated_by_project(studio, format):
    client, store = studio
    p = create(client)
    before = client.get(f"/api/projects/{p['id']}/scenes/0.png").content
    response = upload(client, p, photo_bytes(format))
    assert response.status_code == 201, response.text
    asset = response.json()["asset_id"]
    with Image.open(store.directory / "assets" / p["id"] / f"{asset}.jpg") as image:
        assert image.format == "JPEG" and image.mode == "RGB" and not image.getexif()
    p["scenes"][0]["asset_id"] = asset
    updated = client.put(f"/api/projects/{p['id']}", json=edit_body(p))
    assert updated.status_code == 200
    after = client.get(f"/api/projects/{p['id']}/scenes/0.png").content
    assert after != before
    with Image.open(io.BytesIO(after)) as rendered:
        r, g, b = rendered.getpixel((360, 400))
        assert r > 3*g and r > 3*b  # Uploaded photo actually reaches the composition.
    other = create(client)
    other["scenes"][0]["asset_id"] = asset
    assert client.put(f"/api/projects/{other['id']}", json=edit_body(other)).status_code == 400
    other["scenes"][0]["asset_id"] = "../../outside"
    assert client.put(f"/api/projects/{other['id']}", json=edit_body(other)).status_code == 422
    p = updated.json()
    p["scenes"][0]["asset_id"] = None
    assert client.put(f"/api/projects/{p['id']}", json=edit_body(p)).status_code == 200
    assert client.get(f"/api/projects/{p['id']}/scenes/0.png").content == before
    assert (store.directory / "assets" / p["id"] / f"{asset}.jpg").exists()  # Old export snapshots retain their source.


def test_bad_photos_and_stream_limits(studio, monkeypatch):
    client, _ = studio
    p = create(client)
    route = f"/api/projects/{p['id']}/assets"
    assert upload(client, p, b"not a photo").status_code == 400
    assert client.post(route, content=photo_bytes(), headers={"Content-Type": "image/svg+xml"}).status_code == 415
    assert client.post(route, content=photo_bytes(), headers={"Content-Type": "image/png", "Origin": "https://elsewhere.test"}).status_code == 403
    assert client.post(route, content=(b"x"*1024*1024 for _ in range(9)), headers={"Content-Type": "image/png"}).status_code == 413
    assert client.post("/api/projects", content=(b"x"*4096 for _ in range(9)), headers={"Content-Type": "application/json"}).status_code == 413
    from app import assets
    monkeypatch.setattr(assets, "MAX_PIXELS", 100)
    assert upload(client, p).status_code == 400
    monkeypatch.setattr(assets, "MAX_PIXELS", 20_000_000)
    monkeypatch.setattr(assets, "MAX_ASSETS", 1)
    assert upload(client, p).status_code == 201
    assert upload(client, p).status_code == 400


def test_voice_unavailable_is_explicit(studio, monkeypatch):
    client, _ = studio
    main = importlib.import_module("app.main")
    monkeypatch.setattr(main, "narration_available", lambda: False)
    assert client.get("/api/config").json()["narration_available"] is False
    p = create(client)
    assert client.post(f"/api/projects/{p['id']}/render", json={"version": 1, "narration": True}).status_code == 400


@pytest.mark.parametrize("music", [True, False])
def test_narrated_export_sync_materials_and_snapshot(studio, monkeypatch, music):
    client, store = studio
    main = importlib.import_module("app.main")
    renderer = importlib.import_module("app.renderer")
    monkeypatch.setattr(main, "narration_available", lambda: True)
    spoken = []

    def fake_voice(text, destination, convert, **options):
        spoken.append(text)
        with wave.open(str(destination), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(22050)
            audio.writeframes(b"".join(struct.pack("<h", int(3000*math.sin(i*.1))) for i in range(round(22050*2.23))))
        return 2.23

    monkeypatch.setattr(renderer, "synthesize", fake_voice)
    p = create(client)
    asset = upload(client, p).json()["asset_id"]
    scenes = [{"heading": "第一幕", "caption": "这一句需要完整说完。", "duration": 2, "asset_id": asset},
              {"heading": "第二幕", "caption": "下一幕字幕随后出现。", "duration": 2}]
    p = client.put(f"/api/projects/{p['id']}", json=edit_body(p, scenes=scenes)).json()
    payload = {"version": p["version"], "music": music, "narration": True}
    job = client.post(f"/api/projects/{p['id']}/render", json=payload).json()
    job = wait_job(client, job["id"])
    assert job["status"] == "completed", job
    assert job["duration"] == pytest.approx(5.667, abs=.001)
    assert spoken == [s["caption"] for s in scenes]
    output = store.directory / "exports" / job["id"]
    frames = imageio_ffmpeg.read_frames(str(output / "video.mp4"))
    metadata = next(frames)
    next(frames)
    frames.close()
    assert metadata["duration"] == pytest.approx(job["duration"], abs=.08)
    assert metadata["audio_codec"] == "aac"
    srt = (output / "subtitles.srt").read_text()
    assert "00:00:00,300 --> 00:00:02,530" in srt
    assert "00:00:03,133 --> 00:00:05,363" in srt
    snapshot = client.get(f"/api/jobs/{job['id']}/materials/storyboard.json").json()
    assert snapshot["duration"] == pytest.approx(job["duration"], abs=.001)
    assert client.get(f"/api/projects/{p['id']}").json()["duration"] == 4
    assert client.get(f"/api/jobs/{job['id']}/materials/cover.png").headers["content-type"] == "image/png"
    assert scenes[0]["caption"] in client.get(f"/api/jobs/{job['id']}/materials/post.txt").text
    assert client.get(f"/api/jobs/{job['id']}/materials/studio.sqlite3").status_code == 404
    assert client.post(f"/api/projects/{p['id']}/render", json=payload).json()["id"] == job["id"]
    silent = client.post(f"/api/projects/{p['id']}/render", json=payload | {"narration": False}).json()
    assert silent["id"] != job["id"]
    assert wait_job(client, silent["id"])["duration"] == 4


def test_voice_failure_is_actionable(studio, monkeypatch):
    from app.narration import NarrationError
    client, _ = studio
    main = importlib.import_module("app.main")
    renderer = importlib.import_module("app.renderer")
    monkeypatch.setattr(main, "narration_available", lambda: True)

    def fail(*args, **kwargs):
        raise NarrationError("关闭配音后重试")

    monkeypatch.setattr(renderer, "synthesize", fail)
    p = create(client)
    job = client.post(f"/api/projects/{p['id']}/render", json={"version": 1, "narration": True}).json()
    completed = wait_job(client, job["id"])
    assert completed["status"] == "failed"
    assert completed["error"] == "关闭配音后重试"
