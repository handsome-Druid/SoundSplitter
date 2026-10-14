# SoundSplitter

把两个独立的音箱当作一对立体声音箱使用：一个播放左声道，另一个播放右声道。音乐、视频和游戏照常播放，SoundSplitter 负责把声音分到两边。

适用于 Windows。

## 能做什么

- 把电脑播放的声音分成左右两路，分别交给两个音箱播放。
- 记住设置，下次启动时自动尝试开始分流。
- 最小化到系统托盘后继续运行，不必一直开着主窗口。
- 跟随系统音量和静音状态；两边播放不同步时，也可以手动补偿延迟。

## 开始使用

1. **安装虚拟声卡**：下载并安装 [VB-CABLE](https://vb-audio.com/Cable/)，按安装说明操作，必要时重启电脑。
2. **连接两个音箱**：确认 Windows 能分别识别它们，再把 Windows 的声音输出设为 `CABLE Input`。
3. **启动 SoundSplitter**：软件会自动配置 VB-CABLE 的输入源和音量监听。
4. **首次使用时选好左右音箱**，点击「开始分流」，然后照常播放音乐、视频或游戏。

设置会自动保存。以后设备连接正常时，启动软件就会按保存的设置尝试开始分流，不必每次重新配置。延迟默认是 `0`，听起来没有不同步就不用调整。

不再使用分流时，把 Windows 的声音输出切回原来的音箱即可；「停止分流」不会替你切换系统播放设备。

## 设置

修改设置前先点击「停止分流」，改好后再点击「开始分流」。

### 输入源和左右输出

- **音频输入源**：默认使用自动识别的 `CABLE Output`，换用其他虚拟声卡时，在这里选择对应的输入设备。
- **左、右声道输出**：分别选择实际播放声音的两个设备，不能选同一个设备。接入新设备后，可以点击「刷新输出设备」更新列表。
- **只分流某个应用**：在该应用或 Windows 音量混合器中，把它的输出设为 `CABLE Input`，其他应用继续使用原来的播放设备。

VB-CABLE 的名称是从虚拟声卡的角度命名的：播放器把声音送进 `CABLE Input`，SoundSplitter 从 `CABLE Output` 读取，再分别送到左右音箱。不要把左右输出选回虚拟声卡，以免形成音频回路。

### 音量监听

使用 VB-CABLE 时，音量监听会自动开启。调整 Windows 中 `CABLE Input` 的音量或静音，两边的声音会一起跟随。

换用其他虚拟声卡时，勾选「音量监听」，在旁边选择对应的播放设备。取消勾选后，左右输出不再跟随它的音量。

若两边响度不同，可以分别调整音箱或 Windows 中对应设备的音量。

### 左右声道延迟

两个设备的播放延迟可能不同，尤其是有线设备和蓝牙设备搭配使用时。可以分别设置「左声道延迟(ms)」和「右声道延迟(ms)」。

例如，右侧听起来比左侧晚约 100 毫秒，可以把左声道延迟设为 `100`，右声道保留为 `0`，再重新开始分流试听。

给较快的一侧增加延迟，边调整边试听。蓝牙设备的延迟可能波动，固定的延迟值不一定能一直保持同步。

### 托盘和开机自启

- 最小化主窗口会隐藏到托盘，分流仍可继续运行。
- 点击窗口关闭按钮会询问是否退出，不是直接隐藏到托盘。
- 勾选「开机自启」，登录 Windows 后软件会自动启动，在托盘中运行。
- 程序只允许运行一个实例。如果提示已有实例运行，先检查系统托盘。

## 从源码编译

安装 [uv](https://docs.astral.sh/uv/)，在项目目录先将 Qt UI 和资源文件编译为 Python 模块：

```powershell
uv run pyside6-rcc src\SoundSplitter\integration\app\resources\resources.qrc -o src\SoundSplitter\integration\app\resources\resources_rc.py
uv run pyside6-uic src\SoundSplitter\integration\app\ui\main_window.ui -o src\SoundSplitter\integration\app\ui\main_window_ui.py
uv run pyside6-rcc src\setup\resources\resources.qrc -o src\setup\resources\resources_rc.py
uv run pyside6-uic src\setup\ui\main_dialog.ui -o src\setup\ui\main_dialog_ui.py
uv run pyside6-lupdate -recursive -extensions py,ui -source-language en_US -target-language zh_CN src\SoundSplitter -ts translation\SoundSplitter\zh_CN.ts 
uv run pyside6-lrelease translation\SoundSplitter\zh_CN.ts -qm translation\SoundSplitter\zh_CN.qm
uv run pyside6-lupdate -recursive -extensions py,ui -source-language en_US -target-language zh_CN src\setup -ts translation\setup\zh_CN.ts
uv run pyside6-lrelease translation\setup\zh_CN.ts -qm translation\setup\zh_CN.qm
```

生成的 UI 和资源模块被 Git 忽略，首次构建时也必须生成；仅生成主程序资源不足以启动安装程序。修改 `.ui`、`.qrc` 或其引用的资源文件后，需要重新执行对应命令。使用 Nuitka 4.3 打包单文件安装程序：

```powershell
uv run nuitka --onefile --onefile-no-dll --follow-imports --output-dir=build --enable-plugin=pyside6 --noinclude-custom-mode=pydantic.v1:bytecode --include-module=av._cyutil --windows-console-mode=hide --windows-icon-from-ico=resources\icon.ico --include-windows-runtime-dlls=no --no-prefer-source-code --project-name=SoundSplitter --main-entry-point=soundsplitter=SoundSplitter:main --main-entry-point=setup=setup:main --main-entry-point=uninstall=uninstall:main --output-filename=setup.exe --user-package-configuration-file=nuitka.yml --include-data-dir=./translation=translation --noinclude-data-files=**/*.ts
```

生成的单文件安装程序位于 `build\setup.exe`。`--onefile-no-dll` 保留可执行的内部 payload；安装程序从 `__compiled__.python_runtime_dir` 复制完整 payload，再复制改名内部 EXE 实现各个入口。

## 遇到问题时

- **没有声音**：确认原应用正在播放，输出已设为 `CABLE Input`，本工具输入选的是 `CABLE Output`，左右输出选择正确且没有静音。如果启用了音量监听，也检查被监听设备的音量。
- **只听到一侧**：检查原音频是否只有一个声道有声音，再检查对应的输出设备是否正常。
- **设备没有出现在列表中**：先确认 Windows 能识别设备；输出列表可点击「刷新输出设备」，必要时重新打开程序。
- **左右不同步**：给较快的一侧增加延迟；设备本身的延迟波动可能仍会影响效果。
