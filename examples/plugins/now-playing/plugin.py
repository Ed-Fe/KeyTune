"""First-party example plugin for the process-isolated API."""


class Plugin:
    def __init__(self, api):
        self.api = api

    def on_start(self):
        self.api.add_menu_action("announce-current", "Anunciar faixa atual", self.announce, submenu="Exemplos")
        starts = int(self.api.get_setting("starts", 0)) + 1
        self.api.set_setting("starts", starts)

    def announce(self):
        state = self.api.playback_state()
        self.api.notify(state.get("media_path") or "Nenhuma mídia em reprodução.")
