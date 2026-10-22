"""Versioned, editable project packages. Imports always create an isolated copy."""
import json
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from .assets import MAX_ASSETS, MAX_UPLOAD, list_photos, save_photo
from .models import ProjectEdit
from .store import now

MAX_PACKAGE = 350 * 1024**2
MAX_UNPACKED = MAX_ASSETS * MAX_UPLOAD + 1024**2
FORMAT = "frame-project"


def export_package(store, project, path):
    directory = store.directory / "assets" / project["id"]
    photos = list_photos(directory)
    ids = {item["asset_id"] for item in photos}
    if any(scene.get("asset_id") and scene["asset_id"] not in ids for scene in project["scenes"]):
        raise ValueError("分镜引用的照片已丢失，请重新上传或移除后再备份。")
    if len(photos) != len(list(directory.glob("*.jpg"))):
        raise ValueError("照片库中有不可读取的文件，请检查照片后再备份。")
    manifest = {"format":FORMAT,"format_version":1,"exported_at":now(),"project":project,
                "assets":[{"asset_id":p["asset_id"],"name":p["name"]} for p in photos]}
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json",json.dumps(manifest,ensure_ascii=False,indent=2))
        archive.writestr("README.txt","FRAME 拾帧可编辑作品包\n在作品库选择「导入作品包」继续编辑。\n含分镜与本作品照片，不含历史导出视频或 API 密钥。\n")
        for photo in photos:
            asset=photo["asset_id"]
            archive.write(directory/f"{asset}.jpg",f"assets/{asset}.jpg")
    if path.stat().st_size > MAX_PACKAGE:
        raise ValueError("作品包超过 350 MB，请减少照片后再导出。")


def import_package(store, path):
    try:
        with zipfile.ZipFile(path) as archive:
            entries=archive.infolist()
            names=[item.filename for item in entries]
            if len(entries)>MAX_ASSETS+2 or len(names)!=len(set(names)) or "manifest.json" not in names:
                raise ValueError("作品包文件结构不完整或包含重复文件。")
            if sum(item.file_size for item in entries)>MAX_UNPACKED:
                raise ValueError("作品包解压后的内容过大。")
            for item in entries:
                if item.flag_bits & 1 or stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError("作品包不能包含加密文件或链接。")
                if item.filename in {"manifest.json","README.txt"}:
                    if item.file_size>512*1024:
                        raise ValueError("作品包说明文件过大。")
                elif not re.fullmatch(r"assets/[a-f0-9]{32}\.jpg",item.filename) or item.file_size>MAX_UPLOAD:
                    raise ValueError("请选择由拾帧导出的作品包，照片路径或大小不符合要求。")
            manifest=json.loads(archive.read("manifest.json"))
            if not isinstance(manifest,dict) or manifest.get("format")!=FORMAT or manifest.get("format_version")!=1:
                raise ValueError("不支持这个作品包版本，请使用拾帧格式 v1。")
            raw=manifest.get("project")
            if not isinstance(raw,dict):
                raise ValueError("作品包缺少分镜信息。")
            # Unknown metadata is discarded; imported identifiers never become paths.
            edit=ProjectEdit.model_validate({**raw,"version":1})
            assets=manifest.get("assets",[])
            if not isinstance(assets,list) or len(assets)>MAX_ASSETS:
                raise ValueError("作品包照片清单无效。")
            assets_by_id={}
            for item in assets:
                if not isinstance(item,dict) or not isinstance(item.get("asset_id"),str) or not re.fullmatch(r"[a-f0-9]{32}",item["asset_id"]):
                    raise ValueError("作品包照片标识无效。")
                if item["asset_id"] in assets_by_id or not isinstance(item.get("name","门店照片"),str):
                    raise ValueError("作品包照片清单重复或无效。")
                assets_by_id[item["asset_id"]]=item
            expected={f"assets/{asset}.jpg" for asset in assets_by_id}
            if expected!={name for name in names if name.startswith("assets/")}:
                raise ValueError("照片清单与文件内容不一致。")
            if any(scene.asset_id and scene.asset_id not in assets_by_id for scene in edit.scenes):
                raise ValueError("作品包缺少分镜使用的照片。")
            with tempfile.TemporaryDirectory(prefix="project-import-",dir=store.directory) as temporary:
                staging=Path(temporary)/"assets";staging.mkdir()
                remap={}
                for asset,item in assets_by_id.items():
                    photo=save_photo(archive.read(f"assets/{asset}.jpg"),staging,item.get("name","门店照片"))
                    remap[asset]=photo["asset_id"]
                project=edit.model_dump()
                for scene in project["scenes"]:
                    if scene["asset_id"]:
                        scene["asset_id"]=remap[scene["asset_id"]]
                source=raw.get("source")
                project.update(id=str(uuid4()),source=source if source in {"template","deepseek","merchant_template"} else "template",
                               mode="template",prompt=str(raw.get("prompt", "导入的作品"))[:800],
                               example=raw.get("example") is True,imported=True,archived=False,
                               created_at=now(),updated_at=now(),duration=sum(s["duration"] for s in project["scenes"]))
                destination=store.directory/"assets"/project["id"]
                destination.parent.mkdir(exist_ok=True)
                staging.rename(destination)
                try:
                    store.save_project(project)
                except Exception:
                    shutil.rmtree(destination,ignore_errors=True)
                    raise
                return project
    except ValidationError as exc:
        raise ValueError("作品包分镜内容无效，请检查字数、时长和画面设置。") from exc
    except (zipfile.BadZipFile, UnicodeError, json.JSONDecodeError, KeyError, NotImplementedError) as exc:
        raise ValueError("无法读取作品包，请选择完整的 FRAME 作品 ZIP。") from exc
