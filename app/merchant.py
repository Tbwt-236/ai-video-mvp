"""Facts-only local templates: category changes the framing, never the shop facts."""
from .models import MerchantBrief, Scene


INDUSTRIES = {
    "coffee": {"label": "咖啡茶饮", "icon": "☕", "heading": "给日常，一点好滋味", "style": "editorial",
               "photos": ["主推饮品近景", "店内座位与环境", "门头与到店路线"],
               "example": {"store_name": "拾光咖啡（演示）", "product": "桂花拿铁", "selling_point": "桂花香气，搭配柔和奶香。临窗坐坐，给午后留一点空闲。", "cta": "欢迎到店，喝一杯喜欢的咖啡。"}},
    "food": {"label": "餐饮小店", "icon": "🍜", "heading": "这一餐，来点喜欢的", "style": "cinema",
             "photos": ["招牌菜出餐特写", "用餐环境", "门头与到店路线"],
             "example": {"store_name": "巷口面馆（演示）", "product": "番茄牛肉面", "selling_point": "汤面与小菜可以搭配选择，店内设有单人座。", "cta": "路过时，来吃一碗热面。"}},
    "bakery": {"label": "烘焙甜品", "icon": "🥐", "heading": "把小小甜意，带回日常", "style": "cinema",
               "photos": ["面包或蛋糕特写", "陈列与制作过程", "包装与门店位置"],
               "example": {"store_name": "麦田烘焙（演示）", "product": "海盐黄油卷", "selling_point": "咸香黄油搭配柔软面包，可在店内选购。", "cta": "来店里，选一份喜欢的面包。"}},
    "beauty": {"label": "美甲美睫", "icon": "✦", "heading": "给自己，一点新的灵感", "style": "editorial",
               "photos": ["实际款式作品", "工作台与店内环境", "预约方式与门头"],
               "example": {"store_name": "指间小屋（演示）", "product": "奶油色系美甲", "selling_point": "可从店内色卡挑选颜色，先沟通款式再开始制作。", "cta": "先来聊聊，你喜欢什么样的款式。"}},
    "pet": {"label": "宠物服务", "icon": "🐾", "heading": "把日常照顾，认真做好", "style": "editorial",
            "photos": ["实际服务场景", "空间与服务用品", "门头与预约方式"],
            "example": {"store_name": "毛球小站（演示）", "product": "宠物洗护预约", "selling_point": "到店前可沟通宠物体型、毛发情况与服务安排。", "cta": "欢迎先咨询，再安排到店时间。"}},
    "flowers": {"label": "花店绿植", "icon": "❀", "heading": "让一束花，走进日常", "style": "editorial",
                "photos": ["花束与花材细节", "包装或搭配过程", "花店门头与位置"],
                "example": {"store_name": "一枝花房（演示）", "product": "暖色系日常花束", "selling_point": "可以沟通喜欢的颜色与预算，再选择花材搭配。", "cta": "来选一束，送给想念的人。"}},
}
SCENARIOS = {
    "visit": {"label": "到店邀请", "description": "介绍产品、特色和地址，让顾客知道为什么来。"},
    "product": {"label": "产品主推", "description": "以一款产品或服务开场，突出你填写的特色。"},
    "offer": {"label": "活动宣传", "description": "把活动放在开头，请填写优惠内容及适用时间。"},
    "story": {"label": "认识小店", "description": "先介绍店名和特色，再邀请顾客认识主推产品。"},
}


def catalog():
    industries = []
    for key, item in INDUSTRIES.items():
        industries.append({"id": key, **item, "example": {**item["example"], "offer": "",
                          "address": "示例城市 · 春日路 18 号（虚构地址）"}})
    return {"industries": industries, "scenarios": [{"id": key, **item} for key, item in SCENARIOS.items()]}


def merchant_storyboard(brief: MerchantBrief):
    industry = INDUSTRIES[brief.industry]
    product_photo, setting_photo, arrival_photo = industry["photos"]
    closing = ("下次见，就在这里", f"{brief.address}。{brief.cta}", arrival_photo)
    product = (brief.product, f"今日主推：{brief.product}。", product_photo)
    benefit = (industry["heading"], brief.selling_point, setting_photo)
    offer = ("这次到店，可以了解", brief.offer or brief.cta, product_photo)
    opening = (brief.store_name, f"欢迎来到{brief.store_name}。", setting_photo)
    if brief.duration > 30:
        lines = {
            "visit": [opening, product, benefit, offer, closing],
            "product": [product, benefit, opening, offer, closing],
            "offer": [("店里的活动，告诉你", brief.offer, product_photo), product, benefit, opening, closing],
            "story": [opening, benefit, product, offer, closing],
        }[brief.scenario]
    else:
        benefit_with_offer = (benefit[0], brief.selling_point + (f" {brief.offer}" if brief.offer else ""), setting_photo)
        lines = {
            "visit": [(brief.store_name, product[1], product_photo), benefit_with_offer, closing],
            "product": [product, benefit_with_offer, closing],
            "offer": [(brief.product, brief.offer, product_photo), benefit, closing],
            "story": [(brief.store_name, brief.selling_point, setting_photo), (brief.product, product[1] + (f" {brief.offer}" if brief.offer else ""), product_photo), closing],
        }[brief.scenario]
    base, extra = divmod(brief.duration, len(lines))
    return {"title": f"{brief.store_name} · {SCENARIOS[brief.scenario]['label']}", "source": "merchant_template",
            "prompt": f"{brief.store_name}：{brief.product}；{brief.selling_point}；{brief.offer}；{brief.address}",
            "merchant": brief.model_dump(exclude={"style", "aspect", "duration", "example"}),
            "scenes": [Scene(heading=h, caption=c, photo_hint=hint, duration=base+(i < extra)).model_dump()
                       for i, (h, c, hint) in enumerate(lines)]}
