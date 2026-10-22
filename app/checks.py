"""Practical export checks; warnings explain limitations without blocking valid work."""
import shutil
from PIL import Image
from .renderer import SIZES


def export_check(project, data_dir, settings, voice_available):
    blocking, warnings = [], []
    width,height = SIZES[project["aspect"]]
    if settings.quality == "1080p":
        width,height = width*3//2,height*3//2
    photos = 0
    for index, scene in enumerate(project["scenes"]):
        if scene.get("asset_id"):
            photos += 1
            path = data_dir / "assets" / project["id"] / f"{scene['asset_id']}.jpg"
            try:
                with Image.open(path) as image:
                    if image.width < width/2 or image.height < height/2:
                        warnings.append(f"第 {index+1} 幕照片分辨率偏小，放大后可能模糊。")
            except (OSError, ValueError):
                blocking.append(f"第 {index+1} 幕照片不可读取，请重新上传或移除该照片。")
        spoken=scene.get("voiceover") or scene["caption"]
        if len(spoken if settings.narration else scene["caption"]) > scene["duration"]*5:
            warnings.append(f"第 {index+1} 幕" + ("口播较长，将按实际配音长度自动延长镜头。" if settings.narration else "字幕较长，建议延长镜头或开启配音自动对齐。"))
    if project.get("merchant") and photos == 0:
        warnings.append("当前全部为图形背景；加入产品或门店照片，会更便于顾客认识你的小店。")
    if project.get("example"):
        warnings.append("这是一份虚构示例，下载文案会保留演示标识。")
    if not settings.music and not settings.narration:
        warnings.append("当前为无声视频。")
    if settings.narration and not voice_available:
        blocking.append("本机中文配音不可用，请关闭配音后导出。")
    free = shutil.disk_usage(data_dir).free
    needed = (512 if settings.quality=="1080p" else 256)*1024**2
    if free < needed:
        blocking.append(f"磁盘剩余空间不足，请至少预留 {needed//1024**2} MB 后再导出。")
    return {"ready": not blocking, "blocking":blocking, "warnings":warnings,
            "scenes":len(project["scenes"]),"photos":photos,"duration":sum(s["duration"] for s in project["scenes"]),
            "width":width,"height":height,"free_mb":free//1024**2}
