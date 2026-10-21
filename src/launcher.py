from pathlib import Path

if Path(globals()["__compiled__"].original_argv0).stem.casefold() == "uninstall":
    from uninstall import main
elif Path(globals()["__compiled__"].python_runtime_dir).samefile(
    other_path=globals()["__compiled__"].containing_dir
):
    from SoundSplitter import main
else:
    from setup import main

main()
