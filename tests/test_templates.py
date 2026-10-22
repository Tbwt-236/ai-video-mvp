import pytest
from app.merchant import catalog, merchant_storyboard
from app.models import MerchantBrief
from test_studio import studio, edit_body


@pytest.mark.parametrize("scenario", ["visit", "product", "offer", "story"])
@pytest.mark.parametrize("duration", [15, 60])
def test_all_industries_keep_supplied_facts_without_adding_claims(scenario, duration):
    for category in catalog()["industries"]:
        facts = category["example"] | {"industry":category["id"],"scenario":scenario,"duration":duration,
                                     "offer":"10 月 24 日指定产品赠包装（演示）"}
        board = merchant_storyboard(MerchantBrief(**facts))
        text = " ".join(s["heading"]+s["caption"] for s in board["scenes"])
        assert all(facts[key] in text for key in ["product","selling_point","offer","address","cta"])
        assert sum(s["duration"] for s in board["scenes"]) == duration
        assert "全城最低" not in text and "销量第一" not in text
        assert board["merchant"]["industry"] == category["id"]
        if scenario=="offer":
            assert facts["offer"] in board["scenes"][0]["caption"]
        if category["id"] not in ["coffee","food","bakery"]:
            assert "好滋味" not in text and "咖啡" not in text


def test_activity_requires_details_and_legacy_save_retains_merchant(studio):
    client,_=studio
    facts=catalog()["industries"][4]["example"] | {"industry":"pet","scenario":"offer"}
    assert client.post("/api/merchant-projects",json=facts).status_code==422
    p=client.post("/api/merchant-projects",json=facts | {"scenario":"visit"}).json()
    assert p["merchant"]["industry"]=="pet"
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p)).json()
    assert p["merchant"]["store_name"]==facts["store_name"]
    captions=[s["caption"] for s in p["scenes"]]
    changed=p["merchant"] | {"store_name":"毛球小站新店名"}
    updated=client.put(f"/api/projects/{p['id']}",json=edit_body(p,merchant=changed)).json()
    assert updated["merchant"]["store_name"]==changed["store_name"]
    assert [s["caption"] for s in updated["scenes"]]==captions
    assert client.get(f"/api/projects/{p['id']}/scenes/0.png").status_code==200


def test_template_boundaries_and_catalog(studio):
    client,_=studio
    data=client.get("/api/config").json()["merchant_catalog"]
    assert len(data["industries"])==6 and len(data["scenarios"])==4
    for industry in data["industries"]:
        assert len(industry["photos"])==3
        assert "虚构" in industry["example"]["address"] and "演示" in industry["example"]["store_name"]
    facts={"store_name":"店"*24,"product":"品"*32,"selling_point":"好"*48,"offer":"惠"*40,"address":"路"*48,"cta":"来"*32}
    for scenario in ["visit","product","offer","story"]:
        response=client.post("/api/merchant-projects",json=facts | {"scenario":scenario})
        assert response.status_code==201,response.text
        p=response.json()
        assert len(p["title"])<=32 and all(len(s["caption"])<=96 for s in p["scenes"])
