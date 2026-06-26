import wx

from .single_instance import ACTION_FOCUS, ACTION_OPEN, SingleInstanceServer


def main(initial_paths=None):
    from .frames import MediaPlayerFrame

    app = wx.App(False)
    frame = MediaPlayerFrame(initial_paths=initial_paths or [])

    def _on_message(message):
        action = message.get("action")
        if action == ACTION_OPEN:
            wx.CallAfter(frame.receive_external_files, message.get("paths") or [])
        elif action == ACTION_FOCUS:
            wx.CallAfter(frame.focus_from_relaunch)

    ipc_server = SingleInstanceServer(_on_message)

    app.SetTopWindow(frame)
    app.MainLoop()

    ipc_server.shutdown()
