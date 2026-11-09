import io

import imageio_ffmpeg
import pytest
from PIL import Image, ImageChops, ImageDraw, ImageStat

from test_studio import create, edit_body, studio, wait_job
from app.renderer import PALETTES, scene_layers


def test_moving_photo_keeps_caption_stationary_in_encoded_video(studio):
    client,store=studio
    project=create(client)
    photo=Image.new("RGB",(720,1280),(20,40,80));draw=ImageDraw.Draw(photo)
    for x in range(0,720,40):
        draw.rectangle((x,0,x+18,1280),fill=(160,75,45))
    image=io.BytesIO();photo.save(image,"PNG")
    asset=client.post(f"/api/projects/{project['id']}/assets",content=image.getvalue(),headers={"Content-Type":"image/png"}).json()["asset_id"]
    project=client.put(f"/api/projects/{project['id']}",json=edit_body(project,scenes=[
        {"heading":"文字保持稳定","caption":"移动的是照片，字幕更容易阅读。","duration":2,"asset_id":asset,"motion":"pan_right"}
    ])).json()
    job=client.post(f"/api/projects/{project['id']}/render",json={"version":project["version"],"music":False}).json()
    assert wait_job(client,job["id"])["status"]=="completed"
    frames=imageio_ffmpeg.read_frames(str(store.directory/"exports"/job["id"]/"video.mp4"))
    meta=next(frames);samples=[]
    try:
        for index,frame in enumerate(frames):
            if index in (12,36):samples.append(Image.frombytes("RGB",meta["size"],frame))
            if index==36:break
    finally:
        frames.close()
    # Above the text, the colored stripe photo demonstrably moves.
    region=(80,250,640,500)
    assert sum(ImageStat.Stat(ImageChops.difference(samples[0].crop(region),samples[1].crop(region))).mean)>5
    # Bright opaque heading pixels remain in the same screen coordinates.
    masks=[]
    for sample in samples:
        crop=sample.crop((40,700,680,930))
        masks.append({i for i,(r,g,b) in enumerate(crop.getdata()) if r>225 and g>215 and b>190})
    assert len(masks[0])>1000
    assert len(masks[0]&masks[1])/len(masks[0]|masks[1])>.95


@pytest.mark.parametrize("accent,expected", [("#0000ff", PALETTES["editorial"][3]),
                                          ("#800080", PALETTES["editorial"][3]),
                                          ("#ffff00", (255,255,0))])
def test_saturated_dark_brand_colors_do_not_hide_caption_or_counter(accent, expected):
    project = {"aspect":"1:1", "style":"editorial", "accent_color":accent,
               "scenes":[{"heading":"欢迎到店", "caption":"门店地址和活动信息要清楚可读。"}]}
    _, foreground = scene_layers(project, 0)
    caption = foreground.crop((60,550,660,640))
    counter = foreground.crop((570,60,660,95))
    # Include antialiasing at the small counter size, but ignore transparent pixels.
    for region in (caption, counter):
        pixels = [pixel for pixel in region.getdata() if pixel[3] > 0]
        assert len(pixels) > 50 and all(pixel[:3] == expected for pixel in pixels)
    # The brand-colored progress line retains the original color.
    chosen = tuple(int(accent[i:i+2],16) for i in (1,3,5))
    assert sum(pixel == (*chosen,255) for pixel in foreground.crop((60,645,660,680)).getdata()) > 100
