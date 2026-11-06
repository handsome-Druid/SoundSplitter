from pathlib import Path

if Path(globals()["__compiled__"].original_argv0).stem.casefold() == "uninstall":
    from uninstall import main
elif (
    globals()["__compiled__"].containing_dir
    == globals()["__compiled__"].python_runtime_dir
):
    from SoundSplitter import main
else:
    from setup import main

main()
