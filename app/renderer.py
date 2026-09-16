"""Deterministic motion-design renderer; no network or generative-video claims."""
import math
import os
import shutil
import struct
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

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
    while size > 14:
        face = font(size)
        lines = wrapped(draw, text, face, width)
        if len(lines) * size * 1.48 <= height:
            break
        size -= 1
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill, anchor="lt")
        y += int(size * 1.48)


def scene_image(project, index, size=None):
    w, h = size or SIZES[project["aspect"]]
    scene = project["scenes"][index]
    dark, mid, accent, light = PALETTES[project["style"]]
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
    scale = min(w, h) / 720
    draw.text((margin, margin), "F R A M E   /   STUDIO", font=font(max(12, int(16*scale))), fill=light, anchor="lt")
    draw.text((w-margin, margin), f"{index+1:02d} / {len(project['scenes']):02d}", font=font(max(12, int(16*scale))), fill=accent, anchor="rt")
    heading_y = int(h*.565)
    text_block(draw, scene["heading"], margin, heading_y, w-2*margin, h*.175, int(56*scale), light)
    text_block(draw, scene["caption"], margin, int(h*.77), w-2*margin, h*.135, int(25*scale), accent)
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
        for second in range(duration):
            buffer = bytearray()
            for i in range(rate):
                t = second + i / rate
                fade = min(1, t / 1.5, (duration-t) / 2)
                sample = sum(math.sin(2*math.pi*f*t) * (.7 + .3*math.sin(t*.4+j)) for j, f in enumerate(chord)) / len(chord)
                buffer.extend(struct.pack("<h", int(sample * 3400 * max(0, fade))))
            out.writeframes(buffer)


def run_ffmpeg(args, timeout=120):
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError("FFmpeg 合成失败: " + result.stderr.decode(errors="replace")[-1200:])


def srt(project):
    def stamp(seconds):
        return f"{seconds//3600:02d}:{seconds//60%60:02d}:{seconds%60:02d},000"
    chunks, start = [], 0
    for i, scene in enumerate(project["scenes"]):
        end = start + scene["duration"]
        chunks.append(f"{i+1}\n{stamp(start)} --> {stamp(end)}\n{scene['heading']}\n{scene['caption']}\n")
        start = end
    return "\n".join(chunks)


def render(project, directory, music, progress):
    directory.mkdir(parents=True, exist_ok=True)
    scratch = directory / "tmp"
    scratch.mkdir(exist_ok=True)
    w, h = SIZES[project["aspect"]]
    try:
        for i, scene in enumerate(project["scenes"]):
            scene_image(project, i).save(scratch / f"scene-{i}.png")
            frames = scene["duration"] * FPS
            filters = (f"scale={w*2}:{h*2},zoompan=z='min(1+on*0.00022,1.04)':"
                       f"x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d={frames}:s={w}x{h}:fps={FPS},"
                       f"fade=t=in:d=0.25,fade=t=out:st={scene['duration']-.25}:d=0.25,format=yuv420p")
            run_ffmpeg(["-i", str(scratch/f"scene-{i}.png"), "-vf", filters,
                        "-frames:v", str(frames), "-an", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", "21", "-threads", "2", str(scratch/f"clip-{i}.mp4")])
            progress(int(8 + (i+1)/len(project["scenes"])*77), f"已合成分镜 {i+1} / {len(project['scenes'])}")
        (scratch/"clips.txt").write_text("\n".join(f"file 'clip-{i}.mp4'" for i in range(len(project["scenes"]))), encoding="utf-8")
        duration = sum(s["duration"] for s in project["scenes"])
        args = ["-f", "concat", "-safe", "0", "-i", str(scratch/"clips.txt")]
        if music:
            progress(88, "正在合成氛围音轨")
            make_music(scratch/"music.wav", duration)
            args += ["-i", str(scratch/"music.wav"), "-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "128k"]
        args += ["-c:v", "copy", "-t", str(duration), "-movflags", "+faststart", str(directory/"video.part.mp4")]
        run_ffmpeg(args)
        (directory/"video.part.mp4").replace(directory/"video.mp4")
        (directory/"subtitles.srt").write_text(srt(project), encoding="utf-8")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
