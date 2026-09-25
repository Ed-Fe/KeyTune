"""Controles de download compartilhados pelas Preferências e pelo diálogo de download."""

from __future__ import annotations

import wx

from ..i18n import _
from ..widgets import add_choice_row, add_directory_row
from .options import (
    AUDIO_QUALITIES,
    AUDIO_QUALITY_ORIGINAL,
    DOWNLOAD_KIND_AUDIO,
    DOWNLOAD_KINDS,
    SAMPLE_RATES,
    VIDEO_QUALITIES,
    audio_quality_label,
    default_download_directory,
    download_kind_label,
    normalize_audio_quality,
    normalize_download_kind,
    normalize_sample_rate,
    normalize_video_quality,
    resolve_download_directory,
    sample_rate_label,
    video_quality_label,
)
from .plan import DownloadChoice


class DownloadOptionsPanel(wx.Panel):
    """Tipo, qualidades, taxa de amostragem e pasta de um download.

    Só o que faz sentido para o tipo escolhido fica habilitado: a qualidade do
    áudio e a taxa de amostragem valem para áudio, a do vídeo para vídeo, e a
    taxa de amostragem só quando o áudio é convertido.
    """

    def __init__(self, parent, *, kind_label):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.kind_choice = add_choice_row(
            self,
            sizer,
            kind_label,
            _("Escolha se o download será apenas o áudio ou o vídeo completo."),
            [download_kind_label(kind) for kind in DOWNLOAD_KINDS],
        )
        self.audio_quality_choice = add_choice_row(
            self,
            sizer,
            _("Qualidade do áudio"),
            _(
                "Original mantém o áudio exatamente como o YouTube o entrega, sem converter. "
                "MP3 e FLAC convertem o áudio e exigem o FFmpeg. Se a qualidade escolhida "
                "não existir, o áudio é baixado na qualidade original."
            ),
            [audio_quality_label(quality) for quality in AUDIO_QUALITIES],
        )
        self.sample_rate_choice = add_choice_row(
            self,
            sizer,
            _("Taxa de amostragem do áudio"),
            _(
                "Só vale quando o áudio é convertido para MP3 ou FLAC. "
                "Original mantém a taxa do arquivo baixado."
            ),
            [sample_rate_label(rate) for rate in SAMPLE_RATES],
        )
        self.video_quality_choice = add_choice_row(
            self,
            sizer,
            _("Qualidade do vídeo"),
            _(
                "Altura máxima do vídeo. Se a qualidade escolhida não existir, "
                "o vídeo é baixado na melhor qualidade disponível."
            ),
            [video_quality_label(quality) for quality in VIDEO_QUALITIES],
        )

        self.directory_ctrl = add_directory_row(
            self,
            sizer,
            _("Pasta de download"),
            _("Pasta onde os arquivos baixados serão salvos."),
            _("Escolha a pasta de download"),
            _("Escolher pasta de download"),
        )

        self.SetSizer(sizer)
        self.kind_choice.Bind(wx.EVT_CHOICE, self._on_option_changed)
        self.audio_quality_choice.Bind(wx.EVT_CHOICE, self._on_option_changed)

    def set_values(self, *, kind, audio_quality, video_quality, sample_rate, directory):
        self.kind_choice.SetSelection(DOWNLOAD_KINDS.index(normalize_download_kind(kind)))
        self.audio_quality_choice.SetSelection(AUDIO_QUALITIES.index(normalize_audio_quality(audio_quality)))
        self.video_quality_choice.SetSelection(VIDEO_QUALITIES.index(normalize_video_quality(video_quality)))
        self.sample_rate_choice.SetSelection(SAMPLE_RATES.index(normalize_sample_rate(sample_rate)))
        self.directory_ctrl.SetValue(resolve_download_directory(directory))
        self._refresh_enabled_controls()

    def get_choice(self) -> DownloadChoice:
        return DownloadChoice(
            kind=DOWNLOAD_KINDS[self.kind_choice.GetSelection()],
            audio_quality=AUDIO_QUALITIES[self.audio_quality_choice.GetSelection()],
            video_quality=VIDEO_QUALITIES[self.video_quality_choice.GetSelection()],
            sample_rate=SAMPLE_RATES[self.sample_rate_choice.GetSelection()],
            directory=self.directory_ctrl.GetValue().strip(),
        )

    def get_directory_setting(self) -> str:
        """Pasta a gravar nas preferências: vazio enquanto for a pasta padrão."""
        directory = self.directory_ctrl.GetValue().strip()
        return "" if directory == default_download_directory() else directory

    def _on_option_changed(self, _event):
        self._refresh_enabled_controls()

    def _refresh_enabled_controls(self):
        audio_selected = DOWNLOAD_KINDS[self.kind_choice.GetSelection()] == DOWNLOAD_KIND_AUDIO
        converts = AUDIO_QUALITIES[self.audio_quality_choice.GetSelection()] != AUDIO_QUALITY_ORIGINAL
        self.audio_quality_choice.Enable(audio_selected)
        self.sample_rate_choice.Enable(audio_selected and converts)
        self.video_quality_choice.Enable(not audio_selected)
