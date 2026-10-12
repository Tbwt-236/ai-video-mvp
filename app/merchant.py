"""A facts-only merchant template: no invented offers, claims or shop details."""
from .models import MerchantBrief, Scene


def merchant_storyboard(brief: MerchantBrief):
    lines = [
        (brief.store_name, f"今日主推：{brief.product}。"),
        ("给日常，一点好滋味", brief.selling_point + (f" {brief.offer}" if brief.offer else "")),
        ("下次见，就在这里", f"{brief.address}。{brief.cta}"),
    ]
    if brief.duration > 30:
        lines = [(brief.store_name, f"欢迎来到{brief.store_name}。"),
                 (brief.product, f"今日主推：{brief.product}。"),
                 ("给日常，一点好滋味", brief.selling_point),
                 ("来店里，坐一会儿", brief.offer or brief.cta),
                 ("下次见，就在这里", f"{brief.address}。{brief.cta}")]
    base, extra = divmod(brief.duration, len(lines))
    return {"title": f"{brief.store_name} · 到店邀请", "source": "merchant_template",
            "prompt": f"{brief.store_name}：{brief.product}；{brief.selling_point}；{brief.offer}；{brief.address}",
            "merchant": brief.model_dump(exclude={"style", "aspect", "duration", "example"}),
            "scenes": [Scene(heading=h, caption=c, duration=base+(i < extra)).model_dump()
                       for i, (h, c) in enumerate(lines)]}
