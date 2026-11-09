"""Build a reproducible source/demo ZIP without local projects or credentials."""
import argparse
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = (
    "README.md", ".env.example", ".gitignore", "bootstrap.py", "doctor.py",
    "run.py", "start.sh", "start.command", "start.bat", "requirements.txt",
    "requirements-lock.txt", "requirements-dev.txt", "pytest.ini",
)
TREES = {
    "app": {".py"}, "web": {".html", ".css", ".js", ".svg"},
    "assets/fonts": {".otf", ".ttf", ".txt", ".md"},
    "demo": {".png", ".jpg", ".mp4", ".srt", ".txt", ".json", ".md"},
    "docs": {".md"}, "tests": {".py", ".cjs"}, "scripts": {".py"},
    ".github/workflows": {".yml", ".yaml"},
}


def release_files(root):
    root = Path(root).resolve()
    selected = [root / name for name in ROOT_FILES]
    for name, extensions in TREES.items():
        directory = root / name
        if not directory.is_dir():
            raise ValueError(f"Missing release directory: {name}")
        for path in directory.rglob("*"):
            relative = path.relative_to(directory)
            if any(part.startswith(".") or part == "__pycache__" for part in relative.parts):
                continue
            if path.is_symlink():
                raise ValueError(f"Release files cannot be symlinks: {path.relative_to(root)}")
            if path.is_file() and (path.suffix in extensions or (name == "demo" and path.name == "project.zip")):
                selected.append(path)
    for path in selected:
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError(f"Missing or unsafe release file: {path.relative_to(root)}")
    return sorted(selected, key=lambda path: path.relative_to(root).as_posix())


def archive_entry(name, data, executable=False):
    entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    entry.create_system = 3
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = (0o100755 if executable else 0o100644) << 16
    return entry, data


def build_release(root, destination, version="v0.3"):
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if not re.fullmatch(r"v?\d+\.\d+(?:\.\d+)?", version):
        raise ValueError("Version must look like v0.3 or v0.3.1")
    if destination.is_relative_to(root):
        raise ValueError("Put the release ZIP outside the source directory")
    files = release_files(root)
    prefix = f"AI-Video-MVP-{version}"
    manifest = {"version": version, "format": 1, "files": {}}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="frame-release-", dir=destination.parent) as temporary:
        archive = Path(temporary) / "release.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as package:
            for path in files:
                relative = path.relative_to(root).as_posix()
                data = path.read_bytes()
                manifest["files"][relative] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                entry, data = archive_entry(f"{prefix}/{relative}", data, path.suffix in {".sh", ".command"})
                package.writestr(entry, data)
            entry, data = archive_entry(f"{prefix}/RELEASE-MANIFEST.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
            package.writestr(entry, data)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.replace(destination)
        checksum_file = Path(temporary) / "checksum.txt"
        checksum_file.write_text(f"{checksum}  {destination.name}\n", encoding="utf-8")
        checksum_file.replace(destination.with_suffix(destination.suffix + ".sha256"))
    return {"path": str(destination), "files": len(files), "bytes": destination.stat().st_size, "sha256": checksum}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / "AI-Video-MVP-v0.3.zip")
    parser.add_argument("--version", default="v0.3")
    parser.add_argument("--overwrite", action="store_true", help="Replace an earlier generated release")
    args = parser.parse_args()
    if args.output.exists() and not args.overwrite:
        parser.error("Output already exists; use --overwrite to replace the generated archive")
    try:
        result = build_release(ROOT, args.output, args.version)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Release failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
