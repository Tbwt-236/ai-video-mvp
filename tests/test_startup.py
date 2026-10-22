import json
import sys

import bootstrap
import doctor


def test_dependency_check_detects_version_mismatch_without_installing(tmp_path,monkeypatch):
    monkeypatch.setattr(bootstrap,"ROOT",tmp_path)
    (tmp_path/"requirements.txt").write_text("fastapi==0.0.0\n")
    result=bootstrap.dependency_probe(sys.executable)
    assert result.returncode==1 and "fastapi" in result.stdout and "0.0.0" in result.stdout
    assert not (tmp_path/".venv").exists()


def test_readonly_startup_check_does_not_create_environment(tmp_path,monkeypatch):
    monkeypatch.setattr(bootstrap,"ROOT",tmp_path)
    assert bootstrap.main(["--check"])==1
    assert list(tmp_path.iterdir())==[]


def test_diagnostics_do_not_create_database_or_expose_api_key(tmp_path,monkeypatch):
    monkeypatch.setenv("VIDEO_DATA_DIR",str(tmp_path/"not-created"))
    monkeypatch.setenv("DEEPSEEK_API_KEY","private-test-secret-never-print")
    result=doctor.diagnose()
    assert "private-test-secret" not in json.dumps(result)
    assert any(check["name"]=="作品数据库" and check["ok"] for check in result["checks"])
    assert not (tmp_path/"not-created").exists()
