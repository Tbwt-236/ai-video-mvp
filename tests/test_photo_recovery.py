from PIL import Image

from app.assets import list_photos
from test_studio import create, edit_body, studio
from test_merchant import upload


def test_truncated_photo_is_blocked_before_export_and_does_not_hide_the_project(studio):
    client, store = studio
    project = create(client)
    asset = upload(client, project).json()["asset_id"]
    scene = {**project["scenes"][0], "asset_id":asset}
    project = client.put(f"/api/projects/{project['id']}", json=edit_body(project, scenes=[scene])).json()
    directory = store.directory / "assets" / project["id"]
    path = directory / f"{asset}.jpg"
    data = path.read_bytes()
    path.write_bytes(data[:-100])
    # The header still opens, which used to let preflight approve a broken photo.
    with Image.open(path) as image:
        assert image.width > 0
    assert list_photos(directory) == []
    check = client.post(f"/api/projects/{project['id']}/preflight", json={"version":project["version"]}).json()
    assert not check["ready"] and "照片不可读取" in check["blocking"][0]
    preview = client.get(f"/api/projects/{project['id']}/scenes/0.png")
    assert preview.status_code == 400 and "重新上传" in preview.json()["detail"]
    draft = client.post(f"/api/projects/{project['id']}/preview", json={**edit_body(project), "index":0})
    assert draft.status_code == 400
    assert client.get(f"/api/projects/{project['id']}").json()["title"] == project["title"]
    assert client.get(f"/api/projects/{project['id']}/package.zip").status_code == 400
    # Removing a damaged reference restores both preview and export readiness.
    scene["asset_id"] = None
    project = client.put(f"/api/projects/{project['id']}", json=edit_body(project, scenes=[scene])).json()
    assert client.get(f"/api/projects/{project['id']}/scenes/0.png").status_code == 200
    assert client.post(f"/api/projects/{project['id']}/preflight", json={"version":project["version"]}).json()["ready"]


def test_preflight_distinguishes_reused_photos_from_photo_scenes(studio):
    client, _ = studio
    project = create(client)
    asset = upload(client, project).json()["asset_id"]
    scenes = [{**scene, "asset_id":asset} for scene in project["scenes"]]
    project = client.put(f"/api/projects/{project['id']}", json=edit_body(project, scenes=scenes)).json()
    check = client.post(f"/api/projects/{project['id']}/preflight", json={"version":project["version"]}).json()
    assert check["photos"] == 1 and check["photo_scenes"] == len(scenes)
