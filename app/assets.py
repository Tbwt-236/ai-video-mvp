"""Immutable, project-scoped photos; originals and EXIF are never retained."""
import io
import warnings
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD = 8 * 1024 * 1024
MAX_PIXELS = 20_000_000
MAX_ASSETS = 40


def save_photo(content, directory):
    if len(content) > MAX_UPLOAD:
        raise ValueError("照片不能超过 8 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"} or getattr(source, "is_animated", False):
                    raise ValueError("请选择静态 JPG、PNG 或 WebP 照片")
                if source.width * source.height > MAX_PIXELS:
                    raise ValueError("照片不能超过 2000 万像素，请先缩小")
                source.load()
                photo = ImageOps.exif_transpose(source).convert("RGBA")
                photo.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                normalized = Image.new("RGB", photo.size, "#f4f1e9")
                normalized.paste(photo, mask=photo.getchannel("A"))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValueError("无法读取照片，请使用有效的 JPG、PNG 或 WebP 文件") from exc
    directory.mkdir(parents=True, exist_ok=True)
    if len(list(directory.glob("*.jpg"))) >= MAX_ASSETS:
        raise ValueError("当前作品已上传 40 张照片，请新建作品继续")
    asset_id = uuid4().hex
    normalized.save(directory / f"{asset_id}.jpg", "JPEG", quality=90)
    return {"asset_id": asset_id, "width": normalized.width, "height": normalized.height}
