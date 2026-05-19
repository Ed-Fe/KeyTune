import os

import wx

from ..constants import PLAYLIST_WILDCARD, SUPPORTED_MEDIA_EXTENSIONS
from .playlist_io import is_playlist_source, is_remote_media_path


OPEN_MODE_PLAYLIST = "playlist"
OPEN_MODE_FOLDER_BROWSER = "folder_browser"
OPEN_SOURCE_DIALOG_TITLE = "Abrir mídia, playlist ou pasta"


def build_supported_media_wildcard(include_playlists=False):
    media_pattern = ";".join(f"*{extension}" for extension in sorted(SUPPORTED_MEDIA_EXTENSIONS))
    if not include_playlists:
        return "Mídia suportada|" + media_pattern + "|Todos os arquivos|*.*"

    return (
        "Playlists e mídias suportadas|*.m3u;*.m3u8;"
        + media_pattern
        + "|"
        + PLAYLIST_WILDCARD
        + "|Mídia suportada|"
        + media_pattern
        + "|Todos os arquivos|*.*"
    )


class OpenSourceDialog(wx.Dialog):
    def __init__(self, parent, default_dir="", initial_source="", initial_mode=OPEN_MODE_PLAYLIST):
        super().__init__(
            parent,
            title=OPEN_SOURCE_DIALOG_TITLE,
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._default_dir = default_dir if os.path.isdir(default_dir) else ""
        self._mode_options = [
            ("Playlist", OPEN_MODE_PLAYLIST),
            ("Navegador de pasta", OPEN_MODE_FOLDER_BROWSER),
        ]

        root_sizer = wx.BoxSizer(wx.VERTICAL)

        description = wx.StaticText(
            self,
            label=(
                "Informe um arquivo, uma pasta local, um link de mídia ou um arquivo/link .m3u/.m3u8. "
                "Pastas podem abrir como playlist ou no navegador."
            ),
        )
        description.Wrap(420)

        source_label = wx.StaticText(self, label="Arquivo, pasta ou link")
        self.source_text = wx.TextCtrl(self, value=str(initial_source or ""), style=wx.TE_PROCESS_ENTER)
        self.source_text.SetName("Caminho ou link")
        self.source_text.SetHelpText(
            "Informe um arquivo existente, uma playlist .m3u/.m3u8, uma pasta local ou um link de mídia."
        )

        browse_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self.browse_file_button = wx.Button(self, label="Ar&quivo...")
        self.browse_folder_button = wx.Button(self, label="&Pasta...")
        self.browse_file_button.SetHelpText("Escolhe um arquivo de mídia ou playlist.")
        self.browse_folder_button.SetHelpText("Escolhe uma pasta local.")
        browse_sizer.Add(self.browse_file_button, 0, wx.RIGHT, 8)
        browse_sizer.Add(self.browse_folder_button, 0)

        mode_label = wx.StaticText(self, label="Abrir como")
        self.mode_choice = wx.Choice(self, choices=[label for label, _value in self._mode_options])
        self.mode_choice.SetName("Modo de abertura")
        self.mode_choice.SetHelpText(
            "Escolhe se a origem será aberta como playlist ou como navegador de pasta."
        )

        mode_index = 0
        for index, (_label, value) in enumerate(self._mode_options):
            if value == initial_mode:
                mode_index = index
                break
        self.mode_choice.SetSelection(mode_index)

        self.status_label = wx.StaticText(self, label="")
        self.status_label.Wrap(420)
        self.status_label.SetForegroundColour(wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT))

        button_sizer = self.CreateStdDialogButtonSizer(wx.OK | wx.CANCEL)
        if button_sizer is not None:
            ok_button = self.FindWindow(wx.ID_OK)
            if ok_button is not None:
                ok_button.SetLabel("&Abrir")
            cancel_button = self.FindWindow(wx.ID_CANCEL)
            if cancel_button is not None:
                cancel_button.SetLabel("&Cancelar")

        root_sizer.Add(description, 0, wx.ALL | wx.EXPAND, 12)
        root_sizer.Add(source_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.source_text, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(browse_sizer, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(mode_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 12)
        root_sizer.Add(self.mode_choice, 0, wx.LEFT | wx.RIGHT | wx.TOP | wx.EXPAND, 12)
        root_sizer.Add(self.status_label, 0, wx.ALL | wx.EXPAND, 12)
        if button_sizer is not None:
            root_sizer.Add(button_sizer, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.ALIGN_RIGHT, 12)

        self.SetSizerAndFit(root_sizer)
        self.SetMinSize((500, 260))
        self.SetEscapeId(wx.ID_CANCEL)

        self._last_announced_source_kind = None

        self.Bind(wx.EVT_BUTTON, self._on_confirm, id=wx.ID_OK)
        self.source_text.Bind(wx.EVT_TEXT, self._on_source_changed)
        self.source_text.Bind(wx.EVT_TEXT_ENTER, self._on_confirm)
        self.mode_choice.Bind(wx.EVT_CHOICE, self._on_mode_changed)
        self.browse_file_button.Bind(wx.EVT_BUTTON, self._on_browse_file)
        self.browse_folder_button.Bind(wx.EVT_BUTTON, self._on_browse_folder)

        self._refresh_state()
        self.source_text.SetFocus()
        self.source_text.SetInsertionPointEnd()

    def get_source(self):
        return str(self.source_text.GetValue() or "").strip()

    def get_open_mode(self):
        selection = self.mode_choice.GetSelection()
        if selection == wx.NOT_FOUND:
            return OPEN_MODE_PLAYLIST
        return self._mode_options[selection][1]

    def _on_source_changed(self, _event):
        self._refresh_state()

    def _on_mode_changed(self, _event):
        self._refresh_state()

    def _on_confirm(self, event):
        if not self.get_source():
            wx.MessageBox(
                "Informe um caminho local, uma pasta ou um link de mídia.",
                OPEN_SOURCE_DIALOG_TITLE,
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            self.source_text.SetFocus()
            return

        event.Skip()

    def _on_browse_file(self, _event):
        source = self.get_source()
        default_dir = self._browse_default_directory(source)
        wildcard = self._source_file_wildcard()
        with wx.FileDialog(
            self,
            "Escolha um arquivo de mídia ou playlist",
            defaultDir=default_dir,
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            self.source_text.SetValue(dialog.GetPath())
            self.mode_choice.SetSelection(0)

    def _on_browse_folder(self, _event):
        source = self.get_source()
        default_dir = self._browse_default_directory(source)
        with wx.DirDialog(
            self,
            "Escolha uma pasta",
            defaultPath=default_dir,
            style=wx.DD_DEFAULT_STYLE | wx.DD_DIR_MUST_EXIST,
        ) as dialog:
            if dialog.ShowModal() == wx.ID_CANCEL:
                return
            self.source_text.SetValue(dialog.GetPath())

    def _browse_default_directory(self, source):
        normalized_source = str(source or "").strip()
        if normalized_source and not is_remote_media_path(normalized_source):
            if os.path.isdir(normalized_source):
                return normalized_source
            if os.path.isfile(normalized_source):
                return os.path.dirname(normalized_source)

        return self._default_dir

    def _source_file_wildcard(self):
        return build_supported_media_wildcard(include_playlists=True)

    def _detect_source_kind(self, source):
        normalized_source = str(source or "").strip()
        if not normalized_source:
            return "empty"

        if os.path.isdir(normalized_source):
            return "folder"

        if is_playlist_source(normalized_source):
            return "playlist"

        if os.path.isfile(normalized_source):
            return "media"

        if is_remote_media_path(normalized_source):
            return "remote"

        return "unknown"

    def _refresh_state(self):
        source_kind = self._detect_source_kind(self.get_source())
        allow_folder_mode = source_kind in {"folder", "empty", "unknown"}

        if allow_folder_mode:
            self.mode_choice.Enable(True)
        else:
            self.mode_choice.SetSelection(0)
            self.mode_choice.Enable(False)

        status_message = {
            "empty": "Pastas podem abrir como playlist ou no navegador. Arquivos, links e playlists podem abrir para reprodução.",
            "folder": "Esta pasta pode abrir como playlist estática ou no navegador de pastas.",
            "playlist": "Arquivos e links .m3u/.m3u8 são abertos como playlist.",
            "media": "Arquivos de mídia são abertos como playlist com um item.",
            "file": "Arquivos existentes serão tentados como mídia.",
            "remote": "Links remotos serão tentados como mídia, exceto quando forem playlists .m3u/.m3u8.",
            "unknown": "Se o caminho for uma pasta local, você pode escolher playlist ou navegador. Arquivos e links serão tentados como mídia.",
        }.get(source_kind, "")
        self.status_label.SetLabel(status_message)
        self.status_label.Wrap(max(320, self.GetClientSize().Width - 24))
        self.Layout()

        if status_message and source_kind != self._last_announced_source_kind:
            self._last_announced_source_kind = source_kind
            parent = self.GetParent()
            announce = getattr(parent, "_announce", None)
            if callable(announce):
                announce(status_message)
