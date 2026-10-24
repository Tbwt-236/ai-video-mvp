import importlib
import struct
import wave

from test_portability import import_zip
from test_studio import create, edit_body, studio, wait_job


def test_independent_voiceover_is_used_for_speech_and_srt_not_screen_text(studio,monkeypatch):
    client,store=studio;main=importlib.import_module("app.main");renderer=importlib.import_module("app.renderer")
    monkeypatch.setattr(main,"narration_available",lambda:True)
    spoken=[]
    def voice(text,path,convert,**options):
        spoken.append(text)
        with wave.open(str(path),"wb") as sound:
            sound.setnchannels(1);sound.setsampwidth(2);sound.setframerate(22050)
            sound.writeframes(struct.pack("<h",800)*22050)
        return 1
    monkeypatch.setattr(renderer,"synthesize",voice)
    p=create(client)
    scene={"heading":"新品上架","caption":"海盐黄油卷","voiceover":"  海盐黄油卷，配一杯咖啡。\n让忙碌的早晨慢下来。  ","duration":2}
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,scenes=[scene])).json()
    assert p["scenes"][0]["voiceover"]=="海盐黄油卷，配一杯咖啡。 让忙碌的早晨慢下来。"
    job=client.post(f"/api/projects/{p['id']}/render",json={"version":p["version"],"narration":True,"music":False}).json()
    assert wait_job(client,job["id"])["status"]=="completed"
    assert spoken==[p["scenes"][0]["voiceover"]]
    srt=client.get(f"/api/jobs/{job['id']}/subtitles.srt").text
    assert p["scenes"][0]["voiceover"] in srt and "新品上架" not in srt
    snapshot=client.get(f"/api/jobs/{job['id']}/storyboard.json").json()
    assert snapshot["scenes"][0]["caption"]=="海盐黄油卷"
    package=client.get(f"/api/projects/{p['id']}/package.zip").content
    restored=import_zip(client,package).json()
    assert restored["scenes"][0]["voiceover"]==p["scenes"][0]["voiceover"]
    # Turning voice off uses the visual captions for subtitles.
    silent=client.post(f"/api/projects/{p['id']}/render",json={"version":p["version"],"music":False}).json()
    assert wait_job(client,silent["id"])["status"]=="completed"
    assert "新品上架" in client.get(f"/api/jobs/{silent['id']}/subtitles.srt").text


def test_empty_and_overlong_voiceover_validation(studio):
    client,store=studio;p=create(client)
    scene={"heading":"标题","caption":"字幕","duration":2,"voiceover":"  "}
    result=client.put(f"/api/projects/{p['id']}",json=edit_body(p,scenes=[scene])).json()
    assert result["scenes"][0]["voiceover"] is None
    scene["voiceover"]="长"*161
    assert client.put(f"/api/projects/{p['id']}",json=edit_body(result,scenes=[scene])).status_code==422
    assert client.post("/api/narration/preview",json={"text":"长"*161}).status_code==422
