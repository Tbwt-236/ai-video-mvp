import json

import httpx
import pytest

from test_studio import studio


@pytest.mark.parametrize("reply",[
    {"choices":[]},
    {"choices":[{"message":{"content":None}}]},
    {"choices":[{"message":{"content":"[]"}}]},
    {"choices":[{"message":{"content":"not json"}}]},
    {"choices":[{"message":{"content":json.dumps({"title":"好标题","scenes":[{},{}]})}}]},
    {"choices":[{"message":{"content":json.dumps({"title":"好标题","scenes":[{"heading":"长"*33,"caption":"字幕"}]*3})}}]},
    {"choices":[{"finish_reason":"length","message":{"content":json.dumps({"title":"好标题","scenes":[{"heading":"标题","caption":"字幕"}]*3})}}]},
])
def test_malformed_ai_responses_are_clear_errors_without_partial_projects(studio,monkeypatch,reply):
    import app.storyboard as module
    client,store=studio;before=store.projects()
    monkeypatch.setenv("DEEPSEEK_API_KEY","test-only-key")
    class FakeClient:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            assert kwargs["json"]["thinking"]=={"type":"disabled"}
            return httpx.Response(200,json=reply,request=httpx.Request("POST",url))
    monkeypatch.setattr(module.httpx,"Client",FakeClient)
    result=client.post("/api/projects",json={"prompt":"为小店写一支介绍短片","mode":"ai"})
    assert result.status_code==400
    assert result.json()["detail"]=="AI 返回的分镜格式不完整，请重新生成。"
    assert store.projects()==before
