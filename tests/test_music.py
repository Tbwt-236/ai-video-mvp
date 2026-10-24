import io
import math
import struct
import subprocess
import wave

import imageio_ffmpeg
import pytest

from app.music import make_music
from test_studio import create, edit_body, studio, wait_job


def rms(raw):
    values=[value[0] for value in struct.iter_unpack("<f",raw)]
    return math.sqrt(sum(value*value for value in values)/len(values))


@pytest.mark.parametrize("style",["ambient","piano","light"])
def test_music_preview_has_exact_length_fades_and_safe_signal(studio,style):
    client,store=studio
    result=client.get(f"/api/music/{style}.wav")
    assert result.status_code==200 and result.headers["content-type"]=="audio/wav"
    with wave.open(io.BytesIO(result.content)) as sound:
        assert sound.getnframes()/sound.getframerate()==8
        samples=[sample[0] for sample in struct.iter_unpack("<h",sound.readframes(sound.getnframes()))]
    assert max(abs(sample) for sample in samples)<12000
    assert math.sqrt(sum(sample*sample for sample in samples)/len(samples))>100
    assert max(abs(sample) for sample in samples[:100])<50
    assert max(abs(sample) for sample in samples[-100:])<50
    assert client.get(f"/api/music/{style}.wav").content==result.content
    assert not list((store.directory/"music-previews").glob("*.part"))
    assert client.get("/api/music/unknown.wav").status_code==404


def test_music_choice_is_saved_and_gain_is_applied_to_actual_audio(studio):
    client,store=studio;p=create(client)
    p=client.put(f"/api/projects/{p['id']}",json=edit_body(p,scenes=[{"heading":"音乐","caption":"试听不同音量。","duration":3}])).json()
    levels=[]
    for volume in (.2,.8):
        settings={"version":p["version"],"music":True,"music_style":"piano","music_volume":volume}
        job=client.post(f"/api/projects/{p['id']}/render",json=settings).json()
        assert wait_job(client,job["id"])["status"]=="completed"
        path=store.directory/"exports"/job["id"]/"video.mp4"
        pcm=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-v","error","-i",str(path),"-vn","-f","f32le","-ac","1","-"],capture_output=True,check=True,timeout=20).stdout
        levels.append(rms(pcm))
        snapshot=client.get(f"/api/jobs/{job['id']}/storyboard.json").json()
        assert snapshot["export_settings"]["music_style"]=="piano"
        assert client.post(f"/api/projects/{p['id']}/render",json=settings).json()["id"]==job["id"]
    assert 3.7<levels[1]/levels[0]<4.3
    assert client.post(f"/api/projects/{p['id']}/render",json={"version":p["version"],"music_style":"invalid"}).status_code==422


def test_styles_produce_different_music(tmp_path):
    outputs=[]
    for style in ("ambient","piano","light"):
        path=tmp_path/f"{style}.wav";make_music(path,2,style=style);outputs.append(path.read_bytes())
    assert len(set(outputs))==3
