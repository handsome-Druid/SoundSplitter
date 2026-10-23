#!/usr/bin/env python
from os import chdir, environ, pathsep
from pathlib import Path
from re import sub
from shutil import which
from subprocess import run
from sys import argv, exit, platform
from xml.etree.ElementTree import parse

chdir(path=Path(__file__).parent)
if "--deps" in argv:
    if platform == "linux":
        if which(cmd="apt") is not None:
            run(args=("sudo", "apt", "update"), check=True)
            run(
                args=(
                    "sudo",
                    "apt",
                    "install",
                    "build-essential",
                    "ccache",
                    "portaudio19-dev",
                    "python3-dev",
                    "curl",
                    "patchelf",
                    "dpkg-dev",
                    "devscripts",
                    "debhelper-compat=13",
                    "binutils",
                ),
                check=True,
            )
        elif which(cmd="dnf") is not None:
            environ["PATH"] = (
                str(object=(Path.home() / ".local" / "bin")) + pathsep + environ["PATH"]
            )
            run(
                args=(
                    "sudo",
                    "dnf",
                    "--refresh",
                    "install",
                    "curl",
                    "@Development Tools",
                    "ccache",
                    "portaudio-devel",
                    "python3-devel",
                    "patchelf",
                    "rpm-build",
                    "redhat-rpm-config",
                    "systemd-rpm-macros",
                    "binutils",
                ),
                check=True,
            )
        run(
            args=("bash", "-c", "curl -LsSf https://astral.sh/uv/install.sh | sh"),
            check=True,
        )
        environ["PATH"] = (
            str(object=(Path.home() / ".local" / "bin")) + pathsep + environ["PATH"]
        )
        run(args=("uv", "sync"), check=True)
    if platform == "win32":
        run(
            args=(
                "winget",
                "install",
                "--id",
                "Microsoft.VisualStudio.BuildTools",
                "--exact",
                "--override",
                (
                    "--wait --passive --norestart "
                    "--add Microsoft.VisualStudio.Workload.VCTools "
                    "--includeRecommended"
                ),
            ),
            check=True,
        )
        run(
            args=(
                "winget",
                "install",
                "--id",
                "astral-sh.uv",
                "--exact",
            ),
            check=True,
        )
    exit()
if "--distclean" in argv:
    run(args=("uvx", "pyclean", ".", "--debris", "all"), check=True)
    for path in Path("src").rglob(pattern="*"):
        if path.name.endswith(("_ui.py", "_rc.py")):
            path.unlink()
    for path in Path("translations").rglob(pattern="*.qm"):
        path.unlink()
    exit()
if "--clean" in argv:
    run(args=("uvx", "pyclean", "."), check=True)
    exit()
run(args=("uv", "sync"), check=True)
src: list[Path] = []
for path in Path("src").rglob(pattern="*"):
    if path.is_file():
        match path.suffix:
            case ".ui":
                output: Path = path.with_name(name=path.stem + "_ui.py")
                if output.exists() and output.stat().st_mtime >= path.stat().st_mtime:
                    continue
                run(
                    args=(
                        "uv",
                        "run",
                        "pyside6-uic",
                        str(object=path),
                        "-o",
                        str(object=output),
                    ),
                    check=True,
                )
                src.append(output)
            case ".qrc":
                output: Path = path.with_name(name=path.stem + "_rc.py")
                if (
                    output.exists()
                    and output.stat().st_mtime >= path.stat().st_mtime
                    and all(
                        (path.parent / file.text.strip()).stat().st_mtime
                        <= output.stat().st_mtime
                        for file in parse(source=path).getroot().findall(path=".//file")
                        if file.text and file.text.strip()
                    )
                ):
                    continue
                run(
                    args=(
                        "uv",
                        "run",
                        "pyside6-rcc",
                        str(object=path),
                        "-o",
                        str(object=output),
                    ),
                    check=True,
                )
                src.append(output)
            case ".py":
                src.append(path)
for path in Path("translations").rglob(pattern="*.ts"):
    if not path.is_file():
        continue
    output: Path = path.with_name(name=path.stem + ".qm")
    if output.exists() and output.stat().st_mtime >= path.stat().st_mtime:
        continue
    run(
        args=(
            "uv",
            "run",
            "pyside6-lrelease",
            str(object=path),
            "-qm",
            str(object=output),
        ),
        check=True,
    )
    src.append(output)
