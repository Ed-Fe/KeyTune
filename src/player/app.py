import wx

from .single_instance import SingleInstanceServer


def main(initial_paths=None):
    from .frames import MediaPlayerFrame

    app = wx.App(False)
    frame = MediaPlayerFrame(initial_paths=initial_paths or [])

    def _on_external_paths(paths):
        wx.CallAfter(frame.receive_external_files, paths)

    ipc_server = SingleInstanceServer(_on_external_paths)

    app.SetTopWindow(frame)
    app.MainLoop()

    ipc_server.shutdown()
