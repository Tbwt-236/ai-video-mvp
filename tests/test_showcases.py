import io
import json
import zipfile

import pytest
from PIL import Image

from test_portability import import_zip
from test_studio import studio, wait_job


@pytest.mark.parametrize("key,aspect",[("coffee","9:16"),("flowers","1:1"),("bakery","16:9")])
def test_showcase_has_real_editable_photos_and_disclosure(studio,key,aspect):
    client,store=studio
    catalog=client.get("/api/config").json()["showcases"]
    assert {item["id"] for item in catalog}=={"coffee","flowers","bakery"}
    assert client.get(f"/showcase/{key}.png").headers["content-type"]=="image/png"
    response=client.post(f"/api/showcases/{key}",json={"aspect":aspect})
    assert response.status_code==201,response.text
    project=response.json()
    assert project["example"] and project["example_assets"]=="ai" and project["aspect"]==aspect
    assert len(project["scenes"])==3 and sum(s["duration"] for s in project["scenes"])==15
    assets=client.get(f"/api/projects/{project['id']}/assets").json()
    assert len(assets)==1 and all(scene["asset_id"]==assets[0]["asset_id"] for scene in project["scenes"])
    preview=client.get(f"/api/projects/{project['id']}/scenes/0.png")
    with Image.open(io.BytesIO(preview.content)) as image:
        width,height=image.size
        ratio=width/height
        assert abs(ratio-{"9:16":9/16,"1:1":1,"16:9":16/9}[aspect])<.01
    copy=client.post(f"/api/showcases/{key}",json={"aspect":aspect}).json()
    assert copy["id"]!=project["id"] and copy["scenes"][0]["asset_id"]!=project["scenes"][0]["asset_id"]
    package=client.get(f"/api/projects/{project['id']}/package.zip").content
    imported=import_zip(client,package).json()
    assert imported["example_assets"]=="ai" and imported["example"]


def test_invalid_showcase_creates_nothing(studio):
    client,store=studio
    before=len(store.projects())
    assert client.get("/showcase/missing.png").status_code==404
    assert client.post("/api/showcases/missing",json={}).status_code==400
    assert client.post("/api/showcases/bakery",json={"aspect":"bad"}).status_code==422
    assert len(store.projects())==before


def test_showcase_export_preserves_ai_origin(studio):
    client,store=studio
    project=client.post("/api/showcases/bakery",json={}).json()
    project["scenes"]=project["scenes"][:1]
    project["scenes"][0]["duration"]=2
    project=client.put(f"/api/projects/{project['id']}",json=project).json()
    job=client.post(f"/api/projects/{project['id']}/render",json={"version":project["version"],"music":False}).json()
    assert wait_job(client,job["id"])["status"]=="completed"
    post=client.get(f"/api/jobs/{job['id']}/materials/post.txt").text
    assert "AI 演示照片" in post and "虚构演示" in post
    snapshot=client.get(f"/api/jobs/{job['id']}/storyboard.json").json()
    assert snapshot["example_assets"]=="ai"
