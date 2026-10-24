import io
import json
import stat
import zipfile

import pytest

from test_studio import create, edit_body, studio
from test_merchant import upload


def import_zip(client,content):
    return client.post("/api/projects/import",content=content,headers={"Content-Type":"application/zip"})


def alter_package(content,change):
    buffer=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as original,zipfile.ZipFile(buffer,"w") as changed:
        entries={name:original.read(name) for name in original.namelist()}
        change(entries)
        for name,value in entries.items():changed.writestr(name,value)
    return buffer.getvalue()


def test_project_package_roundtrip_isolated_and_complete(studio):
    client,store=studio;p=create(client)
    a=upload(client,p).json()["asset_id"];b=upload(client,p).json()["asset_id"]
    p["scenes"][1].update(asset_id=a,crop_x=.2,zoom=1.5,text_position="top",motion="pan_left")
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,accent_color="#ffaa66",cover_scene=1)).json()
    package=client.get(f"/api/projects/{p['id']}/package.zip")
    assert package.status_code==200 and package.headers["content-type"]=="application/zip"
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert set(archive.namelist())=={"manifest.json","README.txt",f"assets/{a}.jpg",f"assets/{b}.jpg"}
    response=import_zip(client,package.content)
    assert response.status_code==201,response.text
    copy=response.json()
    assert copy["id"]!=p["id"] and copy["version"]==1 and copy["cover_scene"]==1 and copy["accent_color"]=="#ffaa66"
    imported=copy["scenes"][1]
    assert imported["asset_id"]!=a and imported["crop_x"]==.2 and imported["zoom"]==1.5
    assert len(client.get(f"/api/projects/{copy['id']}/assets").json())==2
    assert client.get(f"/api/projects/{copy['id']}/assets/{a}.jpg").status_code==404
    assert client.get(f"/api/projects/{copy['id']}/scenes/1.png").status_code==200
    assert client.get(f"/api/projects/{copy['id']}/jobs").json()==[]
    assert client.get(f"/api/projects/{p['id']}").json()["version"]==p["version"]
    assert not list(store.directory.glob("project-import-*")) and not list(store.directory.glob("package-upload-*"))
    assert not list(store.directory.glob("project-export-*"))


@pytest.mark.parametrize("invalid",["traversal","version","missing","unknown","bad_image","corrupt_json","symlink"])
def test_bad_packages_cannot_create_partial_projects_or_files(studio,invalid):
    client,store=studio;p=create(client)
    asset=upload(client,p).json()["asset_id"];p["scenes"][0]["asset_id"]=asset
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p)).json()
    content=client.get(f"/api/projects/{p['id']}/package.zip").content
    before=set(project["id"] for project in store.projects())
    folders=set(path.name for path in (store.directory/"assets").iterdir())
    def change(entries):
        manifest=json.loads(entries["manifest.json"])
        if invalid=="traversal":entries["../../outside.txt"]=b"escape"
        elif invalid=="version":manifest["format_version"]=99
        elif invalid=="missing":entries.pop(f"assets/{asset}.jpg")
        elif invalid=="unknown":entries["secret.env"]=b"bad"
        elif invalid=="bad_image":entries[f"assets/{asset}.jpg"]=b"not an image"
        elif invalid=="symlink":
            link=zipfile.ZipInfo("assets/"+"b"*32+".jpg");link.create_system=3;link.external_attr=(stat.S_IFLNK | 0o777)<<16
            entries[link]=b"/etc/passwd"
        entries["manifest.json"]=b"not json" if invalid=="corrupt_json" else json.dumps(manifest).encode()
    response=import_zip(client,alter_package(content,change))
    assert response.status_code==400,response.text
    assert set(project["id"] for project in store.projects())==before
    assert set(path.name for path in (store.directory/"assets").iterdir())==folders
    assert not (store.directory.parent/"outside.txt").exists()
    assert not list(store.directory.glob("project-import-*")) and not list(store.directory.glob("package-upload-*"))


def test_package_import_limits_and_original_project_id_ignored(studio,monkeypatch):
    import importlib
    client,store=studio;p=create(client)
    content=client.get(f"/api/projects/{p['id']}/package.zip").content
    def change(entries):
        manifest=json.loads(entries["manifest.json"])
        manifest["project"]["id"]="../../outside"
        entries["manifest.json"]=json.dumps(manifest).encode()
    response=import_zip(client,alter_package(content,change))
    assert response.status_code==201 and "/" not in response.json()["id"]
    assert client.post("/api/projects/import",content=content,headers={"Content-Type":"image/png"}).status_code==415
    assert client.post("/api/projects/import",content=content,headers={"Content-Type":"application/zip","Origin":"https://elsewhere.test"}).status_code==403
    main=importlib.import_module("app.main");monkeypatch.setattr(main,"MAX_PACKAGE",10)
    assert import_zip(client,content).status_code==413
    assert client.post("/api/projects/import",content=(b"x"*8 for _ in range(2)),headers={"Content-Type":"application/zip"}).status_code==413
    assert not list(store.directory.glob("package-upload-*"))
