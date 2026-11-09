import copy
import sqlite3

import pytest

from app.projects import copy_projects
from test_merchant import upload
from test_studio import create, edit_body, studio


def test_variants_use_current_draft_and_keep_original_isolated(studio):
    client,store=studio
    project=create(client)
    asset=upload(client,project).json()["asset_id"]
    project["scenes"][0].update(asset_id=asset,crop_x=.2,zoom=1.4)
    body=edit_body(project,title="一份未保存的内容",accent_color="#ffee99",cover_scene=1,
                   aspects=["9:16","16:9","1:1"])
    saved=client.put(f"/api/projects/{project['id']}",json=edit_body(project,title="其他窗口的新内容")).json()
    response=client.post(f"/api/projects/{project['id']}/variants",json=body)
    assert response.status_code==201,response.text
    variants=response.json()
    assert [v["aspect"] for v in variants]==body["aspects"]
    assert len({v["variant_group"] for v in variants})==1
    for variant in variants:
        assert variant["version"]==1 and variant["variant_of"]==project["id"]
        assert variant["title"].startswith(body["title"]) and variant["cover_scene"]==1
        assert variant["scenes"][0]["crop_x"]==.2 and variant["accent_color"]=="#ffee99"
        assert len(client.get(f"/api/projects/{variant['id']}/assets").json())==1
        assert client.get(f"/api/projects/{variant['id']}/scenes/0.png").status_code==200
    changed=variants[0]
    changed["scenes"][0]["caption"]="只修改竖屏版本。"
    assert client.put(f"/api/projects/{changed['id']}",json=changed).status_code==200
    assert client.get(f"/api/projects/{variants[1]['id']}").json()["scenes"][0]["caption"]!=changed["scenes"][0]["caption"]
    assert client.get(f"/api/projects/{project['id']}").json()==saved


@pytest.mark.parametrize("aspects",[[],["9:16","9:16"],["2:1"],["9:16","1:1","16:9","1:1"]])
def test_invalid_variants_create_no_partial_group(studio,aspects):
    client,store=studio;project=create(client)
    before=store.projects()
    assert client.post(f"/api/projects/{project['id']}/variants",json=edit_body(project,aspects=aspects)).status_code==422
    assert store.projects()==before


def test_copy_failure_cleans_all_new_photo_folders(studio,monkeypatch):
    import app.projects as module
    client,store=studio;project=create(client);upload(client,project)
    before=set(p.name for p in (store.directory/"assets").iterdir())
    database=store.projects()
    def fail(projects):
        raise OSError("simulated storage failure")
    monkeypatch.setattr(store,"insert_projects",fail)
    with pytest.raises(OSError):
        copy_projects(store,project,aspects=["16:9","1:1"])
    assert store.projects()==database
    assert set(p.name for p in (store.directory/"assets").iterdir())==before


def test_group_database_insert_rolls_back_on_existing_id(studio):
    client,store=studio;project=create(client)
    new=copy.deepcopy(project);new["id"]="new-but-should-rollback"
    with pytest.raises(sqlite3.IntegrityError):
        store.insert_projects([new,project])
    assert store.get_project(new["id"]) is None
