"""Diálogo de conversão: formato, qualidade e pasta de destino."""

from __future__ import annotations

import os

import wx

from ..download.options import SAMPLE_RATES, sample_rate_label
from ..i18n import _
from ..widgets import add_choice_row, add_directory_row
from .options import (
    AUDIO_BITRATES,
    AUDIO_FORMAT_IDS,
    AUDIO_FORMATS,
    AUDIO_TO_VIDEO_FORMATS,
    DEFAULT_AUDIO_BITRATE,
    DEFAULT_AUDIO_FORMAT,
    DEFAULT_VIDEO_FORMAT,
    DEFAULT_VIDEO_HEIGHT,
    MODE_AUDIO_TO_VIDEO,
    MODE_VIDEO_TO_VIDEO,
    MODE_TARGET_KIND,
    KIND_AUDIO,
    VIDEO_CONTAINER_FORMATS,
    VIDEO_HEIGHTS,
    audio_format_label,
    bitrate_label,
    mode_label,
    video_format_label,
    video_height_label,
)
from .plan import ConvertRequest


def target_formats_for(mode: str, source_path: str, *, exclude_source: bool = True):
    """Formatos de destino oferecidos para *mode*."""
    if MODE_TARGET_KIND[mode] == KIND_AUDIO:
        return AUDIO_FORMAT_IDS
    if mode == MODE_AUDIO_TO_VIDEO:
        return AUDIO_TO_VIDEO_FORMATS
    if not exclude_source:
        return VIDEO_CONTAINER_FORMATS
    # Trocar só o contêiner: o formato de origem não é um destino útil.
    source_extension = os.path.splitext(source_path)[1].lstrip(".").lower()
    formats = tuple(item for item in VIDEO_CONTAINER_FORMATS if item != source_extension)
    return formats or VIDEO_CONTAINER_FORMATS


