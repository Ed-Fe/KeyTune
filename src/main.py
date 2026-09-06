import os
import sys

from player.mpv_runtime import bootstrap_mpv_runtime


_SMTC_SMOKE_TEST_ARGUMENT = "--smtc-smoke-test"
_YOUTUBE_DEPENDENCIES_SMOKE_TEST_ARGUMENT = "--youtube-dependencies-smoke-test"
_AUTODJ_ANALYZER_ARGUMENT = "--autodj-analyzer"
_PLUGIN_WORKER_ARGUMENT = "--plugin-worker"


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


def _run_smtc_smoke_test():
    from player.smtc import SmtcService

    service = SmtcService()
    if not service.start():
        return 1
    service.stop()
    return 0


def _run_youtube_dependencies_smoke_test():
    from player.youtube_music.dependencies import import_ytmusicapi_module

    import_ytmusicapi_module()
    return 0


def main():
    if _AUTODJ_ANALYZER_ARGUMENT in sys.argv[1:]:
        from player.autodj.dependencies import activate_autodj_dependencies
        from player.autodj.worker import main as worker_main

        activate_autodj_dependencies()
        argument_index = sys.argv.index(_AUTODJ_ANALYZER_ARGUMENT)
        return worker_main(sys.argv[argument_index + 1:])
    if _PLUGIN_WORKER_ARGUMENT in sys.argv[1:]:
        from player.plugins.worker import main as worker_main

        worker_main()
        return 0
    if _SMTC_SMOKE_TEST_ARGUMENT in sys.argv[1:]:
        return _run_smtc_smoke_test()
    if _YOUTUBE_DEPENDENCIES_SMOKE_TEST_ARGUMENT in sys.argv[1:]:
        return _run_youtube_dependencies_smoke_test()

    bootstrap_mpv_runtime()

    _setup_language()

    initial_paths = _collect_initial_paths()

    from player.single_instance import try_send_to_existing_instance

    # Single instance: forward this launch to a running KeyTune (files to play,
    # or a focus request for a bare launch) and exit. Only start a new instance
    # when none is already running.
    if try_send_to_existing_instance(initial_paths):
        return 0

    from player.app import main as app_main

    app_main(initial_paths=initial_paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
