"""Barra de progresso na barra de status, para downloads e conversões.

A barra só aparece enquanto há uma tarefa em andamento; sem porcentagem
conhecida ela fica em modo indeterminado. Se o download e a conversão rodarem
juntos, mostra a que mudou por último. Sem barra criada (testes, janelas
parciais), todas as chamadas são inofensivas.
"""

import wx

from ..i18n import _


_GAUGE_FIELD = 1
_GAUGE_WIDTH = 180


class TaskProgressMixin:
    def _task_progress_values(self):
        # Criado sob demanda para funcionar mesmo antes de a janela existir por inteiro.
        if not hasattr(self, "_task_progress_by_source"):
            self._task_progress_by_source = {}
            self._task_progress_latest = None
        return self._task_progress_by_source

    def _create_task_progress_gauge(self, status_bar):
        """Cria a barra (escondida) num segundo campo da barra de status."""
        self._task_progress_gauge = wx.Gauge(status_bar, range=100, style=wx.GA_HORIZONTAL)
        self._task_progress_gauge.SetName(_("Progresso da tarefa"))
        self._task_progress_gauge.Hide()
        status_bar.SetFieldsCount(2)
        status_bar.SetStatusWidths([-1, 0])
        status_bar.Bind(wx.EVT_SIZE, self._on_task_progress_status_bar_resized)

    def _on_task_progress_status_bar_resized(self, event):
        event.Skip()
        self._place_task_progress_gauge()

    def _place_task_progress_gauge(self):
        gauge = getattr(self, "_task_progress_gauge", None)
        status_bar = getattr(self, "status_bar", None)
        if gauge is None or status_bar is None:
            return
        rect = status_bar.GetFieldRect(_GAUGE_FIELD)
        gauge.SetSize(rect.x + 2, rect.y + 2, max(0, rect.width - 4), max(0, rect.height - 4))

    def _set_task_progress(self, source, percent):
        """Atualiza a barra da tarefa *source*; ``None`` deixa em modo indeterminado."""
        self._task_progress_values()[source] = percent
        self._task_progress_latest = source
        self._refresh_task_progress()

    def _clear_task_progress(self, source):
        values = self._task_progress_values()
        values.pop(source, None)
        if self._task_progress_latest == source:
            self._task_progress_latest = next(reversed(values), None)
        self._refresh_task_progress()

    def _refresh_task_progress(self):
        gauge = getattr(self, "_task_progress_gauge", None)
        status_bar = getattr(self, "status_bar", None)
        if gauge is None or status_bar is None:
            return

        values = self._task_progress_values()
        if not values:
            gauge.Hide()
            status_bar.SetStatusWidths([-1, 0])
            return

        status_bar.SetStatusWidths([-1, _GAUGE_WIDTH])
        self._place_task_progress_gauge()
        gauge.Show()
        percent = values.get(self._task_progress_latest)
        if percent is None:
            gauge.Pulse()
        else:
            gauge.SetValue(max(0, min(100, int(percent))))
