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

## 下一步试用方式

目前无需店主关系或更多功能开发即可开展验证：把样片当作效果说明，先在熟悉的咖啡店消费后询问是否愿意看十几秒样片，不发送未经允许的批量消息。

首轮目标是拿到 3 次具体反馈和 1 次用真实店铺照片制作的试用：对方能否看懂、是否愿意用自己的素材、最想修改什么、最终愿不愿意发布。得到真实采用意愿后再投入更多行业模板、云端配音或付费系统；这些目标目前尚未验证。
