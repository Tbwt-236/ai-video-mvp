"""Availability of finished export files, without changing historical records."""
MATERIAL_FILES = ("video.mp4", "subtitles.srt", "cover.png", "post.txt", "storyboard.json")


def missing_files(directory, job):
    if job["status"] != "completed":
        return []
    expected = MATERIAL_FILES if job.get("materials") else MATERIAL_FILES[:2]
    missing = []
    for name in expected:
        path = directory / job["id"] / name
        try:
            if not path.is_file() or path.stat().st_size == 0:
                missing.append(name)
        except OSError:
            missing.append(name)
    return missing
