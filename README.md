# FRAME 拾帧 · AI Video MVP

填写门店信息、上传照片，制作带中文配音的宣传短视频，同时拿到封面和发布文案。

V0.2 首先面向咖啡小店的到店宣传，保留自由创意工作流。门店文案使用明确的本地模板，无需 API 密钥；配置 DeepSeek 后，自由创意模式可使用 AI 编写分镜。

先看 [18.25 秒咖啡店样片](demo/merchant/video.mp4)、[封面](demo/merchant/cover.png)、[发布文案](demo/merchant/post.txt) 和 [演示说明](demo/merchant/README.md)。门店与地址均为虚构，首幕为 AI 演示图片，后两幕为动态图形；样片不是实际商家案例。原有 [15 秒动态文字样片](demo/FRAME-demo.mp4) 仍保留。

## 一分钟启动

需要 Python 3.10+，推荐 Python 3.12。首次安装依赖需要联网，安装后本地模板模式可离线运行。

**macOS / Linux**

```bash
bash start.sh
```

macOS 也可以双击 `start.command`。浏览器打开 **http://127.0.0.1:8000**，保留启动终端，按 `Ctrl+C` 停止。

**Windows / 手动安装**

```bash
python -m venv .venv
# Windows:
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python run.py
# macOS / Linux:
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

FFmpeg 可执行程序由 `imageio-ffmpeg` 提供；仓库自带 Noto 中文字体，无需额外安装字体或 Node.js。

## 3 分钟演示路线

1. 在「商家宣传」填写店名、产品、特色、活动（可留空）、地址与到店邀请。也可点击「填入虚构示例」。
2. 保留 9:16 / 15 秒，点击「生成我的分镜」。文案只采用表单中的信息，不编造优惠、期限或经营事实。
3. 为每幕上传产品、店内环境或门头照片。支持静态 JPG / PNG / WebP，单张 ≤8 MB、≤2000 万像素，每个项目最多 40 次上传。仓库中的 `demo/merchant/coffee-ai-demo.png` 可用于纯演示。
4. 编辑标题、字幕与时长，点击「保存分镜」，检查照片的居中裁切及文字可读性。未上传的镜头继续使用图形背景。
5. macOS 已安装「婷婷」中文语音时，可启用「中文配音」，配音会朗读每幕字幕。音乐在配音开启时自动降低音量。
6. 点击「导出视频」，播放后下载 MP4、SRT、封面 PNG、发布文案 TXT 和导出快照 JSON。开启配音时，过短的镜头自动延长，页面显示实际成片时长。
7. 在「我的作品」搜索并重新打开，最近一次导出结果及声音选项会恢复。正式发布前用真实门店信息和照片核对成片；虚构示例的文案下载会带演示标识。

## 已实现

- 中文创作工作台、作品库、搜索、最近项目和使用指南；适配桌面与手机窄屏。
- 咖啡店引导表单：产品、特色、活动与到店邀请自动编排为 3 / 5 个可编辑分镜。
- 照片上传、替换、移除；自动纠正方向、移除 EXIF、最长边压至 2400px。原始照片不保留，处理后的照片按项目隔离，并作为不可变文件供历史导出快照复用。
- 三种动态视觉模板：日落电影感、自然编辑风、未来科技感。
- 9:16、16:9、1:1；初始 15 / 30 / 45 / 60 秒，分镜可逐段调整，总长不超过 60 秒。
- 分镜标题、字幕、时长、作品名称、画幅与风格可编辑；未保存修改有提示。
- 服务端生成中文预览图；MP4 使用同一排版函数，并加入缓慢镜头运动和淡入淡出。
- H.264 / yuv420p / 24 fps；竖屏 720×1280，横屏 1280×720，方形 720×720。
- macOS 本机中文配音、可选原创氛围音轨（AAC）；MP4、SRT、JSON、封面 PNG、发布文案 TXT 下载。
- 配音按实际音频长度对齐每幕，长字幕会延长镜头，最多 120 秒；SRT 为逐幕字幕，涵盖该幕朗读区间，不是逐字卡拉 OK 字幕。画面文字整幕显示。
- SQLite 本地持久化、版本冲突检查、导出快照、队列进度、重复导出去重、失败重试、重启中断恢复。
- 视频支持 HTTP Range，便于拖动播放进度。服务默认仅监听本机。

## 能力边界

**门店模式按表单编排文案，自由创意的本地模式匹配预设文案，两者都不调用 AI。** 门店模板目前针对咖啡类到店宣传；活动原样写入，不会自动核验价格或日期。自由创意保留城市、咖啡、创作工具及通用结构。界面会明确显示来源。

**AI 模式用 DeepSeek 编写标题和字幕，画面由本地照片/图形模板渲染。** 产品内没有实拍素材生成、扩散视频模型、自动剪辑原始视频、账号系统或多人协作。仓库样片的 AI 演示图片是制作时预先生成的素材，应用不会联网生成图片。

**中文配音目前仅支持 macOS 的已安装婷婷语音。** Windows / Linux 会明确禁用此选项，仍能导出照片、字幕和音乐；不会用无声文件冒充配音。macOS 语音生成失败会明确报错，可关闭配音重试。首次安装系统语音可能需要在系统设置中下载。

分镜预览用于检查构图和文字；最终时序、镜头运动、淡入淡出和音频以导出 MP4 为准。

## 可选：启用真实 AI 分镜

```bash
cp .env.example .env
```

在 `.env` 中填写自己的 `DEEPSEEK_API_KEY`，按需调整 `DEEPSEEK_MODEL`，然后重启。环境变量优先于 `.env`。界面中选择「DeepSeek AI」才会调用模型，并把创意发送至 DeepSeek，可能产生 API 费用。

```dotenv
DEEPSEEK_API_KEY=填写你自己的密钥
DEEPSEEK_MODEL=deepseek-flash
```

密钥仅在服务端读取，不会下发浏览器、不写入作品或导出文件。`.env` 已忽略，请勿提交密钥。AI 请求超时、无效密钥、限流及格式错误会明确报错，不会悄悄改用模板并宣称生成成功。

接口依据：[DeepSeek Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) 与 [JSON Output](https://api-docs.deepseek.com/guides/json_mode/)。可用模型和费用以提供商账户及文档为准。

## 项目结构

```text
app/
  main.py          FastAPI 路由、任务队列与同源检查
  models.py        创意、分镜与保存请求校验
  storyboard.py    本地模板与 DeepSeek 适配器
  merchant.py      基于填写事实的咖啡店文案模板
  assets.py        照片校验、方向修正与无 EXIF 标准化
  narration.py     可选 macOS 本机中文语音
  renderer.py      中文画面、FFmpeg 合成、音轨和 SRT
  store.py         SQLite 项目与任务持久化
