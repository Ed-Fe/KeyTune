"""Publicar uma rádio no diretório do Radio Browser.

O cadastro é público: o KeyTune não consegue desfazê-lo nem editá-lo. A rede
roda fora da thread da interface, e um envio que não responde fica incerto.
"""

import threading

import wx

from player.radio.directory_dialog import AddRadioToDirectoryDialog
from player.radio.service import (
    DIRECTORY_ADDED,
    DIRECTORY_CHECK_FAILED,
    DIRECTORY_DUPLICATE,
    DIRECTORY_REJECTED,
    DIRECTORY_UNCERTAIN,
    DirectoryAddResult,
)
from player.radio.submission import initial_directory_submission

from ...announcements import ANNOUNCE_CONFIRMATIONS, ANNOUNCE_ERRORS, ANNOUNCE_PROGRESS
from ...i18n import _

_RESULTS_THAT_REOPEN = frozenset({DIRECTORY_CHECK_FAILED, DIRECTORY_REJECTED, DIRECTORY_UNCERTAIN})


def _directory_result_message(submission, result):
    """O que aconteceu, e a categoria do anúncio quando o resultado só é falado."""
    name = submission.name
    status = result.status
    if status == DIRECTORY_ADDED:
        return _("{name} foi adicionada ao diretório.").format(name=name), ANNOUNCE_CONFIRMATIONS
    if status == DIRECTORY_DUPLICATE:
        if result.existing_name:
            message = _("Este endereço já está no diretório, na rádio {name}.").format(name=result.existing_name)
        else:
            message = _("Este endereço já está no diretório.")
        return message, ANNOUNCE_ERRORS
    if status == DIRECTORY_REJECTED:
        if result.message:
            message = _("O diretório não aceitou o cadastro: {detail}").format(detail=result.message)
        else:
            message = _("O diretório não aceitou o cadastro.")
        return message, ANNOUNCE_ERRORS
    if status == DIRECTORY_UNCERTAIN:
        return (
            _(
                "Não dá para saber se o cadastro de {name} foi gravado. Procure a rádio antes de tentar de novo."
            ).format(name=name),
            ANNOUNCE_ERRORS,
        )
    return (
        _("Não foi possível verificar se este endereço já está no diretório. Nada foi enviado."),
        ANNOUNCE_ERRORS,
    )


def _alive(window):
    try:
        return bool(window) and not window.IsBeingDeleted()
    except RuntimeError:
        return False


class RadioDirectoryMixin:
    def _add_radio_to_directory(self):
        if getattr(self, "_radio_directory_submit_running", False):
            self._announce(_("O cadastro no diretório ainda está sendo enviado."), ANNOUNCE_ERRORS)
            return False
        country_code, _country_name = self._radio_region()
        return self._show_radio_directory_dialog(
            initial_directory_submission(country_code, self._selected_radio_results())
        )

    def _radio_directory_parent(self):
        panel = self._get_radio_panel()
        if _alive(panel):
            return panel
        return self

    def _show_radio_directory_dialog(self, initial):
        if not _alive(self):
            return False
        dialog = AddRadioToDirectoryDialog(self._radio_directory_parent(), initial)
        try:
            confirmed = dialog.ShowModal() == wx.ID_OK
            submission = dialog.submission if confirmed else None
        finally:
            if _alive(dialog):
                dialog.Destroy()
        if not confirmed or submission is None or not _alive(self):
            return False
        return self._submit_radio_to_directory(submission)

    def _submit_radio_to_directory(self, submission):
        if getattr(self, "_radio_directory_submit_running", False):
            self._announce(_("O cadastro no diretório ainda está sendo enviado."), ANNOUNCE_ERRORS)
            return False
        self._radio_directory_submit_running = True
        service = self._get_radio_service()
        self._announce(_("Enviando {name} ao diretório.").format(name=submission.name), ANNOUNCE_PROGRESS)

        def finish(result):
            try:
                self._radio_directory_submit_running = False
                if not _alive(self):
                    return
                if result.status in _RESULTS_THAT_REOPEN:
                    if self._ask_to_reopen_directory_form(submission, result) and _alive(self):
                        self._show_radio_directory_dialog(submission)
                    return
                message, category = _directory_result_message(submission, result)
                self._announce(message, category)
            except RuntimeError:
                return

        def runner():
            try:
                result = service.add_to_directory(submission)
            except Exception:
                result = DirectoryAddResult(DIRECTORY_UNCERTAIN)
            try:
                wx.CallAfter(finish, result)
            except RuntimeError:
                return

        threading.Thread(target=runner, daemon=True, name="radio-directory-add").start()
        return True

    def _ask_to_reopen_directory_form(self, submission, result):
        """Pergunta se a pessoa quer o formulário de volta. A mensagem do resultado fica só aqui."""
        if not _alive(self):
            return False
        detail, _category = _directory_result_message(submission, result)
        parent = self._radio_directory_parent()
        if not _alive(parent):
            return False
        dialog = wx.MessageDialog(
            parent,
            _("{detail}\n\nVoltar ao formulário?").format(detail=detail),
            _("Cadastro no diretório"),
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION,
        )
        try:
            dialog.SetYesNoLabels(_("&Sim"), _("&Não"))
            if not _alive(dialog):
                return False
            return dialog.ShowModal() == wx.ID_YES
        finally:
            if _alive(dialog):
                dialog.Destroy()
