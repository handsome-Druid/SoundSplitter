# SoundSplitter

English | [简体中文](docs/README.zh-CN.md)

Turn two separate speakers into a stereo pair: one plays the left channel, and the other plays the right. SoundSplitter keeps the output audio streams synchronized and provides independent channel delay adjustment to compensate for fixed differences in device latency.

**For Windows.** Use two different audio output devices recognized by Windows. Wired, USB, and Bluetooth devices can be used together. Keep using your music player, browser, or game as usual.

## 1. Start using SoundSplitter

### Install SoundSplitter

1. Download `setup.exe` from the [latest release](https://github.com/handsome-Druid/SoundSplitter/releases/latest) and run it. Approve the installer's administrator prompt.
2. The installer checks for **VB-CABLE** and offers a download link if it is not detected. Install the driver separately if you are going to use it; the installer does not install it for you.

Only the installer needs administrator privileges. Run the SoundSplitter application as a normal user.

If your PC has **Steam Streaming Speakers** and you will use **Loopback** mode only, you do not need VB-CABLE: follow Section 2. The installer's **Not detected** message refers only to VB-CABLE and does not prevent that loopback setup from working.

### Play through VB-CABLE

1. Install [VB-CABLE](https://vb-audio.com/Cable/) if it is not already installed. Follow its driver instructions and restart Windows if requested.
2. Connect both speakers and confirm that Windows recognizes them as separate playback devices. Set the Windows sound output to **CABLE Input**.
3. Open SoundSplitter. It loads saved settings, automatically selects **CABLE Output** if no usable source is saved, and enables **Volume Monitoring** for **CABLE Input** when using that VB-CABLE source. It then attempts to start splitting.
4. **If splitting has not started**, select the two physical speakers under **Select left channel output** and **Select right channel output**, then click **Start Splitting**. The outputs must be different devices; do not select the virtual cable as an output.
5. Play stereo audio at a low volume. Leave both channel latency values at `0` unless you hear a timing difference.

**If SoundSplitter has already started splitting with the correct source and outputs, just play audio. Do not stop it to repeat the setup steps.**

```text
Windows / App -> CABLE Input -> CABLE Output -> SoundSplitter -> L + R
```

Audio is sent **into CABLE Input** and read **from CABLE Output**. The standard VB-CABLE route uses **Loopback off**, which is the default for a new configuration; there is no need to select the detected source again.

Settings are saved automatically. Later launches restore those choices and attempt to resume splitting; you do not need to configure the same devices again.

## 2. More ways to route audio

Loopback captures audio played through a playback device. Select a playback device as the source with **Loopback on**, or a recording device with **Loopback off**. VB-CABLE supports both modes.

**Steam Streaming Speakers** is Steam's virtual playback device. Use it with **Loopback on** to split its audio without installing VB-CABLE.

| Your setup | Install VB-CABLE? | Loopback | Audio input source in SoundSplitter |
|---|---|---|---|
| Standard VB-CABLE setup | Yes, unless already installed | Off | `CABLE Output` |
| Steam Streaming Speakers with loopback | No | On | `Steam Streaming Speakers` |
| Loopback without Steam Streaming Speakers | VB-CABLE is recommended | On | `CABLE Input` |

These are alternative configurations, not steps to repeat on a working setup. Stop splitting only when you want to change a running setup's source or Loopback mode; make the change, then start again. Configure a stopped setup directly.

### Use Steam Streaming Speakers without VB-CABLE

1. Set the Windows sound output, or your player's output, to **Steam Streaming Speakers**.
2. In SoundSplitter, enable **Loopback** and select **Steam Streaming Speakers** as the audio input source.
3. Select your two physical speakers as the left and right outputs.
4. Click **Start Splitting** and play audio.

VB-CABLE is not required for this loopback route.

### Use VB-CABLE in Loopback mode

VB-CABLE is recommended when you do not have Steam Streaming Speakers, including for loopback use. Send Windows or application audio to **CABLE Input**, enable **Loopback**, and select **CABLE Input** as the source. Select your physical speakers as the left and right outputs, then start splitting.

```text
Windows / App -> CABLE Input [Loopback] -> SoundSplitter -> L + R
```

With Loopback **off**, select **CABLE Output** as the VB-CABLE source. With Loopback **on**, select **CABLE Input**. Select the source after changing the mode, because the source list changes between recording and playback devices.

## 3. Fine-tune your setup

To change the source, output devices, Loopback mode, volume-monitoring setup, or channel latency while splitting, click **Stop Splitting**, make your changes, then click **Start Splitting**. When not splitting, configure these controls directly. The output volume sliders and mute buttons work while splitting.

### Split only one application's audio

Use that application's output selector or the Windows volume mixer to send it to **CABLE Input** or **Steam Streaming Speakers**, matching your SoundSplitter route. Leave other applications on their normal playback device. Changing only an application's output this way does not require stopping SoundSplitter.

SoundSplitter captures the selected audio endpoint, not an individual process. If multiple applications play through that endpoint, their audio is split together.

### Balance volume and mute

- The left and right volume sliders and speaker buttons control each selected output device's Windows volume and mute state, not just SoundSplitter's audio.
- In the standard VB-CABLE setup, **Volume Monitoring** is enabled automatically for **CABLE Input**, so the split audio follows that device's volume and mute state.
- For another non-loopback input, enable **Volume Monitoring** and choose the corresponding playback device beside it if you want to follow that device's volume. Disable it if you do not want that tracking.
- In Loopback mode, the separate **Volume Monitoring** controls are locked and cannot be changed independently.

### Align speakers with different delays

Use **Left channel latency (ms)** and **Right channel latency (ms)** to add delay to the faster side. Both default to `0`.

For example, if the right speaker sounds about `100` ms later than the left, set the left latency to `100` and keep the right at `0`. Restart splitting and listen again; adjust in small steps.

Compensating for the fixed delay difference keeps playback from the two devices synchronized.

### Language, startup, and the system tray

- Use the language selector to switch between the available interface languages; the selection is saved.
- Enable **Launch at Startup** to start SoundSplitter in the system tray when you sign in to Windows.
- Minimize the window or choose **Hide to Tray** to keep splitting in the background. Click the tray icon to show the window again.
- Closing the window asks whether to exit; it is not the same as hiding it. You can also choose **Exit** from the tray menu.
- Only one instance runs at a time. If SoundSplitter is already running, check the system tray before starting another copy.

## 4. Troubleshooting

| Problem | What to check |
|---|---|
| No sound | Confirm that audio is playing into the virtual playback device, that the selected source matches the Loopback mode, and that both physical outputs are selected and unmuted. Check the monitored device's volume too if Volume Monitoring is enabled. |
| Only one side plays | Check both output selections, volumes, and mute buttons. Try audio with content in both stereo channels. |
| A device is missing | Make sure Windows recognizes and enables it. Click **Refresh Output Devices** for the output lists, or reopen the input-source menu to refresh its devices. |
| Steam Streaming Speakers is missing | Use the recommended VB-CABLE setup. It supports both standard capture and Loopback mode. |
| The installer says VB-CABLE is not detected | Install VB-CABLE for the VB-CABLE route. The Steam Streaming Speakers loopback route does not need it. |
| Echo or feedback | Use a virtual playback device as the source, not either physical output that SoundSplitter is writing to. Keep the left and right outputs on the actual speakers. |
| One speaker plays later than the other | Stop splitting, add channel latency to the faster side to compensate for the delay difference, then start splitting again. |

## 5. Stop using SoundSplitter or uninstall it

1. Click **Stop Splitting** when you no longer want to split audio.
2. Change the Windows or application's output back to a normal playback device. Stopping SoundSplitter does **not** switch Windows away from the virtual device for you.
3. To remove the application, uninstall **SoundSplitter** from Windows **Settings > Apps > Installed apps**. In the uninstaller, check **Keep user data** to preserve settings for a later installation, or leave it unchecked to remove them.

Some temporary uninstaller files are scheduled for removal when Windows next starts. Uninstalling SoundSplitter does not uninstall VB-CABLE or Steam's audio devices.

## 6. Build from source

On Windows, install Python 3.14+ and [uv](https://docs.astral.sh/uv/). Run these commands from the repository root to install dependencies, generate the UI/resources and translations, and build the installer:

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

uv run nuitka --onefile --onefile-no-dll --follow-imports --output-dir=build --enable-plugin=pyside6 --noinclude-custom-mode=pydantic.v1:bytecode --include-module=av._cyutil --windows-console-mode=hide --windows-icon-from-ico=resources\icon.ico --include-windows-runtime-dlls=no --no-prefer-source-code --project-name=SoundSplitter --output-filename=setup.exe --user-package-configuration-file=nuitka.yml --include-data-dir=./translations=translations --include-data-files=.venv\Lib\site-packages\PySide6\translations\qtbase_*.qm=PySide6/translations/ --noinclude-data-files=**/*.ts src\launcher.py
```

The resulting installer is `build\setup.exe`. The launcher runs the application when named `SoundSplitter.exe`, runs the uninstaller when named `uninstall.exe`, and opens the installer for all other names. You can rename the release installer, for example to `SoundSplitter-v2.0.0b1-amd64.exe`.

Generated UI/resource modules and compiled translations are ignored by Git, so regenerate them before building from a fresh checkout.
