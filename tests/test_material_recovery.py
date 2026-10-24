import pytest

from test_studio import create, edit_body, studio, wait_job


@pytest.mark.parametrize("name,empty", [("post.txt", False), ("video.mp4", True)])
def test_incomplete_exports_rebuild_without_losing_remaining_files(studio, name, empty):
    client, store = studio
    project = create(client)
    project = client.put(f"/api/projects/{project['id']}", json=edit_body(project, scenes=[
        {"heading":"可恢复素材", "caption":"重新生成，无需改动分镜。", "duration":2, "motion":"still"}
    ])).json()
    settings = {"version":project["version"], "music":False}
    first = wait_job(client, client.post(f"/api/projects/{project['id']}/render", json=settings).json()["id"])
    assert first["status"] == "completed" and first["missing_files"] == []
    directory = store.directory / "exports" / first["id"]
    preserved = (directory / "cover.png").read_bytes()
    assert client.get(f"/api/jobs/{first['id']}/materials.zip").status_code == 200
    if empty:
        (directory / name).write_bytes(b"")
    else:
        (directory / name).unlink()
    incomplete = client.get(f"/api/jobs/{first['id']}").json()
    assert incomplete["status"] == "completed" and incomplete["missing_files"] == [name]
    listed = client.get(f"/api/projects/{project['id']}/jobs").json()
    assert listed[0]["missing_files"] == [name]
    listed = client.get("/api/jobs").json()["jobs"]
    assert listed[0]["missing_files"] == [name]
    # A previously built ZIP must not disguise a missing or empty source file.
    assert client.get(f"/api/jobs/{first['id']}/materials.zip").status_code == 404
    path = "video.mp4" if name == "video.mp4" else f"materials/{name}"
    assert client.get(f"/api/jobs/{first['id']}/{path}").status_code == 404
    second = client.post(f"/api/projects/{project['id']}/render", json=settings).json()
    assert second["id"] != first["id"]
    second = wait_job(client, second["id"])
    assert second["status"] == "completed" and second["missing_files"] == []
    assert client.get(f"/api/jobs/{second['id']}/materials.zip").status_code == 200
    assert client.get(f"/api/projects/{project['id']}").json() == project
    assert client.get(f"/api/jobs/{first['id']}/materials/cover.png").content == preserved
    assert client.post(f"/api/projects/{project['id']}/render", json=settings).json()["id"] == second["id"]