class ConvertDialog(wx.Dialog):
    def __init__(self, parent, mode, source_path, *, other_directory="", item_count=1, settings=None):
        super().__init__(
            parent,
            title=_("Converter mídia"),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._mode = mode
        # Preferências com a última escolha de cada opção; sem elas valem os padrões.
        self._settings = settings
        self._source_path = str(source_path)
        self._item_count = max(1, int(item_count))
        # Numa fila, os arquivos com o mesmo formato do destino são simplesmente pulados.
        self._target_formats = target_formats_for(mode, self._source_path, exclude_source=self._item_count == 1)
        self._audio_target = MODE_TARGET_KIND[mode] == KIND_AUDIO

        panel = wx.Panel(self)
        root_sizer = wx.BoxSizer(wx.VERTICAL)
        options_sizer = wx.BoxSizer(wx.VERTICAL)

        if self._item_count > 1:
            intro = _("{mode}: {count} arquivos").format(
                mode=mode_label(mode), count=self._item_count
            )
        else:
            intro = _("{mode}: “{name}”").format(
                mode=mode_label(mode), name=os.path.basename(self._source_path)
            )
        intro_label = wx.StaticText(panel, label=intro)
        intro_label.Wrap(520)
        root_sizer.Add(intro_label, 0, wx.ALL | wx.EXPAND, 10)

        labels = [
            audio_format_label(item) if self._audio_target else video_format_label(item)
            for item in self._target_formats
        ]
        self.format_choice = add_choice_row(
            panel,
            options_sizer,
            _("Formato de destino"),
            self._format_help_text(),
            labels,
        )
        self.format_choice.SetSelection(self._default_format_index())

        self.bitrate_choice = None
        self.sample_rate_choice = None
        self.height_choice = None
        self.cover_checkbox = None

        if self._audio_target:
            self.bitrate_choice = add_choice_row(
                panel,
                options_sizer,
                _("Qualidade do áudio"),
                _("Taxa de bits dos formatos com perdas (MP3, M4A, OGG e Opus). FLAC e WAV não usam esta opção."),
                [bitrate_label(bitrate) for bitrate in AUDIO_BITRATES],
            )
            self.bitrate_choice.SetSelection(
                self._remembered_index("convert_audio_bitrate", AUDIO_BITRATES, DEFAULT_AUDIO_BITRATE)
            )
            self.sample_rate_choice = add_choice_row(
                panel,
                options_sizer,
                _("Taxa de amostragem do áudio"),
                _("Original mantém a taxa do arquivo. O Opus sempre usa 48000 Hz."),
                [sample_rate_label(rate) for rate in SAMPLE_RATES],
            )
            self.sample_rate_choice.SetSelection(self._remembered_index("convert_sample_rate", SAMPLE_RATES, 0))
        elif self._mode == MODE_AUDIO_TO_VIDEO:
            self.height_choice = add_choice_row(
                panel,
                options_sizer,
                _("Resolução do vídeo"),
                _("Tamanho do quadro do vídeo gerado. Resoluções maiores geram arquivos maiores."),
                [video_height_label(height) for height in VIDEO_HEIGHTS],
            )
            self.height_choice.SetSelection(
                self._remembered_index("convert_video_height", VIDEO_HEIGHTS, DEFAULT_VIDEO_HEIGHT)
            )
            self.cover_checkbox = wx.CheckBox(panel, label=_("&Usar a capa do álbum como imagem, se houver"))
            self.cover_checkbox.SetName(_("Usar a capa do álbum como imagem"))
            self.cover_checkbox.SetToolTip(
                _("Marcado, o vídeo mostra a capa embutida no áudio. Sem capa, ou desmarcado, o fundo é preto.")
            )
            self.cover_checkbox.SetValue(bool(self._remembered("convert_use_cover", True)))
            options_sizer.Add(self.cover_checkbox, 0, wx.ALL | wx.EXPAND, 6)

        self.destination_choice = add_choice_row(
            panel,
            options_sizer,
            _("Salvar em"),
            _(
                "Mesma pasta do arquivo original ou outra pasta à sua escolha. "
                "O arquivo original nunca é alterado."
            ),
            [_("Mesma pasta do arquivo original"), _("Outra pasta")],
        )
        self.directory_ctrl = add_directory_row(
            panel,
            options_sizer,
            _("Outra pasta"),
            _("Pasta onde o arquivo convertido será salvo. Só vale com a opção Outra pasta."),
            _("Escolha a pasta de destino"),
            _("Escolher pasta de destino"),
        )
        self.directory_ctrl.SetValue(str(other_directory or "").strip())
        # «Outra pasta» só volta selecionada se houver uma pasta lembrada para usar.
        other_folder = not self._remembered("convert_same_folder", True) and bool(self.directory_ctrl.GetValue())
        self.destination_choice.SetSelection(1 if other_folder else 0)
        self.destination_choice.Bind(wx.EVT_CHOICE, self._on_destination_changed)

        root_sizer.Add(options_sizer, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 4)

        button_sizer = wx.StdDialogButtonSizer()
        self.convert_button = wx.Button(panel, wx.ID_OK, _("Con&verter"))
        self.cancel_button = wx.Button(panel, wx.ID_CANCEL, _("&Cancelar"))
        self.convert_button.SetDefault()
        self.convert_button.Bind(wx.EVT_BUTTON, self._on_confirm)
        button_sizer.AddButton(self.convert_button)
        button_sizer.AddButton(self.cancel_button)
        button_sizer.Realize()
        root_sizer.Add(button_sizer, 0, wx.ALL | wx.EXPAND, 10)

        panel.SetSizer(root_sizer)
        frame_sizer = wx.BoxSizer(wx.VERTICAL)
        frame_sizer.Add(panel, 1, wx.EXPAND)
        self.SetSizerAndFit(frame_sizer)
        self.SetMinSize((560, 0))
        self.SetEscapeId(wx.ID_CANCEL)
        self.CentreOnParent()

        self.format_choice.Bind(wx.EVT_CHOICE, self._on_format_changed)
        self._refresh_enabled_controls()
        self._refresh_destination_controls()

    def _format_help_text(self):
        if self._audio_target:
            return _("Formato do arquivo de áudio gerado.")
        if self._mode == MODE_AUDIO_TO_VIDEO:
            return _("Formato do vídeo gerado. O áudio é mantido e a imagem fica parada durante toda a duração.")
        return _(
            "Novo formato do vídeo. O nome do arquivo é mantido, com a nova extensão. "
            "As faixas compatíveis com o novo formato são copiadas sem perda de qualidade, "
            "e as demais são recodificadas."
        )

    def _remembered(self, name, fallback):
        return getattr(self._settings, name, fallback) if self._settings is not None else fallback

    def _remembered_index(self, name, values, fallback):
        value = self._remembered(name, fallback)
        return values.index(value if value in values else fallback)

    def _format_setting_name(self):
        # Cada tipo de conversão lembra o próprio formato de destino.
        if self._audio_target:
            return "convert_audio_format"
        if self._mode == MODE_AUDIO_TO_VIDEO:
            return "convert_video_format"
        return "convert_container_format"

    def _default_format_index(self):
        fallback = DEFAULT_AUDIO_FORMAT if self._audio_target else DEFAULT_VIDEO_FORMAT
        for candidate in (self._remembered(self._format_setting_name(), fallback), fallback):
            if candidate in self._target_formats:
                return self._target_formats.index(candidate)
        return 0

    def store_choices(self, settings):
        """Guarda em *settings* o que foi escolhido, para o próximo diálogo abrir igual."""
        setattr(settings, self._format_setting_name(), self._selected_format())
        if self.bitrate_choice is not None:
            settings.convert_audio_bitrate = AUDIO_BITRATES[self.bitrate_choice.GetSelection()]
        if self.sample_rate_choice is not None:
            settings.convert_sample_rate = SAMPLE_RATES[self.sample_rate_choice.GetSelection()]
        if self.height_choice is not None:
            settings.convert_video_height = VIDEO_HEIGHTS[self.height_choice.GetSelection()]
        if self.cover_checkbox is not None:
            settings.convert_use_cover = self.cover_checkbox.GetValue()
        settings.convert_same_folder = self.saves_in_same_folder()
        settings.convert_directory = self.other_directory() or settings.convert_directory

    def _selected_format(self):
        return self._target_formats[self.format_choice.GetSelection()]

    def _on_format_changed(self, _event):
        self._refresh_enabled_controls()

    def _on_destination_changed(self, _event):
        self._refresh_destination_controls()

    def _saves_in_other_folder(self) -> bool:
        return self.destination_choice.GetSelection() == 1

    def saves_in_same_folder(self) -> bool:
        """Numa fila, cada arquivo vai para a pasta do próprio original."""
        return not self._saves_in_other_folder()

    def _refresh_destination_controls(self):
        # O campo de pasta só vale para «Outra pasta».
        other = self._saves_in_other_folder()
        self.directory_ctrl.Enable(other)
        self.directory_ctrl.browse_button.Enable(other)

    def other_directory(self) -> str:
        """Última pasta digitada ou escolhida em «Outra pasta», para lembrar depois."""
        return self.directory_ctrl.GetValue().strip()

    def _refresh_enabled_controls(self):
        if not self._audio_target:
            return
        spec = AUDIO_FORMATS[self._selected_format()]
        self.bitrate_choice.Enable(spec.lossy)
        # O Opus fixa 48 kHz: a escolha não teria efeito.
        self.sample_rate_choice.Enable(self._selected_format() != "opus")

    def get_request(self) -> ConvertRequest:
        bitrate = DEFAULT_AUDIO_BITRATE
        if self.bitrate_choice is not None:
            bitrate = AUDIO_BITRATES[self.bitrate_choice.GetSelection()]
        sample_rate = SAMPLE_RATES[self.sample_rate_choice.GetSelection()] if self.sample_rate_choice else 0
        height = VIDEO_HEIGHTS[self.height_choice.GetSelection()] if self.height_choice else DEFAULT_VIDEO_HEIGHT
        return ConvertRequest(
            mode=self._mode,
            source_path=self._source_path,
            output_directory=(
                self.directory_ctrl.GetValue().strip()
                if self._saves_in_other_folder()
                else os.path.dirname(self._source_path)
            ),
            target_format=self._selected_format(),
            audio_bitrate_kbps=bitrate,
            sample_rate=sample_rate,
            video_height=height,
            use_cover=self.cover_checkbox.GetValue() if self.cover_checkbox else True,
        )

    def _on_confirm(self, _event):
        if self._saves_in_other_folder() and not self.directory_ctrl.GetValue().strip():
            wx.MessageBox(
                _("Escolha uma pasta de destino para o arquivo convertido."),
                _("Converter mídia"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self.directory_ctrl.SetFocus()
            return
        self.EndModal(wx.ID_OK)