last_time: float = (
    Path("build/.stamp").stat().st_mtime if Path("build/.stamp").exists() else 0.0
)
if (
    Path(__file__).stat().st_mtime < last_time
    and Path("uv.lock").stat().st_mtime < last_time
    and all(path.stat().st_mtime < last_time for path in src)
    and all(
        path.stat().st_mtime < last_time
        for directory in ("debian", "rpm")
        for path in Path(directory).rglob(pattern="*")
    )
):
    exit()
if platform == "linux":
    run(
        args=(
            "uv",
            "run",
            "nuitka",
            "--standalone",
            "--follow-imports",
            "--output-dir=build",
            "--output-folder-name=SoundSplitter",
            "--output-filename=SoundSplitter.bin",
            "--enable-plugin=pyside6",
            "--noinclude-custom-mode=pydantic.v1:bytecode",
            "--noinclude-qt-plugins=egldeviceintegrations",
            "--include-module=av._cyutil",
            "--no-prefer-source-code",
            "--assume-yes-for-downloads",
            "--include-data-dir=./translations/SoundSplitter=translations/SoundSplitter",
            "--include-data-files="
            + run(
                args=(
                    "uv",
                    "run",
                    "python",
                    "-c",
                    "import PySide6, pathlib; print(pathlib.Path(PySide6.__file__).parent)",
                ),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            + "/Qt/translations/qtbase_*.qm=PySide6/translations/",
            "--noinclude-data-files=**/*.ts",
            "--python-flag=-m",
            "src/SoundSplitter",
        ),
        check=True,
    )
    version: str = run(
        args=("uvx", "hatch", "version"), capture_output=True, text=True, check=True
    ).stdout.strip()
    if which(cmd="dpkg-buildpackage") is not None:
        Path("debian/changelog.dch").unlink(missing_ok=True)
        run(
            args=(
                "dch",
                "--controlmaint",
                "--newversion",
                sub(pattern=r"(\d)([a-zA-Z])", repl=r"\1~\2", string=version) + "-1",
                "",
            ),
            check=True,
        )
        Path("debian/rules").chmod(mode=0o755)
        run(
            args=(
                "dpkg-buildpackage",
                "-b",
                "-uc",
                "-tc",
                "--buildinfo-option=-ubuild",
                "--changes-option=-ubuild",
                "--buildinfo-file=build/soundsplitter.buildinfo",
                "--changes-file=build/soundsplitter.changes",
            ),
            check=True,
        )
    elif which(cmd="rpmbuild") is not None:
        run(
            args=(
                "rpmbuild",
                "-bb",
                "--define",
                "_topdir " + str(object=Path("build/rpm").resolve()),
                "--define",
                "_rpmdir " + str(object=Path("build").resolve()),
                "--define",
                "_sourcedir " + str(object=Path.cwd()),
                "--define",
                "app_version "
                + sub(pattern=r"(\d)([a-zA-Z])", repl=r"\1~\2", string=version),
                "rpm/soundsplitter.spec",
            ),
            check=True,
        )
if platform == "win32":
    run(
        args=(
            "uv",
            "run",
            "nuitka",
            "--onefile",
            "--onefile-no-dll",
            "--follow-imports",
            "--output-dir=build",
            "--enable-plugin=pyside6",
            "--assume-yes-for-downloads",
            "--noinclude-custom-mode=pydantic.v1:bytecode",
            "--include-module=av._cyutil",
            "--windows-console-mode=hide",
            "--windows-icon-from-ico=resources/icon.ico",
            "--include-windows-runtime-dlls=no",
            "--no-prefer-source-code",
            "--project-name=SoundSplitter",
            "--output-filename=setup.exe",
            "--include-data-dir=./translations=translations",
            "--include-data-files=.venv/Lib/site-packages/PySide6/translations/qtbase_*.qm=PySide6/translations/",
            "--noinclude-data-files=**/*.ts",
            "src/launcher.py",
        ),
        check=True,
    )
Path("build/.stamp").touch()
