# 原琴工具箱 3.4 · MIDI 转换与游戏演奏

[![tests](https://github.com/wycwysgs/yuanqin-converter/actions/workflows/test.yml/badge.svg)](https://github.com/wycwysgs/yuanqin-converter/actions/workflows/test.yml)
[![license](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

把 MIDI 批量转换为《原神》乐器可用的 GS2 曲谱，并在同一个程序里管理、试听和演奏。支持 BetterGI 的 YuanQinAssistant，也可使用自带播放器。

**[下载 Windows 版](https://github.com/wycwysgs/yuanqin-converter/releases/latest)** · [详细使用说明](docs/使用说明.txt)

## 3.4 版

- 主窗口和游戏悬浮窗统一为深蓝、青绿色主题，新增音符图标。
- 曲库、转换队列、导出和演奏设置分区显示；开始与停止按钮更醒目。
- 主窗口可滚动，悬浮窗保持紧凑布局，支持搜索和选择歌曲。

## 功能

- **批量转换**：多选 MIDI 或添加整个文件夹；单首失败继续处理，输出 CSV 记录。
- **轨道与编曲**：完整伴奏、简化伴奏（每组最多 3 音）、主旋律（优先最高音）。
- **自动移调**：根据实际音符时长推荐白键适配率较高的移调；支持手动调整、半音修正和鼓轨过滤。
- **保留节奏**：读取 MIDI 速度变化；转换与演奏均支持调整倍率。
- **一首一份曲谱**：转换为通用三排 GS2；演奏时勾选三排模式，取消则折回为两排，无需重复生成。
- **曲库与演奏**：列表连播、倒计时、间隔、自定义全局快捷键，切出游戏或按住修饰键时自动暂停。
- **悬浮控制**：置顶窗口可搜索、选曲、试听、开始、暂停和停止，并显示游戏连接与权限提示。
- **试听与自检**：合成音色试听前 20 秒；“测试琴键 A”倒计时后只发送一次琴键。
- **设置记忆**：保存曲库、速度、排数、快捷键、转换选项和悬浮窗位置。

## 快速使用

1. 从 [Releases](https://github.com/wycwysgs/yuanqin-converter/releases/latest) 下载 `yuanqin-converter.exe`，双击运行，在 Windows 管理员提示中选择“是”。Windows x64，无需安装 Python。
2. 打开工具箱，在 **MIDI 转换** 页添加文件，按需调整轨道和编曲，点击 **转换并加入曲库**。
3. 在曲库或悬浮窗选择歌曲，可先 **试听前20秒**。按乐器勾选或取消 **三排模式**。
4. 原神使用窗口或无边框模式，打开乐器演奏界面，关闭聊天框。
5. 点击悬浮窗 **开始 / 继续**，程序请求切回游戏，默认倒计时 3 秒后开始。
6. 默认 **F8** 开始 / 暂停，**F9** 停止。切出游戏会自动暂停；停止后再次开始会从曲首播放。

“批量安装到助手”可输出到 BetterGI 的曲谱目录，默认：

```text
C:/Program Files/BetterGI/User/JsScript/YuanQinAssistant/assets/score
```

设置保存在 `%LOCALAPPDATA%/YuanQinToolbox/settings.json`。程序旁的 `曲谱` 文件夹存放“转换并加入曲库”的结果。

## 源码运行与打包

Windows、Python **3.10+**（含 tkinter）：

```powershell
python -m pip install -r requirements.txt
python app.py
```

默认打开悬浮窗。`python app.py --main` 打开主窗口；`python app.py --preview --main` 仅预览界面，不注册全局快捷键、不发送琴键、不读写正式用户设置。

源码运行若需匹配游戏的管理员权限，请从管理员终端启动。发布的 EXE 已设置启动时请求管理员权限。

```powershell
python -m pip install pyinstaller
python -m PyInstaller --noconfirm yuanqin.spec
```

产物为 `dist/原琴转换器.exe`，含专属图标与 `requireAdministrator` 清单。

## 键位与原理

| 音域 | MIDI 自然音 | 游戏键位 |
|---|---|---|
| 低音区（三排） | 48 50 52 53 55 57 59 | Z X C V B N M |
| 中音区 | 60 62 64 65 67 69 71 | A S D F G H J |
| 高音区 | 72 74 76 77 79 81 83 | Q W E R T Y U |

三排共 **21 键**。两排模式将低音提高一个八度映射到中音区，同刻重复琴键合并，原曲谱不修改。

转换器配对 MIDI 音符、保留速度变化，再筛选轨道、移调、处理半音、按八度折回并校验 GS2。播放器将 GS2 转为绝对时间琴键序列，通过 Windows `SendInput` 模拟按键；悬浮窗是普通置顶窗口，不向游戏注入窗口或读取游戏内存。

## 限制

- 支持 MIDI Type 0/1；不支持 Type 2、SMPTE 或直接转换 MP3、视频、简谱图片。
- 原神乐器音域有限，半音修正和八度折回会改变部分旋律与和声；试听音色与游戏不同。
- 主旋律模式按最高音选取，无法保证识别人声旋律。踏板、力度、音色和弯音不还原。
- 程序不能判断游戏是否已打开乐器界面，也不能自动判断琴键是否发声；可使用“测试琴键 A”检查。
- 悬浮窗适合窗口/无边框游戏；独占全屏下可能不可见。
- 当前不保存未转换的 MIDI 队列和逐首临时编辑。

## 测试

```powershell
python -m unittest discover -s tests -v
```

测试使用现场生成的 MIDI 和临时文件；游戏输入通过替身测试，不向真实游戏发送琴键。

## 第三方与许可

本项目与 HoYoverse、[BetterGI](https://github.com/babalae/better-genshin-impact) 无关联。依赖 [mido](https://github.com/mido/mido)（MIT）。仓库和发布包不包含 MIDI 源文件、个人曲谱或运行日志。

[MIT](LICENSE)

## English

Yuanqin Toolbox is a Windows GUI for batch MIDI-to-GS2 conversion, library management, synthesized preview and Genshin Impact instrument playback. Version 3.4 adds a shared navy/teal interface and a compact topmost player. Choose two or three keyboard rows at playback time. Download the executable from Releases, or run `python app.py` with Python 3.10+ and mido. The executable requests administrator privileges to match an elevated game. No MIDI files or finished music scores are distributed.
