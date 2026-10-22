from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Brief(BaseModel):
    prompt: str = Field(min_length=5, max_length=800)
    style: Literal["cinema", "editorial", "tech"] = "cinema"
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    duration: Literal[15, 30, 45, 60] = 15
    mode: Literal["template", "ai"] = "template"

    @field_validator("prompt")
    @classmethod
    def trim_prompt(cls, value):
        value = value.strip()
        if len(value) < 5:
            raise ValueError("请至少输入 5 个字的创意描述")
        return value


class Scene(BaseModel):
    heading: str = Field(min_length=1, max_length=32)
    caption: str = Field(min_length=1, max_length=96)
    duration: int = Field(ge=2, le=20)
    asset_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    crop_x: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    crop_y: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)
    zoom: float = Field(default=1, ge=1, le=2, allow_inf_nan=False)
    photo_fit: Literal["cover", "contain"] = "cover"
    motion: Literal["zoom_in", "zoom_out", "still", "pan_left", "pan_right"] = "zoom_in"
    text_position: Literal["bottom", "center", "top"] = "bottom"

    @field_validator("heading", "caption")
    @classmethod
    def clean_text(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("分镜文字不能为空")
        return value


class MerchantProfile(BaseModel):
    industry: Literal["coffee", "food", "bakery", "beauty", "pet", "flowers"] = "coffee"
    scenario: Literal["visit", "product", "offer", "story"] = "visit"
    store_name: str = Field(min_length=1, max_length=24)
    product: str = Field(min_length=1, max_length=32)
    selling_point: str = Field(min_length=1, max_length=48)
    offer: str = Field(default="", max_length=40)
    address: str = Field(min_length=1, max_length=48)
    cta: str = Field(default="欢迎到店，发现一份喜欢。", min_length=1, max_length=32)

    @field_validator("store_name", "product", "selling_point", "address", "cta", "offer")
    @classmethod
    def clean_merchant_text(cls, value, info):
        value = " ".join(value.split())
        if not value and info.field_name != "offer":
            raise ValueError("请填写门店信息")
        return value

    @model_validator(mode="after")
    def offer_needs_details(self):
        if self.scenario == "offer" and not self.offer:
            raise ValueError("活动宣传需要填写活动信息，包括具体内容与适用时间")
        return self


class ProjectEdit(BaseModel):
    title: str = Field(min_length=1, max_length=32)
    style: Literal["cinema", "editorial", "tech"]
    aspect: Literal["9:16", "16:9", "1:1"]
    scenes: list[Scene] = Field(min_length=1, max_length=8)
    version: int = Field(ge=1)
    accent_color: str | None = Field(default=None, pattern=r"^#[a-fA-F0-9]{6}$")
    cover_scene: int = Field(default=0, ge=0, le=7)
    merchant: MerchantProfile | None = None

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value):
        if not value.strip():
            raise ValueError("项目名称不能为空")
        return value.strip()

    @model_validator(mode="after")
    def check_total(self):
        if sum(s.duration for s in self.scenes) > 60:
            raise ValueError("视频总时长不能超过 60 秒")
        if self.cover_scene >= len(self.scenes):
            raise ValueError("请选择已有分镜作为封面")
        return self


class ProjectState(BaseModel):
    version: int = Field(ge=1)
    archived: bool


class VersionRequest(BaseModel):
    version: int = Field(ge=1)


class PreviewRequest(ProjectEdit):
    index: int = Field(ge=0, le=7)


class RenderRequest(BaseModel):
    version: int = Field(ge=1)
    music: bool = True
    narration: bool = False
    quality: Literal["720p", "1080p"] = "720p"
    speech_rate: int = Field(default=210, ge=140, le=280)
    music_volume: float = Field(default=.5, ge=0, le=1, allow_inf_nan=False)

    @model_validator(mode="after")
    def normalize_inactive_settings(self):
        if not self.narration:
            self.speech_rate = 210
        if not self.music:
            self.music_volume = .5
        return self


class VoicePreview(BaseModel):
    text: str = Field(min_length=1, max_length=96)
    speech_rate: int = Field(default=210, ge=140, le=280)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("请先填写要试听的字幕")
        return value.strip()


class ShowcaseRequest(BaseModel):
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"


class MerchantBrief(MerchantProfile):
    style: Literal["cinema", "editorial", "tech"] = "editorial"
    aspect: Literal["9:16", "16:9", "1:1"] = "9:16"
    duration: Literal[15, 30, 45, 60] = 15
    example: bool = False
