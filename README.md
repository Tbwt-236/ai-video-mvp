# FRAME 拾帧 · AI Video MVP

从创意到分镜，再到一支可以播放、下载的动态文字短片。

基于 `Tbwt-236/ai-video-mvp` 空仓库搭建的首个可演示版本。默认无需 API 密钥；配置 DeepSeek 后可使用 AI 编写分镜。

仓库附有通过本项目实际导出的 [15 秒演示视频](demo/FRAME-demo.mp4) 和 [分镜文件](demo/storyboard.json)。

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

1. 点击「城市漫游」示例，保留「日落电影感 / 9:16 / 15 秒」。
2. 点击「生成我的分镜」：得到 3 个分镜，项目立即保存。
3. 修改第一幕字幕，例如「让脚步慢下来，在熟悉的城市发现新的风景。」
4. 点击「保存分镜」，选择缩略图查看新文字，再播放分镜预览。
5. 保留「氛围音轨」，点击「导出视频」。等待真实渲染完成。
6. 在播放器播放成片，下载 MP4、SRT 字幕和分镜 JSON。
7. 打开「我的作品」，搜索并重新打开作品，展示保存与导出结果恢复。

## 已实现

- 中文创作工作台、作品库、搜索、最近项目和使用指南；适配桌面与手机窄屏。
- 三种动态视觉模板：日落电影感、自然编辑风、未来科技感。
- 9:16、16:9、1:1；初始 15 / 30 / 45 / 60 秒，分镜可逐段调整，总长不超过 60 秒。
- 分镜标题、字幕、时长、作品名称、画幅与风格可编辑；未保存修改有提示。
- 服务端生成中文预览图；MP4 使用同一排版函数，并加入缓慢镜头运动和淡入淡出。
- H.264 / yuv420p / 24 fps；竖屏 720×1280，横屏 1280×720，方形 720×720。
- 可选本地合成的原创氛围音轨（AAC）；真实 MP4、SRT、JSON 下载。
- SQLite 本地持久化、版本冲突检查、导出快照、队列进度、重复导出去重、失败重试、重启中断恢复。
- 视频支持 HTTP Range，便于拖动播放进度。服务默认仅监听本机。

## 能力边界

**本地模式是预设文案匹配与动态图形模板，不调用 AI。** 城市、咖啡、创作工具主题有预设脚本，其他主题提供可修改的通用结构，不保证理解任意创意细节。界面会明确显示来源。

**AI 模式用 DeepSeek 编写标题和字幕，画面仍由本地动态图形模板渲染。** 本版本不包含扩散视频模型、实拍素材生成、图片上传、人声配音、账号系统或多人协作。短片中的字幕是屏幕文字，不是自动语音识别结果。

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
  renderer.py      中文画面、FFmpeg 合成、音轨和 SRT
  store.py         SQLite 项目与任务持久化
web/               原生 HTML / CSS / JavaScript，无前端构建依赖
assets/fonts/      Noto Sans CJK SC 与 OFL 许可证
tests/             接口、任务与真实视频导出验收
data/              启动后产生；不纳入 Git
run.py             加载环境配置、启动本机服务
```

数据保存在 `data/studio.sqlite3`，导出文件位于 `data/exports/<任务 ID>/`。备份时先停止服务，再复制整个 `data` 文件夹。导出过程中临时文件会在结束后清理；历史成片持续保留。

## 验收

```bash
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

测试涵盖输入校验、持久化、并发保存冲突、AI 适配器结构与错误（mock）、队列上限和去重、导出快照、重启恢复、三种比例的真实 FFmpeg 导出、MP4 完整解码、HTTP Range 和 SRT 时间轴。

本次本地结果：**19 passed**。另有上游 Starlette / AnyIO 的一个弃用提示，不影响运行。已通过浏览器操作验证生成、修改、保存、实际播放、作品搜索和刷新后重新打开，并检查 390px 窄屏无横向溢出。`requirements-lock.txt` 固定本次验证使用的运行依赖。

真实 DeepSeek 请求需要用户密钥；本次交付没有密钥，未声称完成真实模型联调。GitHub Actions 工作流已提供，推送后可在 Linux 上运行；本地验收在 macOS / Python 3.12 完成。

## 常见问题

- **8000 端口被占用**：在 `.env` 设置 `PORT=8001` 后重启，访问相应地址。
- **首次运行提示缺少模块**：重新运行 `bash start.sh`，或按手动步骤安装 `requirements.txt`。
- **无法播放 / 导出失败**：检查终端日志、磁盘空间和 `/api/health`。页面保留作品，支持重试。
- **服务重启时中断导出**：任务会标记失败，重新打开项目并导出即可。
- **自定义字体**：用 `VIDEO_FONT` 指向支持中文的 TTF / OTF 字体。
- **对外部署**：当前版本面向个人本地演示。公开部署前需要实现认证、每用户数据隔离、配额、持久化任务服务及 HTTPS；不要直接把本地端口暴露到公网。请使用单个应用进程，避免不同进程争抢任务。

中文字体来自 [Noto CJK](https://github.com/notofonts/noto-cjk)，使用 SIL Open Font License，许可证随字体附带。图形由代码绘制，音轨由本地正弦合成，不依赖远程媒体素材。
