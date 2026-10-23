# SoundSplitter

English | [简体中文](docs/README.zh-CN.md)

Turn two separate speakers into a stereo pair: one plays the left channel, and the other plays the right. SoundSplitter keeps the output audio streams synchronized and provides independent channel delay adjustment to compensate for fixed differences in device latency.

**For Windows and Linux.** Use two different audio output devices recognized by your system. Wired, USB, and Bluetooth speakers can be used together. Keep using your music player, browser, or game as usual.

> [!IMPORTANT]
> **Before starting SoundSplitter, check for audio devices with duplicate names in your system.** SoundSplitter identifies devices by name rather than device ID. Duplicate names may cause unexpected errors. Rename any duplicates in your system settings so each device has a unique name before launching the application. Naming the two output devices **Left channel output** and **Right channel output** makes them easier to identify.

## 1. Download and install

Choose the package for your system from [Releases](https://github.com/handsome-Druid/SoundSplitter/releases):

| System | Package |
|---|---|
| Windows x64 | `.exe` installer |
| Debian / Ubuntu x64 | `.deb` |
| RPM-based Linux x64 | `.rpm` |

**Windows:** run the installer and approve its administrator prompt. After installation, open SoundSplitter as a normal user.

**Linux:** install the package with your system's software installer or package manager, then open **SoundSplitter** from the application menu.

## 2. Start playing

Connect both speakers and confirm that your system recognizes them as separate playback devices. The left and right outputs must be **different physical devices**, not the virtual device used for input.

Follow these steps for first-time setup.

### Linux

1. Open SoundSplitter. It automatically creates and selects **CABLE Input (SoundSplitter)** as its input source.
2. Select two physical speakers under **Select left channel output** and **Select right channel output**.
3. Click **Start Splitting**.
4. Set your system or player's output to **CABLE Input (SoundSplitter)** and play audio.

This virtual playback device is available only while SoundSplitter is running.

### Windows

Choose one input setup:

| Setup | System or player output | SoundSplitter input source | Loopback |
|---|---|---|---|
| VB-CABLE (install [VB-CABLE](https://vb-audio.com/Cable/) first) | CABLE Input | CABLE Output | Off |
| VB-CABLE loopback | CABLE Input | CABLE Input | On |
| Existing Steam Streaming Speakers | Steam Streaming Speakers | Steam Streaming Speakers | On |

1. Open SoundSplitter. The standard VB-CABLE input is selected automatically. For other setups, set **Loopback** as shown in the table, then select the input source.
2. Select two physical speakers under **Select left channel output** and **Select right channel output**.
3. Click **Start Splitting**.
4. Set your system or player's output to the corresponding device in the table and play audio.

### Next time

Settings are saved automatically. On subsequent launches, SoundSplitter restores your configuration and attempts to start splitting automatically. You do not need to repeat the initial setup.

## 3. Fine-tune your setup

Stop splitting before changing devices, the input setup, or channel delays, then start again. Volume and mute controls work during playback.

### Split only one application's audio

Use the application's output selector or your system's per-application sound settings to choose:

- **Linux:** CABLE Input (SoundSplitter).
- **Windows:** CABLE Input or Steam Streaming Speakers, matching your setup.

Leave other applications on their normal playback device. Applications sent to the same virtual device are split together.

### Balance volume and mute

- The left and right volume sliders and speaker buttons control each selected output device's system volume and mute state, not just SoundSplitter's audio.
- **Linux:** split audio follows the volume and mute state of **CABLE Input (SoundSplitter)**.
- **Windows:** in the standard VB-CABLE setup, **Volume Monitoring** is enabled automatically for **CABLE Input**. For another non-loopback input, enable it and choose the playback device whose volume you want to follow.

### Align speakers with different delays

If one speaker plays later than the other, stop splitting and increase **Left channel latency (ms)** or **Right channel latency (ms)** on the **faster side** by the difference you hear. Keep the slower side's value unchanged, then restart splitting and listen again.

For example, if the right speaker is about `100` ms late, add `100` to the current left-channel latency, then fine-tune in small steps.

### Language, startup, and the system tray

- Use the language selector to switch between the available interface languages; the selection is saved.
- Enable **Launch at Startup** to start SoundSplitter in the background when you sign in.
- Minimize the window or choose **Hide to Tray** to keep splitting in the background. Click the tray icon to show the window again. If your desktop has no system tray, the window stays minimized instead.
- Closing the window asks whether to exit; it is not the same as hiding it. You can also choose **Exit** from the tray menu.
- Opening SoundSplitter again brings the existing window back rather than running a second copy.

## 4. Troubleshooting

### No sound

Set your system or player's output to the virtual device in your setup above, and unmute both the virtual device and the speakers.

### Only one side plays

Unmute the silent side, raise its volume, and try audio with content in both stereo channels.

### A speaker is missing

Make sure your system recognizes and enables it. Click **Refresh Output Devices** in SoundSplitter.

### Echo or feedback

Use the virtual device from the input setup table as the source and physical speakers as the outputs to avoid capturing the split audio again.

### One speaker plays later than the other

Stop splitting, add channel latency to the faster side to compensate for the delay difference, then start splitting again.

### High latency with a virtual audio cable on Windows

When using a virtual audio cable such as VB-CABLE without Loopback, try switching to Loopback mode. With VB-CABLE, you can also reduce the buffer sample count in `VBCABLE_ControlPanel.exe`.

### Minimizing quality loss from resampling

Resampling can occur at any stage of the audio chain. Set capture and playback devices to the same sample rate and bit depth wherever possible. With VB-CABLE, also match the sample rates of **CABLE Input**, **CABLE Output**, and the internal sample rate in `VBCABLE_ControlPanel.exe`.

### Latency, buffering, and audio loss

- **Windows:** both channel delays default to `0 ms`. The application maintains a minimum usable buffer internally.
- **Linux:** both channel delays default to `30 ms`. Lower values reduce latency, but the application cannot guarantee a minimum usable buffer.

On either system, check the log file for audio loss. Increasing both channel delays manually enlarges the buffers and can help reduce audio loss.

Log locations:

- **Windows:** `%ProgramData%\SoundSplitter\logs\SoundSplitter.log`
- **Linux:** `/var/lib/SoundSplitter/logs/SoundSplitter.log`

### Linux shows only one endpoint for multiple outputs on the same graphics card

In **PulseAudio Volume Control (pavucontrol)**, open **Configuration** and set the graphics card's audio profile to **Pro Audio** to expose all endpoints. Avoid manually configuring the speakers through the system sound settings.

## 5. Stop using SoundSplitter or uninstall it

Change your system or application's output back to a physical playback device, then stop splitting or exit SoundSplitter. This lets you keep listening without SoundSplitter.

- **Windows:** uninstall **SoundSplitter** from **Settings > Apps > Installed apps**. Check **Keep user data** in the uninstaller if you want to retain your settings. VB-CABLE and Steam's audio devices are not removed.
- **Linux:** remove **SoundSplitter** with your system's software installer or package manager.
