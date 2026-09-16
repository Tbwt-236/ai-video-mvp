"""Explicit offline templates and an optional, server-side DeepSeek adapter."""
import json
import os
import re

import httpx

from .models import Brief, Scene


EXAMPLES = [
    {"label": "城市漫游", "prompt": "做一支关于周末城市漫游的短片，给忙碌的年轻人，传递慢下来、发现日常之美的感觉。", "style": "cinema"},
    {"label": "咖啡日常", "prompt": "为一家独立咖啡馆做一支短片，突出手冲咖啡、午后阳光和属于自己的片刻，风格温暖克制。", "style": "editorial"},
    {"label": "灵感工具", "prompt": "介绍一款帮助创作者整理灵感的 AI 工具，从随手记录到清晰表达，结尾邀请观众开始创作。", "style": "tech"},
]


def offline_storyboard(brief: Brief):
    prompt = brief.prompt
    if any(word in prompt for word in ["咖啡", "手冲"]):
        title = "一杯咖啡的慢时光"
        lines = [("让时间，慢一拍", "把忙碌暂时留在门外，给自己一段安静的时间。"),
                 ("从一颗豆子开始", "研磨、注水、等待。让细小的仪式唤醒日常。"),
                 ("这一刻，属于你", "找一个喜欢的位置。下一杯，和灵感一起到来。")]
    elif any(word in prompt for word in ["城市", "周末", "旅行", "漫游"]):
        title = "把日常，过成旷野"
        lines = [("把日常，过成旷野", "暂时放下日程，让好奇心带路。"),
                 ("转个弯，发现光", "走进一条陌生的小街，收藏被忽略的风景。"),
                 ("出发，不必等远方", "这个周末，从熟悉的城市开始一次新的漫游。")]
    elif any(word.lower() in prompt.lower() for word in ["AI", "工具", "创作", "科技"]):
        title = "让灵感，有处可去"
        lines = [("灵感，总是突然", "一句话、一张草稿，一个值得被留下的念头。"),
                 ("把碎片，连成线", "记录你的想法，整理成清晰的创作方向。"),
                 ("下一步，开始创造", "从第一个念头，到第一次表达。现在就开始。")]
    else:
        topic = re.split(r"[，。！？\n,!?]", prompt)[0].strip()[:22]
        title = topic
        lines = [(topic, "一个想法，值得被认真看见。"),
                 ("让细节，说出故事", "把你想传递的价值，写进每一个画面。"),
                 ("从这一刻，开始", "在这里写下你的行动邀请，让故事继续发生。")]
    # Offline mode deliberately uses authored templates, never pretends to infer details.
    count = 3 if brief.duration <= 30 else 5
    if count == 5:
        lines.insert(1, ("留一点空间", "放慢节奏，把注意力交给当下。"))
        lines.insert(3, ("记住，这种感觉", "让一件小事，成为今天值得收藏的瞬间。"))
    base, extra = divmod(brief.duration, count)
    scenes = [Scene(heading=h, caption=c, duration=base + (i < extra)).model_dump()
              for i, (h, c) in enumerate(lines)]
    return {"title": title, "scenes": scenes, "source": "template"}


def generate_storyboard(brief: Brief):
    if brief.mode == "template":
        return offline_storyboard(brief)
    key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not key:
        raise ValueError("尚未配置 DeepSeek 密钥，请使用本地模板或在服务端配置 DEEPSEEK_API_KEY。")
    count = 3 if brief.duration <= 30 else 5
    instruction = (
        "你是中文短视频文案编导。根据用户创意写动态文字短片，不生成实拍画面。"
        f"只返回 JSON 对象，格式为 {{\"title\":\"标题\",\"scenes\":[{{\"heading\":\"标题\",\"caption\":\"字幕\"}}]}}。"
        f"必须恰好 {count} 个分镜。title 1-32 字；heading 1-32 字；caption 1-96 字。"
        "文案简洁、适合屏幕阅读，不编造产品功能、统计数字和承诺。不要输出 markdown。"
    )
    try:
        with httpx.Client(timeout=65) as client:
            response = client.post(
                "https://api.deepseek.com/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={"model": os.getenv("DEEPSEEK_MODEL", "deepseek-flash"),
                      "messages": [{"role": "system", "content": instruction},
                                   {"role": "user", "content": json.dumps(brief.model_dump(), ensure_ascii=False)}],
                      "response_format": {"type": "json_object"}, "max_tokens": 1800},
            )
        if response.status_code in (401, 403):
            raise ValueError("DeepSeek 密钥无效或无权限，请检查服务端配置。")
        if response.status_code == 429:
            raise ValueError("DeepSeek 额度不足或请求过于频繁，请稍后重试。")
        response.raise_for_status()
        result = json.loads(response.json()["choices"][0]["message"]["content"])
        if not isinstance(result.get("title"), str) or not 1 <= len(result["title"].strip()) <= 32:
            raise ValueError("invalid title")
        if len(result["scenes"]) != count:
            raise ValueError("invalid scene count")
        base, extra = divmod(brief.duration, count)
        scenes = [Scene(heading=s["heading"], caption=s["caption"], duration=base + (i < extra)).model_dump()
                  for i, s in enumerate(result["scenes"])]
        return {"title": result["title"].strip(), "scenes": scenes, "source": "deepseek"}
    except httpx.TimeoutException as exc:
        raise ValueError("AI 编写超时，请重试或切换到本地模板。") from exc
    except httpx.HTTPError as exc:
        raise ValueError("AI 服务暂时不可用，请重试或切换到本地模板。") from exc
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError("AI 返回的分镜格式不完整，请重新生成。") from exc
