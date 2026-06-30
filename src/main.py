import os
import sys

from player.mpv_runtime import bootstrap_mpv_runtime


def _normalize_launch_path(path):
    normalized_path = str(path or "").strip().strip('"')
    if not normalized_path:
        return ""
    return os.path.normcase(os.path.abspath(normalized_path))


def _collect_initial_paths(argv=None, *, launch_targets=None):
    raw_paths = list(sys.argv[1:] if argv is None else argv)
    normalized_launch_targets = {
        normalized_target
        for normalized_target in (
            _normalize_launch_path(target)
            for target in (launch_targets or (sys.executable, sys.argv[0]))
        )
        if normalized_target
    }

    initial_paths = []
    for path in raw_paths:
        normalized_path = _normalize_launch_path(path)
        if not normalized_path or normalized_path in normalized_launch_targets:
            continue
        initial_paths.append(path)

    return initial_paths


def _read_saved_language():
    # Read just the language key straight from the settings JSON, without
    # importing the preferences/constants modules. Those modules build several
    # module-level label dictionaries through ``_()``, so the active language has
    # to be set *before* they are imported for the labels to be translated.
    try:
        import json

        from player.session import get_app_storage_dir

        settings_path = os.path.join(get_app_storage_dir(), "settings.json")
        with open(settings_path, "r", encoding="utf-8") as settings_file:
            payload = json.load(settings_file)
        if isinstance(payload, dict):
            return str(payload.get("language") or "")
    except Exception:
        pass
    return ""


def _setup_language():
    # Activate the saved interface language (or auto-detect) before any UI module
    # is imported, so every string built at import/construction time is already
    # translated.
    from player.i18n import setup_translation

    setup_translation(_read_saved_language())


def main():
    bootstrap_mpv_runtime()

    _setup_language()

    initial_paths = _collect_initial_paths()

    from player.single_instance import try_send_to_existing_instance

    # Single instance: forward this launch to a running KeyTune (files to play,
    # or a focus request for a bare launch) and exit. Only start a new instance
    # when none is already running.
    if try_send_to_existing_instance(initial_paths):
        return

    from player.app import main as app_main

    app_main(initial_paths=initial_paths)


if __name__ == "__main__":
    main()
