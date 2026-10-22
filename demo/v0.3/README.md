# V0.3 实际导出样片

三支样片均使用工作台实际生成，包含中文配音、原创本地音乐、稳定的文字层与照片运动。每个目录同时提供可编辑作品包。

**店名、地址、经营信息均为虚构；照片为 AI 演示素材，不代表真实店主案例或营销效果。** 一张照片在不同分镜中复用不同构图。

| 示例 | 真实尺寸 / 时长 | 音乐 | 视频 | 可编辑作品 |
| --- | --- | --- | --- | --- |
| 咖啡到店邀请 | 1080 × 1920 / 18.250 秒 | 温暖氛围 | [播放 MP4](coffee/video.mp4) | [导入作品 ZIP](coffee/project.zip) |
| 烘焙独立口播 | 1920 × 1080 / 20.167 秒 | 柔和琴音 | [播放 MP4](bakery/video.mp4) | [导入作品 ZIP](bakery/project.zip) |
| 花店产品主推 | 1080 × 1080 / 16.583 秒 | 清亮节奏 | [播放 MP4](flowers/video.mp4) | [导入作品 ZIP](flowers/project.zip) |

共同格式：H.264 / 24 fps / AAC。烘焙第一幕使用独立口播稿，画面字幕保持简短，镜头按声音长度延长。花店第二幕使用顶部文字布局。

## 继续编辑

1. 启动工作台，打开「我的作品」。
2. 点击「导入作品包」，选择上表中的 project.zip。
3. 导入生成独立作品，照片和分镜可以继续修改；原示例与已有作品保持独立。
4. 若设备没有 macOS 婷婷语音，关闭配音即可继续导出字幕和音乐。

每个目录还包含 cover.png、subtitles.srt、post.txt、storyboard.json。JSON 是这次成片的内容与导出设置快照；如需迁移继续编辑，请使用 project.zip。

## 验证记录

2026-10-23：三支 MP4 均完成 FFmpeg 全片解码，无解码错误；三份作品包分别导入全新临时数据库，并逐幕成功生成预览。原生语音与播放器 metadata 在本机浏览器核对。机器可读记录见 [manifest.json](manifest.json)。

原图和完整生成提示词见 [咖啡素材](../merchant/README.md) 及 [花店、烘焙素材](../showcase/README.md)。均使用内置 image_gen 工具，未使用 CLI/API fallback。

界面实测截图：[桌面工作台](studio.png)、[手机成片预览](mobile.png)、[手机拍摄清单](shooting-plan.png)、[发布助手](publish-assistant.png)。[拍摄清单 TXT](shooting-plan.txt) 是从工作台实际下载的五幕宠物门店虚构示例，可用于了解素材准备方式。
