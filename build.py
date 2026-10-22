#!/usr/bin/env python
from os import chdir
from pathlib import Path
from shutil import copy2, which
from subprocess import run
from sys import argv, exit, platform
from sysconfig import get_path
from xml.etree.ElementTree import parse

chdir(path=Path(__file__).parent)
if "--distclean" in argv:
    run(args=("uvx", "pyclean", ".", "--debris", "all"), check=True)
    exit()
if "--clean" in argv:
    run(args=("uvx", "pyclean", "."), check=True)
    exit()
run(args=("uv", "sync"), check=True)
src: list[Path] = []
translations: set[Path] = set()
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
    translations.add(output)
last_time: float = (
    Path("build/.stamp").stat().st_mtime if Path("build/.stamp").exists() else 0.0
)
if last_time != 0.0:
    for path in Path("build").rglob(pattern="*.qm"):
        if not path.is_file():
            continue
        if "PySide6" not in path.parts:
            source = Path(*path.parts[path.parts.index("translations") :])
            if not source.exists():
                path.unlink()
            else:
                translations.discard(source)
                if source.stat().st_mtime >= path.stat().st_mtime:
                    copy2(src=source, dst=path)
if (
    Path(__file__).stat().st_mtime < last_time
    and Path("uv.lock").stat().st_mtime < last_time
    and not translations
    and all(path.stat().st_mtime < last_time for path in src)
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
            "--include-module=av._cyutil",
            "--no-prefer-source-code",
            "--include-data-dir=./translations/SoundSplitter=translations/SoundSplitter",
            "--include-data-files="
            + get_path(name="platlib")
            + "/PySide6/translations/qtbase_*.qm=PySide6/translations/",
            "--noinclude-data-files=**/*.ts",
            "--python-flag=-m",
            "src/SoundSplitter",
        ),
        check=True,
    )
    if which(cmd="dpkg-buildpackage") is not None:
        Path("debian/rules").chmod(mode=0o755)
        run(args=("dpkg-buildpackage", "-b", "-us", "-uc"), check=True)
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
            "--noinclude-custom-mode=pydantic.v1:bytecode",
            "--include-module=av._cyutil",
            "--windows-console-mode=hide",
            "--windows-icon-from-ico=resources/icon.ico",
            "--include-windows-runtime-dlls=no",
            "--no-prefer-source-code",
            "--project-name=SoundSplitter",
            "--output-filename=setup.exe",
            "--include-data-dir=./translations=translations",
            "--include-data-files="
            + get_path(name="platlib")
            + "/PySide6/translations/qtbase_*.qm=PySide6/translations/",
            "--noinclude-data-files=**/*.ts",
            "src/launcher.py",
        ),
        check=True,
    )
Path("build/.stamp").touch()
