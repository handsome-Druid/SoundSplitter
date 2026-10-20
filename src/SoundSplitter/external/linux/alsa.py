import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Self


class ALSA:
    def __call__(self, name: str, /) -> None:
        if self._directory is None:
            self.__init__()
        directions: dict[str, str] = {}
        for kind, direction in (("sinks", "playback"), ("sources", "capture")):
            result = subprocess.run(
                ["pactl", "--format=json", "list", kind],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            for endpoint in json.loads(result.stdout):
                if endpoint["description"] == name:
                    directions[direction] = endpoint["name"]
                    if kind == "sinks":
                        directions["capture"] = endpoint["monitor_source"]
            if "playback" in directions:
                break
        if not directions:
            raise ValueError(f"Audio endpoint not found: {name!r}")

        devices = self._devices | {name: directions}
        content = [self._base]
        for description, endpoints in devices.items():
            quoted_name = json.dumps(description, ensure_ascii=False)
            content.append(f"pcm.!{quoted_name} {{\n    type asym")
            for direction, internal_name in endpoints.items():
                content.append(
                    f"    {direction}.pcm {{\n"
                    "        type pulse\n"
                    f"        device {json.dumps(internal_name, ensure_ascii=False)}\n"
                    "    }"
                )
            content.append(
                "    hint {\n"
                "        show on\n"
                f"        description {quoted_name}\n"
                "    }\n}"
            )
        temporary = self._config.with_suffix(".tmp")
        temporary.write_text("\n".join(content) + "\n", encoding="utf-8")
        temporary.replace(self._config)
        self._devices = devices

    def __init__(self) -> None:
        self._previous_config = os.environ.get("ALSA_CONFIG_PATH")
        self._directory = TemporaryDirectory(prefix="soundsplitter-alsa-")
        self._config = Path(self._directory.name) / "alsa.conf"
        self._devices: dict[str, dict[str, str]] = {}
        base = json.dumps(
            self._previous_config or "/usr/share/alsa/alsa.conf", ensure_ascii=False
        )
        self._base = f"@hooks [ {{ func load files [ {base} ] errors false }} ]\n"
        self._config.write_text(self._base, encoding="utf-8")
        os.environ["ALSA_CONFIG_PATH"] = str(self._config)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> None:
        if self._directory is None:
            return
        if self._previous_config is None:
            os.environ.pop("ALSA_CONFIG_PATH", None)
        else:
            os.environ["ALSA_CONFIG_PATH"] = self._previous_config
        self._directory.cleanup()
        self._directory = None
