import hashlib
import json
import zipfile

import pytest

from scripts.build_release import ROOT_FILES, TREES, build_release


def source_tree(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    for filename in ROOT_FILES:
        (root / filename).write_text("public source", encoding="utf-8")
    for directory in TREES:
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "app/main.py").write_text("print('hello')", encoding="utf-8")
    (root / "demo/project.zip").write_bytes(b"editable public demo")
    return root


def test_release_excludes_private_data_and_is_reproducible(tmp_path):
    root = source_tree(tmp_path)
    for name in (".env", "data/studio.sqlite3", "data/assets/private.jpg", ".venv/lib/secret.py", "app/__pycache__/code.pyc", "demo/.env", "work/token.txt"):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("DO NOT DISTRIBUTE", encoding="utf-8")
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    result = build_release(root, first)
    build_release(root, second)
    assert first.read_bytes() == second.read_bytes()
    assert result["sha256"] == hashlib.sha256(first.read_bytes()).hexdigest()
    assert first.with_suffix(".zip.sha256").read_text(encoding="utf-8").startswith(result["sha256"])
    with zipfile.ZipFile(first) as package:
        assert package.testzip() is None
        prefix = "AI-Video-MVP-v0.3/"
        manifest = json.loads(package.read(prefix + "RELEASE-MANIFEST.json"))
        assert "demo/project.zip" in manifest["files"]
        for name, metadata in manifest["files"].items():
            data = package.read(prefix + name)
            assert b"DO NOT DISTRIBUTE" not in data
            assert hashlib.sha256(data).hexdigest() == metadata["sha256"]
        assert package.getinfo(prefix + "start.command").external_attr >> 16 & 0o111


def test_release_refuses_incomplete_source_and_unsafe_target(tmp_path):
    root = source_tree(tmp_path)
    with pytest.raises(ValueError, match="outside"):
        build_release(root, root / "release.zip")
    with pytest.raises(ValueError, match="Version"):
        build_release(root, tmp_path / "release.zip", "../oops")
    (root / "run.py").unlink()
    with pytest.raises(ValueError, match="Missing"):
        build_release(root, tmp_path / "release.zip")
