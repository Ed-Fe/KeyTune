import os
import sys

from player.mpv_runtime import bootstrap_mpv_runtime


_SMTC_SMOKE_TEST_ARGUMENT = "--smtc-smoke-test"
_YOUTUBE_DEPENDENCIES_SMOKE_TEST_ARGUMENT = "--youtube-dependencies-smoke-test"
_YOUTUBEJS_DEPENDENCIES_SMOKE_TEST_ARGUMENT = "--youtubejs-dependencies-smoke-test"
_AUTODJ_ANALYZER_ARGUMENT = "--autodj-analyzer"
_PLUGIN_WORKER_ARGUMENT = "--plugin-worker"
_ENQUEUE_ARGUMENT = "--enqueue"


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
        if str(path).strip() == _ENQUEUE_ARGUMENT:
            continue
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


def _run_youtubejs_dependencies_smoke_test():
    from player.youtube_music.youtubejs_runtime import validate_youtubejs_dependencies

    validate_youtubejs_dependencies()
    return 0


def _run_with_portable_storage_warning(app_main, initial_paths, warning):
    import wx

    from player.i18n import _
    from player.log import get_logger
    from player.session import get_app_storage_dir

    data_dir, error = warning

    def show_warning(window):
        local_dir = get_app_storage_dir()
        get_logger(__name__).warning(
            "Using local storage %s because %s is unwritable: %s", local_dir, data_dir, error
        )
        message = _(
            "A pasta de dados portátil {portable_path} está em modo somente leitura. "
            "Os dados ficarão neste computador, em {local_path}."
        ).format(portable_path=data_dir, local_path=local_dir)
        wx.MessageBox(message, _("Versão portátil"), wx.OK | wx.ICON_WARNING, window)

    class StartupWarning(wx.EventFilter):
        scheduled = False

        def FilterEvent(self, event):
            if not self.scheduled and isinstance(event, wx.ShowEvent) and event.IsShown():
                window = event.GetEventObject()
                if isinstance(window, wx.Frame):
                    self.scheduled = True
                    wx.CallAfter(show_warning, window)
            return wx.EventFilter.Event_Skip

    warning_filter = StartupWarning()
    wx.EvtHandler.AddFilter(warning_filter)
    try:
        app_main(initial_paths=initial_paths)
    finally:
        wx.EvtHandler.RemoveFilter(warning_filter)


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
    if _YOUTUBEJS_DEPENDENCIES_SMOKE_TEST_ARGUMENT in sys.argv[1:]:
        return _run_youtubejs_dependencies_smoke_test()

    bootstrap_mpv_runtime()

    _setup_language()

    initial_paths = _collect_initial_paths()
    # ``--enqueue`` adds to the running playlist. With no instance yet, the
    # files open normally (the flag itself is not a path).
    enqueue = _ENQUEUE_ARGUMENT in sys.argv[1:]

    from player.restart import started_by_restart
    from player.single_instance import try_send_to_existing_instance

    # Single instance: forward this launch to a running KeyTune (files to play,
    # files to enqueue, or a focus request for a bare launch) and exit. Only
    # start a new instance when none is already running. A KeyTune that reopened
    # itself skips this: the one that asked for the restart may still be winding down.
    if not started_by_restart() and try_send_to_existing_instance(initial_paths, enqueue=enqueue):
        return 0

    from player.app import main as app_main
    from player.portable import portable_storage_warning

    warning = portable_storage_warning()
    if warning is None:
        app_main(initial_paths=initial_paths)
    else:
        _run_with_portable_storage_warning(app_main, initial_paths, warning)
    return 0


if __name__ == "__main__":
    sys.exit(main())
