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

    @field_validator("heading", "caption")
    @classmethod
    def clean_text(cls, value):
        value = " ".join(value.split())
        if not value:
            raise ValueError("分镜文字不能为空")
        return value


class ProjectEdit(BaseModel):
    title: str = Field(min_length=1, max_length=32)
    style: Literal["cinema", "editorial", "tech"]
    aspect: Literal["9:16", "16:9", "1:1"]
    scenes: list[Scene] = Field(min_length=2, max_length=8)
    version: int = Field(ge=1)

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
        return self


class RenderRequest(BaseModel):
    version: int = Field(ge=1)
    music: bool = True
