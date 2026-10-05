import wx

from .single_instance import ACTION_FOCUS, ACTION_OPEN, SingleInstanceServer


def _load_quick_player_request(paths):
    """Return ``(settings, media_paths)``; no media paths means the full player opens."""
    if not paths:
        return None, []

    from .preferences import load_settings
    from .quick_player import quick_player_paths

    settings = load_settings()
    return settings, quick_player_paths(paths, settings)


def main(initial_paths=None):
    initial_paths = list(initial_paths or [])
    app = wx.App(False)
    # The window that answers launches forwarded by other instances: the quick
    # player first, then the full player if the user continues into it.
    current = {"frame": None}

    def open_full_player(paths, *, new_playlist=False, adopted_playback=None):
        from .frames import MediaPlayerFrame

        frame = MediaPlayerFrame(
            # An adopted playback already carries its own paths.
            initial_paths=[] if adopted_playback is not None else paths,
            initial_paths_in_new_playlist=new_playlist,
            adopted_playback=adopted_playback,
        )
        current["frame"] = frame
        app.SetTopWindow(frame)

    def open_quick_player(settings, paths):
        from .log import setup_logging
        from .quick_player.frame import QuickPlayerFrame

        setup_logging(settings.logging_enabled, settings.logging_level)
        frame = QuickPlayerFrame(paths, settings=settings, on_continue=open_full_player)
        current["frame"] = frame
        app.SetTopWindow(frame)

    def _deliver_message(message):
        frame = current["frame"]
        if not frame:
            return
        action = message.get("action")
        if action == ACTION_OPEN:
            frame.receive_external_files(message.get("paths") or [])
        elif action == ACTION_FOCUS:
            frame.focus_from_relaunch()

    def _on_message(message):
        wx.CallAfter(_deliver_message, message)

    settings, quick_paths = _load_quick_player_request(initial_paths)
    if quick_paths:
        open_quick_player(settings, quick_paths)
    else:
        open_full_player(initial_paths)

    ipc_server = SingleInstanceServer(_on_message)

    app.MainLoop()

    ipc_server.shutdown()
