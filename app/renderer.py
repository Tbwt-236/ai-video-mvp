"""Deterministic motion-design renderer; no network or generative-video claims."""
import math
import copy
import json
import os
import shutil
import struct
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageOps

from .narration import NarrationError, synthesize
from .process import run_process

ROOT = Path(__file__).resolve().parents[1]
SIZES = {"9:16": (720, 1280), "16:9": (1280, 720), "1:1": (720, 720)}
FPS = 24
PALETTES = {
    "cinema": ((23, 27, 29), (122, 83, 65), (238, 191, 151), (248, 233, 215)),
    "editorial": ((20, 36, 31), (61, 87, 69), (194, 214, 155), (238, 244, 218)),
    "tech": ((16, 22, 43), (37, 58, 121), (142, 167, 255), (230, 236, 255)),
}


@lru_cache(maxsize=32)
def font(size):
    path = os.getenv("VIDEO_FONT") or str(ROOT / "assets/fonts/NotoSansCJKsc-Regular.otf")
    return ImageFont.truetype(path, size)


def wrapped(draw, text, face, width):
    lines, line = [], ""
    for char in text:
        if char == "\n" or (line and draw.textlength(line + char, font=face) > width):
            lines.append(line)
            line = "" if char == "\n" else char
        else:
            line += char
    if line:
        lines.append(line)
    return lines


def text_block(draw, text, x, y, width, height, size, fill):
    size = max(8, size)
    while True:
        face = font(size)
        lines = wrapped(draw, text, face, width)
        if len(lines) * size * 1.48 <= height or size <= 8:
            break
        size -= 1
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill, anchor="lt")
        y += int(size * 1.48)