web/               原生 HTML / CSS / JavaScript，无前端构建依赖
assets/fonts/      Noto Sans CJK SC 与 OFL 许可证
tests/             接口、任务与真实视频导出验收
data/              启动后产生；不纳入 Git
run.py             加载环境配置、启动本机服务
```

数据保存在 `data/studio.sqlite3`，照片位于 `data/assets/<项目 ID>/`，导出文件位于 `data/exports/<任务 ID>/`。备份时先停止服务，再复制整个 `data` 文件夹。照片及用户数据不纳入 Git。导出临时文件会在结束后清理；历史成片及照片持续保留。旧项目无需迁移仍可打开；旧任务缺少封面与文案时，保存一次分镜并重新导出即可补齐。

## 验收

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

测试涵盖输入校验、持久化、并发保存冲突、AI 适配器结构与错误（mock）、队列上限和去重、导出快照、重启恢复、三种比例的真实 FFmpeg 导出、MP4 完整解码、HTTP Range、门店事实编排、三种图片格式与 EXIF 清理、项目照片隔离、上传流大小限制、配音不可用/失败，以及配音延长后的音视频和 SRT 时间轴。

本次本地结果：**31 passed**。另有上游 Starlette / AnyIO 的一个弃用提示，不影响运行。自动测试使用可控语音音轨验证时序；真实 macOS 配音另通过随仓库样片和浏览器播放验证。`requirements-lock.txt` 固定本次验证使用的运行依赖。

真实 DeepSeek 请求需要用户密钥；本次交付没有密钥，未声称完成真实模型联调。GitHub Actions 工作流已提供，推送后可在 Linux 上运行；本地验收在 macOS / Python 3.12 完成。

## 常见问题

- **8000 端口被占用**：在 `.env` 设置 `PORT=8001` 后重启，访问相应地址。
- **首次运行提示缺少模块**：重新运行 `bash start.sh`，或按手动步骤安装 `requirements.txt`。
- **无法播放 / 导出失败**：检查终端日志、磁盘空间和 `/api/health`。页面保留作品，支持重试。
- **服务重启时中断导出**：任务会标记失败，重新打开项目并导出即可。
- **自定义字体**：用 `VIDEO_FONT` 指向支持中文的 TTF / OTF 字体。
- **对外部署**：当前版本面向个人本地演示。公开部署前需要实现认证、每用户数据隔离、配额、持久化任务服务及 HTTPS；不要直接把本地端口暴露到公网。请使用单个应用进程，避免不同进程争抢任务。

中文字体来自 [Noto CJK](https://github.com/notofonts/noto-cjk)，使用 SIL Open Font License，许可证随字体附带。图形由代码绘制，音乐由本地正弦合成；上传的照片用于本机制作，请使用你有权使用的素材。演示图片的生成方式和完整提示词见 [素材说明](demo/merchant/README.md)。
