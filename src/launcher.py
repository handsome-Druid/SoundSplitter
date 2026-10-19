from pathlib import Path

match Path(globals()["__compiled__"].original_argv0).stem.casefold():
    case "soundsplitter":
        from SoundSplitter import main
    case "uninstall":
        from uninstall import main
    case _:
        from setup import main

main()
