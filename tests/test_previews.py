import importlib
import io

from PIL import Image, ImageChops

from app.previews import PreviewCache
from test_studio import create, edit_body, studio
from test_merchant import upload


def test_cache_reuses_images_and_evicts_by_byte_budget_and_access_order():
    cache=PreviewCache(max_bytes=8,max_entries=3)
    built=[]
    def get(key,value=b"1234"):
        return cache.get(key,lambda:(built.append(key),value)[1])
    assert get("a")==b"1234"
    get("b");get("a");get("c");get("b")
    assert built==["a","b","c","b"]
    get("large",b"0123456789");get("large",b"0123456789")
    assert built[-2:]==["large","large"]
    cache.clear();get("b")
    assert built[-1]=="b"


def test_scene_thumbnails_preserve_layout_and_cached_versions_never_replace_edits(studio,monkeypatch):
    client,_=studio
    main=importlib.import_module("app.main")
    original=main.scene_image;painted=[]
    def paint(project,index,*args,**kwargs):
        painted.append(project["version"])
        return original(project,index,*args,**kwargs)
    monkeypatch.setattr(main,"scene_image",paint)
    project=create(client)
    url=f"/api/projects/{project['id']}/scenes/0.png"
    full=client.get(url)
    small=client.get(url+"?max_size=480")
    assert full.status_code==small.status_code==200
    with Image.open(io.BytesIO(full.content)) as image:
        image.thumbnail((480,480),Image.Resampling.LANCZOS)
        with Image.open(io.BytesIO(small.content)) as thumbnail:
            assert max(thumbnail.size)==480
            assert ImageChops.difference(image,thumbnail).getbbox() is None
    assert client.get(url+"?max_size=480").content==small.content
    assert len(painted)==2
    project["scenes"][0]["heading"]="已经修改的标题"
    client.put(f"/api/projects/{project['id']}",json=edit_body(project))
    updated=client.get(url+"?max_size=480")
    assert updated.content!=small.content and painted[-1]==2
    assert client.get(url+"?max_size=1").status_code==422
    assert client.get(url+"?max_size=5000").status_code==422


def test_photo_thumbnails_use_original_for_export_and_invalidate_after_damage(studio):
    client,store=studio
    project=create(client)
    buffer=io.BytesIO();Image.new("RGB",(1600,900),"orange").save(buffer,"PNG")
    asset=upload(client,project,buffer.getvalue()).json()["asset_id"]
    url=f"/api/projects/{project['id']}/assets/{asset}.jpg"
    original=client.get(url).content
    thumbnail=client.get(url+"?max_size=480")
    assert thumbnail.status_code==200
    with Image.open(io.BytesIO(thumbnail.content)) as image:
        assert image.size==(480,270)
    with Image.open(io.BytesIO(original)) as image:
        assert image.size==(1600,900)
    assert len(thumbnail.content)<len(original)
    assert client.get(url).content==original
    project["scenes"][0]["asset_id"]=asset
    project=client.put(f"/api/projects/{project['id']}",json=edit_body(project)).json()
    preview=f"/api/projects/{project['id']}/scenes/0.png?max_size=480"
    assert client.get(preview).status_code==200
    path=store.directory/"assets"/project["id"]/f"{asset}.jpg"
    path.write_bytes(original[:-100])
    assert client.get(url+"?max_size=480").status_code==400
    assert client.get(preview).status_code==400
    path.unlink()
    assert client.get(url+"?max_size=480").status_code==404
    assert client.get(preview).status_code==400
