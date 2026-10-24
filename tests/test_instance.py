import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.instance import StudioInUse, StudioLock
from app.main import create_app
from app.store import now
import run


def test_second_application_does_not_recover_another_instances_active_jobs(tmp_path):
    first=create_app(tmp_path)
    with TestClient(first) as client:
        first.state.store.save_job({"id":"active-test","project_id":"test","status":"rendering","created_at":now()})
        with pytest.raises(StudioInUse,match="已有工作台"):
            with TestClient(create_app(tmp_path)):
                pass
        assert client.get('/api/jobs/active-test').json()['status']=='rendering'
    # An actual restart can now mark the orphaned test task as interrupted.
    with TestClient(create_app(tmp_path)) as restarted:
        assert restarted.get('/api/jobs/active-test').json()['status']=='failed'


def test_os_lock_is_shared_across_processes_and_released_on_exit(tmp_path):
    code="""
import sys
from app.instance import StudioLock
with StudioLock(sys.argv[1]):
    print('locked',flush=True)
    sys.stdin.readline()
"""
    child=subprocess.Popen([sys.executable,'-c',code,str(tmp_path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert child.stdout.readline().strip()=='locked'
        with pytest.raises(StudioInUse):
            with StudioLock(tmp_path):
                pass
    finally:
        child.communicate('\n',timeout=10)
    assert child.returncode==0
    with StudioLock(tmp_path):
        assert (tmp_path/'.studio.lock').exists()


def test_lock_releases_even_when_startup_or_work_fails(tmp_path):
    with pytest.raises(ValueError):
        with StudioLock(tmp_path):
            raise ValueError('test startup failure')
    with StudioLock(tmp_path):
        pass


def test_busy_port_stops_before_starting_or_creating_project_data(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(run,'load_env',lambda:None)
    monkeypatch.setenv('PORT','8000')
    data=tmp_path/'untouched';monkeypatch.setenv('VIDEO_DATA_DIR',str(data))
    monkeypatch.setattr(run,'port_in_use',lambda port:True)
    monkeypatch.setattr(run.uvicorn,'run',lambda *args,**kwargs:pytest.fail('server should not start'))
    assert run.main()==1
    assert not data.exists() and '已被占用' in capsys.readouterr().out


def test_different_port_cannot_open_same_active_data_directory(tmp_path,monkeypatch,capsys):
    monkeypatch.setattr(run,'load_env',lambda:None)
    monkeypatch.setenv('PORT','8001');monkeypatch.setenv('VIDEO_DATA_DIR',str(tmp_path))
    monkeypatch.setattr(run,'port_in_use',lambda port:False)
    monkeypatch.setattr(run.uvicorn,'run',lambda *args,**kwargs:pytest.fail('server should not start'))
    with StudioLock(tmp_path):
        assert run.main()==1
    assert '已有工作台' in capsys.readouterr().out
