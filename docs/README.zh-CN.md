# SoundSplitter

[English](../README.md) | 简体中文

把两个独立的音箱组合成立体声音箱：一个播放左声道，另一个播放右声道。SoundSplitter 保持输出音频流同步，并提供独立的声道延迟调整，用于补偿设备之间的固定延迟差。

**适用于 Windows。** 使用两个 Windows 能识别的不同音频输出设备。有线、USB 和蓝牙设备可以组合使用，音乐播放器、浏览器或游戏继续照常使用即可。

## 1. 开始使用 SoundSplitter

### 安装 SoundSplitter

1. 从[最新发行版](https://github.com/handsome-Druid/SoundSplitter/releases/latest)下载 `setup.exe` 并运行，允许安装器请求的管理员权限。
2. 安装器会检测 **VB-CABLE**，未检测到时提供下载链接。需要使用它时，请单独安装驱动；安装器不会替你安装。

只有安装器需要管理员权限。请以普通用户身份运行 SoundSplitter 主程序。

如果电脑上有 **Steam Streaming Speakers**，并且只使用**回环采集**模式，就不需要 VB-CABLE，请按照第 2 节操作。安装器的“**未检测到**”提示只针对 VB-CABLE，不影响该回环采集方案的使用。

### 使用 VB-CABLE 播放

1. 尚未安装 [VB-CABLE](https://vb-audio.com/Cable/) 时先安装它。按照驱动安装说明操作，如果要求重启 Windows，请先重启。
2. 连接两个音箱，确认 Windows 将它们识别为独立的播放设备。将 Windows 声音输出设为 **CABLE Input**。
3. 打开 SoundSplitter。它会加载保存的设置；没有已保存的可用输入源时，自动选择 **CABLE Output**，并在使用该 VB-CABLE 输入源时为 **CABLE Input** 开启“**音量监听**”。随后会自动尝试开始分流。
4. **尚未开始分流时**，在“**选择左声道输出**”和“**选择右声道输出**”中选择两个实际音箱，再点击“**开始分流**”。左右输出必须是不同设备，不要将虚拟声卡选为输出。
5. 以较低音量播放立体声音频。没有听到时间差时，保持两侧声道延迟为 `0`。

**SoundSplitter 已经使用正确的输入源和输出设备开始分流时，直接播放音频即可，不要为了重复配置步骤而停止分流。**

```text
Windows / App -> CABLE Input -> CABLE Output -> SoundSplitter -> L + R
```

音频**送入 CABLE Input**，并**从 CABLE Output 读取**。标准 VB-CABLE 方案使用**关闭回环采集**的模式，这也是新配置的默认值；已经检测到的输入源不需要重新选择。

设置会自动保存。之后启动会恢复这些选择并尝试自动继续分流，不需要重复配置相同的设备。

## 2. 更多音频路由方式

回环采集会捕获播放设备上的音频。**开启回环采集**时选择播放设备作为输入源，**关闭回环采集**时选择录音设备作为输入源。VB-CABLE 支持这两种模式。

**Steam Streaming Speakers** 是 Steam 的虚拟播放设备。**开启回环采集**并选择它，即可分流其音频，无需安装 VB-CABLE。

| 你的配置 | 是否安装 VB-CABLE？ | 回环采集 | SoundSplitter 中的音频输入源 |
|---|---|---|---|
| 标准 VB-CABLE 配置 | 需要，除非已经安装 | 关闭 | `CABLE Output` |
| 使用 Steam Streaming Speakers 回环采集 | 不需要 | 开启 | `Steam Streaming Speakers` |
| 没有 Steam Streaming Speakers，使用回环采集 | 建议安装 VB-CABLE | 开启 | `CABLE Input` |

这些是不同的配置方案，不需要在已经正常工作的配置上重复操作。只有要更改正在运行的配置的输入源或回环采集模式时，才需要停止分流，更改后重新开始。尚未分流时，直接配置即可。

### 不安装 VB-CABLE，使用 Steam Streaming Speakers

1. 将 Windows 声音输出或播放器输出设为 **Steam Streaming Speakers**。
2. 在 SoundSplitter 中开启“**回环采集**”，并选择 **Steam Streaming Speakers** 作为音频输入源。
3. 选择两个实际音箱作为左右输出。
4. 点击“**开始分流**”并播放音频。

这个回环采集方案不需要 VB-CABLE。

### 在回环采集模式下使用 VB-CABLE

没有 Steam Streaming Speakers 时，建议安装 VB-CABLE，包括使用回环采集时。将 Windows 或应用的音频发送到 **CABLE Input**，开启“**回环采集**”，并选择 **CABLE Input** 作为输入源。选择实际音箱作为左右输出，再开始分流。

```text
Windows / App -> CABLE Input [Loopback] -> SoundSplitter -> L + R
```

回环采集**关闭**时，选择 **CABLE Output** 作为 VB-CABLE 输入源；回环采集**开启**时，选择 **CABLE Input**。更改模式后再选择输入源，因为输入源列表会在录音设备和播放设备之间切换。

## 3. 进阶调整

分流过程中要更改输入源、输出设备、回环采集模式、音量监听配置或声道延迟时，点击“**停止分流**”，完成更改后再点击“**开始分流**”。尚未分流时，直接配置这些控件即可。输出音量滑块和静音按钮在分流时仍可使用。

### 只分流某个应用的音频

通过该应用的输出选择器或 Windows 音量混合器，将它的音频发送到与 SoundSplitter 路由匹配的 **CABLE Input** 或 **Steam Streaming Speakers**。其他应用继续使用原来的播放设备。仅以这种方式更改应用的输出，不需要停止 SoundSplitter。

SoundSplitter 捕获的是选定的音频端点，而不是某个单独的进程。如果多个应用通过同一个端点播放，它们的音频会一起被分流。

### 平衡音量与静音

- 左右音量滑块和扬声器按钮控制各自选定输出设备在 Windows 中的音量和静音状态，不只影响 SoundSplitter 的音频。
- 在标准 VB-CABLE 配置中，会自动为 **CABLE Input** 开启“**音量监听**”，使分流音频跟随该设备的音量和静音状态。
- 使用其他非回环采集输入源时，如果希望跟随某个播放设备的音量，请开启“**音量监听**”，并在旁边选择对应的播放设备；不希望跟随时可以关闭。
- 在回环采集模式下，单独的“**音量监听**”控件会被锁定，无法独立更改。

### 对齐延迟不同的音箱

使用“**左声道延迟（毫秒）**”和“**右声道延迟（毫秒）**”为较快的一侧增加延迟。两者默认都为 `0`。

例如，如果右侧音箱听起来比左侧晚约 `100` 毫秒，将左侧延迟设为 `100`，右侧保持 `0`。重新开始分流试听，并以较小的步幅调整。

补偿固定延迟差后，两台设备的播放保持同步。

### 语言、开机自启与系统托盘

- 使用语言选择器切换可用的界面语言，所选语言会被保存。
- 开启“**开机自启**”后，登录 Windows 时 SoundSplitter 会在系统托盘中启动。
- 最小化窗口或选择“**隐藏到托盘**”，可以让分流在后台继续运行。点击托盘图标可重新显示窗口。
- 关闭窗口会询问是否退出，并不等于隐藏窗口。也可以从托盘菜单选择“**退出**”。
- 程序同时只能运行一个实例。如果 SoundSplitter 已在运行，请先检查系统托盘，再启动其他副本。

## 4. 常见问题

| 问题 | 检查内容 |
|---|---|
| 没有声音 | 确认音频正在发送到虚拟播放设备，输入源与回环采集模式匹配，且两个实际输出设备均已选择、没有静音。如果开启了音量监听，也要检查被监听设备的音量。 |
| 只有一侧播放 | 检查两侧输出选择、音量和静音按钮。尝试播放左右声道都有内容的立体声音频。 |
| 缺少设备 | 确认 Windows 能够识别该设备，且设备已启用。点击“**刷新输出设备**”更新输出列表，或重新打开输入源菜单以刷新其中的设备。 |
| 缺少 Steam Streaming Speakers | 使用推荐的 VB-CABLE 配置。它同时支持标准采集和回环采集模式。 |
| 安装器提示未检测到 VB-CABLE | 使用 VB-CABLE 方案时请安装 VB-CABLE。Steam Streaming Speakers 回环采集方案不需要它。 |
| 回声或反馈 | 使用虚拟播放设备作为输入源，不要捕获 SoundSplitter 正在写入的任一实际输出设备。左右输出保持为实际音箱。 |
| 一个音箱比另一个播放得晚 | 停止分流，为较快的一侧增加声道延迟以补偿延迟差，然后重新开始分流。 |

## 5. 停止使用或卸载 SoundSplitter

1. 不再需要音频分流时，点击“**停止分流**”。
2. 将 Windows 或应用的输出改回普通播放设备。停止 SoundSplitter **不会**自动替你将 Windows 输出从虚拟设备切走。
3. 要移除应用，请在 Windows“**设置 > 应用 > 已安装的应用**”中卸载 **SoundSplitter**。在卸载器中，勾选“**保留用户数据**”可保留设置供以后安装时使用；不勾选则删除设置。

部分卸载临时文件会被登记为在 Windows 下次启动时删除。卸载 SoundSplitter 不会卸载 VB-CABLE 或 Steam 的音频设备。

## 6. 从源码编译

在 Windows 上安装 Python 3.14+ 和 [uv](https://docs.astral.sh/uv/)。从仓库根目录运行以下命令，安装依赖、生成界面／资源和翻译，并构建安装程序：

```powershell
uv run pyside6-rcc src\SoundSplitter\integration\app\resources\resources.qrc -o src\SoundSplitter\integration\app\resources\resources_rc.py
uv run pyside6-uic src\SoundSplitter\integration\app\ui\main_window.ui -o src\SoundSplitter\integration\app\ui\main_window_ui.py
uv run pyside6-rcc src\setup\resources\resources.qrc -o src\setup\resources\resources_rc.py
uv run pyside6-uic src\setup\ui\main_wizard.ui -o src\setup\ui\main_wizard_ui.py
uv run pyside6-rcc src\uninstall\resources\resources.qrc -o src\uninstall\resources\resources_rc.py
uv run pyside6-uic src\uninstall\ui\main_wizard.ui -o src\uninstall\ui\main_wizard_ui.py

uv run pyside6-lupdate -recursive -extensions py,ui -source-language en_US -target-language zh_CN src\SoundSplitter -ts translations\SoundSplitter\zh_CN.ts
uv run pyside6-lrelease translations\SoundSplitter\zh_CN.ts -qm translations\SoundSplitter\zh_CN.qm
uv run pyside6-lupdate -recursive -extensions py,ui -source-language en_US -target-language zh_CN src\setup -ts translations\setup\zh_CN.ts
uv run pyside6-lrelease translations\setup\zh_CN.ts -qm translations\setup\zh_CN.qm
uv run pyside6-lupdate -recursive -extensions py,ui -source-language en_US -target-language zh_CN src\uninstall -ts translations\uninstall\zh_CN.ts
uv run pyside6-lrelease translations\uninstall\zh_CN.ts -qm translations\uninstall\zh_CN.qm

uv run nuitka --onefile --onefile-no-dll --follow-imports --output-dir=build --enable-plugin=pyside6 --noinclude-custom-mode=pydantic.v1:bytecode --include-module=av._cyutil --windows-console-mode=hide --windows-icon-from-ico=resources\icon.ico --include-windows-runtime-dlls=no --no-prefer-source-code --project-name=SoundSplitter --main-entry-point=soundsplitter=SoundSplitter:main --main-entry-point=setup=setup:main --main-entry-point=uninstall=uninstall:main --output-filename=setup.exe --user-package-configuration-file=nuitka.yml --include-data-dir=./translations=translations --include-data-files=.venv\Lib\site-packages\PySide6\translations\qtbase_*.qm=PySide6/translations/ --noinclude-data-files=**/*.ts
```

生成的安装程序位于 `build\setup.exe`。生成的界面／资源模块和编译后的翻译文件被 Git 忽略，因此从全新检出的仓库构建前需要重新生成。
