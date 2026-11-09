import io
import json

from PIL import Image

from app.assets import list_photos,save_photo


def test_chinese_photo_names_are_utf8_and_bad_labels_do_not_hide_valid_photos(tmp_path):
    buffer=io.BytesIO();Image.new("RGB",(30,40),"orange").save(buffer,"PNG")
    name="花店 · 清晨花束 🌸"
    photo=save_photo(buffer.getvalue(),tmp_path,name)
    assert list_photos(tmp_path)[0]["name"]==name
    metadata=tmp_path/(photo["asset_id"]+".json")
    for invalid in [b"broken",b"\xff",b"[]",b"null",b'{"name":42}']:
        metadata.write_bytes(invalid)
        listed=list_photos(tmp_path)
        assert len(listed)==1 and listed[0]["name"]=="门店照片"
        assert listed[0]["asset_id"]==photo["asset_id"]
