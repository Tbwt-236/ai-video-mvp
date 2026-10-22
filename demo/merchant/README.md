# 咖啡店宣传样片 · V0.2

这是虚构门店「拾光咖啡（演示）」的功能验证，不是真实店主案例，没有验证营销效果或商业转化。

- `video.mp4`：实际使用工作台导出的 18.25 秒竖屏视频，720×1280 / H.264 / 24 fps，含 macOS 婷婷中文配音及本地合成音乐。
- `cover.png`：第一幕封面。
- `post.txt`：可编辑的发布文案，保留虚构示例提示。
- `subtitles.srt`：逐幕配音字幕，按实际声音长度计算。
- `storyboard.json`：导出时的不可变分镜快照，包含实际时长与每幕语音长度。照片 ID 属于制作时的本地项目，重新制作时需要重新上传下方图片。
- `coffee-ai-demo.png`：首幕 AI 演示图片，不是真实商品或门店照片；后两幕使用应用图形模板。

制作步骤：填写页面虚构示例 → 首幕上传此目录的图片 → 保存 → 保留配音及音乐 → 导出。初始三幕各 5 秒；后两幕为避免截断朗读，分别延长至约 6.42 秒及 6.83 秒。

## 图片来源与提示词

2026-10-12 使用内置 imagegen 工具生成，未使用 CLI/API fallback；完整提示词如下：

> Use case: photorealistic-natural. Asset type: demo photo for a fictional Chinese independent coffee shop marketing video; it will be labeled as AI demo imagery in the app and repository. Create one vertical 9:16 editorial photograph: a ceramic cup of osmanthus latte with subtle latte art on a warm wooden table beside a cafe window, small golden osmanthus blossoms, a softly blurred empty independent cafe behind it. Natural late afternoon light, warm cream and muted olive tones, realistic materials, calm inviting mood. Place the cup and its saucer prominently in the upper half, keep the lower third a quiet wooden tabletop suitable for adding captions in software. No people, no brand, no signage, no text or watermark. Single photo, not a collage.

## 后续版本

此目录保留 V0.2 历史样片。V0.3 已增加多行业模板、分镜与构图编辑、独立口播、多画幅副本、1080p、作品备份和三组一键示例，无需店主反馈即可按 [验收说明](../../docs/ACCEPTANCE.md) 完整体验。

最新成片与可编辑作品包见 [V0.3 演示目录](../v0.3/README.md)。样例均为虚构素材，未声称验证真实商业转化。
