"""Ready-to-edit fictional demos with clearly disclosed AI source photos."""
import shutil
from pathlib import Path
from uuid import uuid4

from .assets import save_photo
from .merchant import catalog, merchant_storyboard
from .models import MerchantBrief
from .store import now

ROOT=Path(__file__).resolve().parents[1]
SHOWCASES={
    "coffee": {"title":"午后咖啡小店","description":"暖色饮品照片 · 到店邀请", "file":"demo/merchant/coffee-ai-demo.png", "color":"#e9ce9c"},
    "flowers": {"title":"一束花的日常","description":"花束细节照片 · 产品主推", "file":"demo/showcase/flowers-ai.png", "color":"#edc4b1"},
    "bakery": {"title":"烘焙店的早晨","description":"面包近景照片 · 产品主推", "file":"demo/showcase/bakery-ai.png", "color":"#edca89"},
}


def available_showcases():
    return [{"id":key,"title":value["title"],"description":value["description"],"image":f"/showcase/{key}.png"}
            for key,value in SHOWCASES.items() if (ROOT/value["file"]).is_file()]


def showcase_photo(key):
    item=SHOWCASES.get(key)
    return ROOT/item["file"] if item and (ROOT/item["file"]).is_file() else None


def build_showcase(key, directory, aspect="9:16"):
    source=showcase_photo(key)
    if source is None:
        raise ValueError("这份演示素材暂时不可用，请选择其他示例。")
    category=next(item for item in catalog()["industries"] if item["id"]==key)
    brief=MerchantBrief(**category["example"],industry=key,scenario="visit" if key=="coffee" else "product",
                        style=category["style"],aspect=aspect,example=True)
    project={**brief.model_dump(include={"style","aspect","duration","example"}),**merchant_storyboard(brief),
             "id":str(uuid4()),"version":1,"mode":"template","created_at":now(),"updated_at":now(),
             "accent_color":SHOWCASES[key]["color"],"cover_scene":0,"example_assets":"ai",
             "demo_note":"虚构门店与 AI 演示照片；同一张照片在三幕中以不同构图复用。"}
    assets=directory/"assets"/project["id"]
    try:
        photo=save_photo(source.read_bytes(),assets,f"AI 演示 · {category['label']}")
    except Exception:
        shutil.rmtree(assets,ignore_errors=True)
        raise
    for i,scene in enumerate(project["scenes"]):
        scene.update(asset_id=photo["asset_id"],zoom=[1,1.2,1.05][i],crop_y=[.4,.3,.5][i],
                     motion=["zoom_in","pan_right","zoom_out"][i])
    return project
