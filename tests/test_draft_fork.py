from test_studio import studio, create, edit_body
from test_merchant import upload


def test_conflicted_draft_can_be_saved_as_independent_copy(studio):
    client,store=studio;p=create(client)
    asset=upload(client,p).json()["asset_id"]
    draft=edit_body(p,title="窗口一的草稿",accent_color="#ddbb77",cover_scene=1)
    draft["scenes"][0].update(asset_id=asset,caption="还没有保存的文字",crop_x=.15)
    newer=client.put(f"/api/projects/{p['id']}",json=edit_body(p,title="窗口二已经保存")).json()
    assert client.put(f"/api/projects/{p['id']}",json=draft).status_code==409
    response=client.post(f"/api/projects/{p['id']}/fork",json=draft)
    assert response.status_code==201,response.text
    copy=response.json()
    assert copy["id"]!=p["id"] and copy["version"]==1
    assert copy["title"].startswith("窗口一的草稿") and copy["cover_scene"]==1
    assert copy["scenes"][0]["caption"]=="还没有保存的文字"
    assert copy["scenes"][0]["crop_x"]==.15 and copy["accent_color"]=="#ddbb77"
    assert client.get(f"/api/projects/{copy['id']}/assets/{asset}.jpg").status_code==200
    assert client.get(f"/api/projects/{p['id']}").json()==newer


def test_draft_fork_validates_scope_and_duration(studio):
    client,_=studio;p=create(client);q=create(client)
    asset=upload(client,q).json()["asset_id"]
    draft=edit_body(p);draft["scenes"][0]["asset_id"]=asset
    assert client.post(f"/api/projects/{p['id']}/fork",json=draft).status_code==400
    draft["scenes"][0]["asset_id"]=None;draft["scenes"][0]["duration"]=61
    assert client.post(f"/api/projects/{p['id']}/fork",json=draft).status_code==422
