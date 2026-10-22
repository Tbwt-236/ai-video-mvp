import io

import imageio_ffmpeg
from PIL import Image, ImageChops, ImageDraw, ImageStat

from test_studio import create, edit_body, studio, wait_job


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