def scene_image(project, index, size=None, asset_dir=None):
    w, h = size or SIZES[project["aspect"]]
    scene = project["scenes"][index]
    dark, mid, accent, light = PALETTES[project["style"]]
    if project.get("accent_color"):
        value = project["accent_color"].lstrip("#")
        accent = tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    im = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(im)
    # A restrained vertical gradient keeps typography readable in every ratio.
    for y in range(h):
        strength = (math.sin(y / h * math.pi) ** 2) * 0.7
        draw.line((0, y, w, y), fill=tuple(int(d + (m - d) * strength) for d, m in zip(dark, mid)))
    margin = int(min(w, h) * .09)
    cx, cy = int(w * (.64 - .07 * (index % 3))), int(h * .30)
    radius = int(min(w, h) * .24)
    if project["style"] == "cinema":
        # A sun and fine orbital lines, then layered landscapes.
        for r in range(radius, 0, -1):
            t = r / radius
            color = tuple(int(a * (1 - .24 * t)) for a in accent)
            draw.ellipse((cx-r, cy-r, cx+r, cy+r), fill=color)
        for n in range(3):
            offset = n * int(h * .03)
            draw.arc((cx-radius*1.48, cy-radius*1.48+offset, cx+radius*1.48, cy+radius*1.48+offset), 200, 345, fill=accent, width=1)
        for n, color in enumerate([mid, tuple(int(c*.66) for c in mid), dark]):
            horizon = int(h * (.41 + n * .045))
            points = [(0, h), (0, horizon)]
            points += [(x, int(horizon + math.sin(x / w * 5 + n + index) * h * .055)) for x in range(0, w+8, 8)]
            points += [(w, h)]
            draw.polygon(points, fill=color)
    elif project["style"] == "editorial":
        for n in range(5):
            x = int(w*.20 + n*min(w,h)*.13)
            y = int(h*.16 + (n % 3)*h*.035)
            rw, rh = int(min(w,h)*.105), int(h*.29)
            color = tuple(int(c*(.58+n*.085)) for c in accent)
            draw.rounded_rectangle((x, y, x+rw, y+rh), radius=rw//2, fill=color)
        draw.line((margin, int(h*.50), w-margin, int(h*.50)), fill=mid, width=2)
    else:
        for x in range(0, w, max(1, w//14)):
            draw.line((x, int(h*.13), x, int(h*.51)), fill=mid)
        for y in range(int(h*.13), int(h*.51), max(1, h//24)):
            draw.line((0, y, w, y), fill=mid)
        for n in range(9):
            delta = n*max(2, radius//10)
            draw.ellipse((cx-radius+delta//2, cy-radius+delta, cx+radius-delta//2, cy+radius-delta), outline=accent, width=2)
        draw.ellipse((cx-7, cy-7, cx+7, cy+7), fill=light)
    if scene.get("asset_id"):
        if asset_dir is None:
            raise ValueError("缺少门店照片目录")
        with Image.open(asset_dir / f"{scene['asset_id']}.jpg") as photo:
            photo = photo.convert("RGB")
            if scene.get("photo_fit") == "contain":
                contained = ImageOps.contain(photo, (w, h), Image.Resampling.LANCZOS)
                im = Image.new("RGB", (w, h), dark)
                im.paste(contained, ((w-contained.width)//2, (h-contained.height)//2))
            else:
                zoom = scene.get("zoom", 1)
                crop_w = min(photo.width, photo.height*w/h) / zoom
                crop_h = crop_w*h/w
                left = (photo.width-crop_w)*scene.get("crop_x", .5)
                top = (photo.height-crop_h)*scene.get("crop_y", .5)
                im = photo.resize((w, h), Image.Resampling.LANCZOS, box=(left, top, left+crop_w, top+crop_h))
        overlay = Image.new("RGBA", (w, h))
        shade = ImageDraw.Draw(overlay)
        for y in range(h):
            alpha = int(35 + 195 * max(0, min(1, (y/h - .27) / .51)))
            position = scene.get("text_position", "bottom")
            if position != "bottom":
                center = .49 if position == "center" else .29
                alpha = int(35 + 180*max(0, 1-abs(y/h-center)/.37))
            if y < h*.16:
                alpha = max(alpha, int(115*(1-y/(h*.16))))
            shade.line((0, y, w, y), fill=(*dark, alpha))
        im = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(im)
    scale = min(w, h) / 720
    brand = (project.get("merchant") or {}).get("store_name", "F R A M E   /   STUDIO")
    text_block(draw, brand, margin, margin, w-2*margin-100*scale, h*.07, max(12, int(16*scale)), light)
    draw.text((w-margin, margin), f"{index+1:02d} / {len(project['scenes']):02d}", font=font(max(12, int(16*scale))), fill=accent, anchor="rt")
    heading_fraction = {"bottom": .565, "center": .34, "top": .16}[scene.get("text_position", "bottom")]
    heading_y = int(h*heading_fraction)
    text_block(draw, scene["heading"], margin, heading_y, w-2*margin, h*.175, int(56*scale), light)
    caption_color = accent if sum(accent) > 250 else light
    text_block(draw, scene["caption"], margin, int(h*(heading_fraction+.205)), w-2*margin, h*.135, int(25*scale), caption_color)
    draw.line((margin, h-margin, w-margin, h-margin), fill=mid, width=2)
    draw.line((margin, h-margin, margin+int((w-2*margin)*(index+1)/len(project["scenes"])), h-margin), fill=accent, width=3)
    return im


def make_music(path, duration):
    """Original quiet sine-pad soundtrack, generated locally (no voice-over)."""
    rate = 22050
    chord = [130.81, 164.81, 196.00, 261.63]
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        for second in range(math.ceil(duration)):
            buffer = bytearray()
            for i in range(min(rate, round(duration*rate)-second*rate)):
                t = second + i / rate
                fade = min(1, t / 1.5, (duration-t) / 2)
                sample = sum(math.sin(2*math.pi*f*t) * (.7 + .3*math.sin(t*.4+j)) for j, f in enumerate(chord)) / len(chord)
                buffer.extend(struct.pack("<h", int(sample * 3400 * max(0, fade))))
            out.writeframes(buffer)


def run_ffmpeg(args, timeout=120, cancel=None):
    result = run_process([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
                         timeout=timeout, cancel=cancel)
    if result.returncode:
        raise RuntimeError("FFmpeg 合成失败: " + result.stderr.decode(errors="replace")[-1200:])


def srt(project, narrated=False):
    def stamp(seconds):
        milliseconds = round(seconds * 1000)
        seconds, ms = divmod(milliseconds, 1000)
        return f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d},{ms:03d}"
    chunks, start = [], 0
    for i, scene in enumerate(project["scenes"]):
        end = start + scene["duration"]
        cue_start = start + (.3 if narrated else 0)
        cue_end = start + .3 + scene["speech_duration"] if narrated else end
        text = scene['caption'] if narrated else f"{scene['heading']}\n{scene['caption']}"
        chunks.append(f"{i+1}\n{stamp(cue_start)} --> {stamp(cue_end)}\n{text}\n")
        start = end
    return "\n".join(chunks)


def render(project, directory, music, progress, asset_dir=None, narration=False, quality="720p", speech_rate=210, music_volume=.5, cancel=None):
    project = copy.deepcopy(project)
    directory.mkdir(parents=True, exist_ok=True)
    scratch = directory / "tmp"
    scratch.mkdir(exist_ok=True)
    w, h = SIZES[project["aspect"]]
    if quality == "1080p":
        w, h = w*3//2, h*3//2
    def convert(args, timeout=120):
        return run_ffmpeg(args, timeout=timeout, cancel=cancel)
    try:
        if narration:
            for i, scene in enumerate(project["scenes"]):
                progress(4 + i, f"正在朗读字幕 {i+1} / {len(project['scenes'])}")
                spoken = synthesize(scene["caption"], scratch/f"voice-{i}.wav", convert, rate=speech_rate, cancel=cancel)
                scene["speech_duration"] = spoken
                scene["duration"] = max(scene["duration"], math.ceil((spoken+.6)*FPS)/FPS)
            if sum(s["duration"] for s in project["scenes"]) > 120:
                raise NarrationError("配音后超过 120 秒，请精简字幕后重试。")
        for i, scene in enumerate(project["scenes"]):
            if cancel:
                cancel()
            scene_image(project, i, size=(w,h), asset_dir=asset_dir).save(scratch / f"scene-{i}.png")
            if i == min(project.get("cover_scene", 0), len(project["scenes"])-1):
                shutil.copyfile(scratch / f"scene-{i}.png", directory / "cover.png")
            frames = round(scene["duration"] * FPS)
            mode = scene.get("motion", "zoom_in")
            zoom = {"zoom_in": "min(1+on*0.00022,1.04)", "zoom_out": "max(1.04-on*0.00022,1)",
                    "still": "1", "pan_left": "1.04", "pan_right": "1.04"}[mode]
            horizontal = "iw/2-iw/zoom/2"
            if mode == "pan_left":
                horizontal = f"(iw-iw/zoom)*(1-on/{max(1,frames-1)})"
            elif mode == "pan_right":
                horizontal = f"(iw-iw/zoom)*on/{max(1,frames-1)}"
            filters = (f"scale={w*2}:{h*2},zoompan=z='{zoom}':"
                       f"x='{horizontal}':y='ih/2-ih/zoom/2':d={frames}:s={w}x{h}:fps={FPS},"
                       f"fade=t=in:d=0.25,fade=t=out:st={scene['duration']-.25}:d=0.25,format=yuv420p")
            convert(["-i", str(scratch/f"scene-{i}.png"), "-vf", filters,
                        "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", "-threads", "2", str(scratch/f"clip-{i}.mp4")])
            progress(int(8 + (i+1)/len(project["scenes"])*77), f"已合成分镜 {i+1} / {len(project['scenes'])}")
        (scratch/"clips.txt").write_text("\n".join(f"file 'clip-{i}.mp4'" for i in range(len(project["scenes"]))), encoding="utf-8")
        duration = sum(s["duration"] for s in project["scenes"])
        args = ["-f", "concat", "-safe", "0", "-i", str(scratch/"clips.txt")]
        if narration:
            progress(87, "正在对齐中文配音与字幕")
            for i, scene in enumerate(project["scenes"]):
                convert(["-i", str(scratch/f"voice-{i}.wav"), "-af", "adelay=300:all=1,apad",
                            "-t", str(scene["duration"]), str(scratch/f"padded-{i}.wav")])
            (scratch/"voices.txt").write_text("\n".join(f"file 'padded-{i}.wav'" for i in range(len(project["scenes"]))), encoding="utf-8")
            convert(["-f", "concat", "-safe", "0", "-i", str(scratch/"voices.txt"), "-c:a", "pcm_s16le", str(scratch/"voice.wav")])
            args += ["-i", str(scratch/"voice.wav")]
        if music:
            progress(88, "正在合成氛围音轨")
            make_music(scratch/"music.wav", duration)
            args += ["-i", str(scratch/"music.wav")]
        if narration and music:
            args += ["-filter_complex", f"[2:a]volume={music_volume*.25}[bed];[1:a][bed]amix=inputs=2:duration=first:normalize=0[audio]",
                     "-map", "0:v:0", "-map", "[audio]"]
        elif narration or music:
            args += ["-map", "0:v:0", "-map", "1:a:0"]
            if music:
                args += ["-af", f"volume={music_volume}"]
        if narration or music:
            args += ["-c:a", "aac", "-b:a", "128k"]
        args += ["-c:v", "copy", "-t", str(duration), "-movflags", "+faststart", str(directory/"video.part.mp4")]
        convert(args)
        (directory/"video.part.mp4").replace(directory/"video.mp4")
        (directory/"subtitles.srt").write_text(srt(project, narrated=narration), encoding="utf-8")
        project["duration"] = duration
        project["narration"] = narration
        project["export_settings"] = {"quality":quality,"speech_rate":speech_rate,"music_volume":music_volume,"music":music,"narration":narration}
        (directory/"storyboard.json").write_text(json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
        copy_text = project["title"] + "\n\n" + "\n".join(s["caption"] for s in project["scenes"])
        if project.get("example"):
            copy_text = "【虚构演示，请替换门店信息后再发布】\n" + copy_text
        (directory/"post.txt").write_text(copy_text, encoding="utf-8")
        return {"duration": round(duration, 3), "width":w, "height":h}
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
