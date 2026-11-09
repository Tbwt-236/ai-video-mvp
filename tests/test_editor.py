import io
import zipfile

import pytest
from PIL import Image

from app.main import create_app
from fastapi.testclient import TestClient
from test_studio import create, edit_body, studio, wait_job
from test_merchant import upload


def test_project_copy_archive_restore_preserves_materials(studio):
    client, store = studio
    p = create(client)
    asset = upload(client, p).json()["asset_id"]
    p["scenes"][0]["asset_id"] = asset
    p = client.put(f"/api/projects/{p['id']}", json=edit_body(p, cover_scene=1, accent_color="#aaccee")).json()
    assert client.post(f"/api/projects/{p['id']}/duplicate", json={"version":1}).status_code == 409
    copy = client.post(f"/api/projects/{p['id']}/duplicate", json={"version":p["version"]}).json()
    assert copy["id"] != p["id"] and copy["version"] == 1 and copy["cover_scene"] == 1
    assert client.get(f"/api/projects/{copy['id']}/assets/{asset}.jpg").status_code == 200
    assert client.get(f"/api/projects/{copy['id']}/assets").json()[0]["asset_id"] == asset
    copy["scenes"][0]["caption"] = "副本独立修改"
    client.put(f"/api/projects/{copy['id']}",json=edit_body(copy))
    assert client.get(f"/api/projects/{p['id']}").json()["scenes"][0]["caption"] != "副本独立修改"
    archived = client.post(f"/api/projects/{p['id']}/archive",json={"version":p["version"],"archived":True}).json()
    assert p["id"] not in [item["id"] for item in client.get("/api/projects").json()]
    assert p["id"] in [item["id"] for item in client.get("/api/projects?include_archived=true").json()]
    assert client.post(f"/api/projects/{p['id']}/archive",json={"version":p["version"],"archived":False}).status_code == 409
    restored = client.post(f"/api/projects/{p['id']}/archive",json={"version":archived["version"],"archived":False}).json()
    assert not restored["archived"]
    assert (store.directory/"assets"/p["id"]/f"{asset}.jpg").is_file()


def test_archiving_all_projects_does_not_seed_another_demo(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        for p in client.get("/api/projects").json():
            assert client.post(f"/api/projects/{p['id']}/archive",json={"version":p["version"],"archived":True}).status_code==200
        count=len(client.get("/api/projects?include_archived=true").json())
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get("/api/projects").json()==[]
        assert len(restarted.get("/api/projects?include_archived=true").json())==count


def test_crop_preview_is_ephemeral_and_respects_asset_scope(studio):
    client,_=studio
    p=create(client)
    image=Image.new("RGB",(1000,500),(0,0,240))
    image.paste((240,0,0),(0,0,500,500))
    buffer=io.BytesIO();image.save(buffer,"PNG")
    asset=upload(client,p,buffer.getvalue()).json()["asset_id"]
    p["scenes"][0].update(asset_id=asset,crop_x=0,zoom=2)
    payload=edit_body(p)|{"index":0}
    left=client.post(f"/api/projects/{p['id']}/preview",json=payload)
    assert left.status_code==200 and left.headers["content-type"]=="image/png"
    p["scenes"][0]["crop_x"]=1
    right=client.post(f"/api/projects/{p['id']}/preview",json=edit_body(p)|{"index":0})
    for response,dominant in [(left,0),(right,2)]:
        with Image.open(io.BytesIO(response.content)) as frame:
            pixel=frame.getpixel((360,450))
            assert pixel[dominant]>pixel[2-dominant]*3
    assert client.get(f"/api/projects/{p['id']}").json()["version"]==1
    assert client.get(f"/api/projects/{p['id']}").json()["scenes"][0]["asset_id"] is None
    other=create(client)
    assert client.post(f"/api/projects/{other['id']}/preview",json=payload).status_code==400
    assert client.get(f"/api/projects/{other['id']}/assets/{asset}.jpg").status_code==404


@pytest.mark.parametrize("scene_extra",[{"crop_x":2},{"crop_y":-1},{"zoom":3},{"motion":"exec"},{"photo_fit":"invalid"},{"text_position":"invalid"}])
def test_composition_rejects_invalid_values(studio,scene_extra):
    client,_=studio;p=create(client)
    p["scenes"][0].update(scene_extra)
    assert client.put(f"/api/projects/{p['id']}",json=edit_body(p)).status_code==422


def test_selected_cover_bundle_and_single_scene(studio):
    client,store=studio;p=create(client)
    p["scenes"]=[{"heading":"单幕宣传","caption":"一个镜头也能完整导出。","duration":2,"motion":"still","text_position":"center"}]
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,accent_color="#ffeecc")).json()
    job=client.post(f"/api/projects/{p['id']}/render",json={"version":p["version"],"music":False}).json()
    job=wait_job(client,job["id"])
    assert job["status"]=="completed"
    bundle=client.get(f"/api/jobs/{job['id']}/materials.zip")
    assert bundle.status_code==200
    with zipfile.ZipFile(io.BytesIO(bundle.content)) as archive:
        assert set(archive.namelist())=={"video.mp4","subtitles.srt","cover.png","post.txt","storyboard.json"}
        assert "一个镜头也能完整导出。" in archive.read("post.txt").decode()
    assert client.get(f"/api/jobs/{job['id']}/storyboard.json").json()["title"]==p["title"]
    before=client.get(f"/api/jobs/{job['id']}/storyboard.json").content
    client.put(f"/api/projects/{p['id']}",json=edit_body(p,title="另一个标题"))
    assert client.get(f"/api/jobs/{job['id']}/storyboard.json").content==before
    (store.directory/"exports"/job["id"]/"post.txt").unlink()
    assert client.get(f"/api/jobs/{job['id']}/materials.zip").status_code==404


def test_cover_uses_selected_scene(studio):
    from app.renderer import scene_image
    client,store=studio;p=create(client)
    p["scenes"]=[{"heading":"第一幕","caption":"开场内容","duration":2,"motion":"pan_left"},
                 {"heading":"第二幕","caption":"选择这一幕作封面","duration":2,"motion":"pan_right"}]
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,cover_scene=1)).json()
    job=client.post(f"/api/projects/{p['id']}/render",json={"version":p["version"],"music":False}).json()
    job=wait_job(client,job["id"])
    assert job["status"]=="completed"
    with Image.open(store.directory/"exports"/job["id"]/"cover.png") as cover:
        assert cover.tobytes()==scene_image(p,1).tobytes()
