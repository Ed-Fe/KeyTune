"""Dados de uma rádio a publicar no diretório, e a validação deles.

Sem wx: a caixa de diálogo e os testes usam as mesmas regras.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

from ..i18n import _

DIRECTORY_NAME_LIMIT = 400
_HTTP_SCHEMES = {"http", "https"}


@dataclass(frozen=True)
class RadioDirectorySubmission:
    name: str
    url: str
    country_code: str = ""
    language_codes: str = ""
    tags: str = ""
    homepage: str = ""
    favicon: str = ""


def _comma_list(value):
    return ",".join(part.strip() for part in str(value or "").split(",") if part.strip())


def _http_url(value):
    """O endereço se for http(s) com servidor; vazio se estiver em branco; ``None`` se não valer."""
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme.lower() not in _HTTP_SCHEMES or not parts.netloc:
        return None
    return text


def directory_submission_preview(submission):
    """O que será enviado, uma linha por dado, e o aviso de que o cadastro é público."""
    lines = [
        _("Nome: {value}").format(value=submission.name),
        _("Endereço do stream: {value}").format(value=submission.url),
    ]
    if submission.country_code:
        lines.append(_("Código do país: {value}").format(value=submission.country_code))
    if submission.language_codes:
        lines.append(_("Códigos de idioma: {value}").format(value=submission.language_codes))
    if submission.tags:
        lines.append(_("Gêneros: {value}").format(value=submission.tags))
    if submission.homepage:
        lines.append(_("Site: {value}").format(value=submission.homepage))
    if submission.favicon:
        lines.append(_("Endereço do ícone: {value}").format(value=submission.favicon))
    lines.append("")
    lines.append(_("O cadastro é público e o KeyTune não pode desfazê-lo."))
    return "\n".join(lines)


def initial_directory_submission(country_code, selected_results):
    """Nome e endereço só entram quando há uma única rádio ainda fora do diretório."""
    code = str(country_code or "").strip().upper()
    results = list(selected_results or ())
    stations = [item for item in results if getattr(item, "result_type", "") == "station"]
    if len(results) == 1 and len(stations) == 1 and not str(stations[0].station_uuid or "").strip():
        station = stations[0]
        return RadioDirectorySubmission(
            name=str(station.name or "").strip(),
            url=str(station.stream_url or "").strip(),
            country_code=code,
        )
    return RadioDirectorySubmission(name="", url="", country_code=code)


def validate_directory_submission(
    name,
    url,
    country_code="",
    language_codes="",
    tags="",
    homepage="",
    favicon="",
):
    """Devolve ``(envio, campo, mensagem)``. Sem erro, o campo e a mensagem vêm vazios."""
    station_name = str(name or "").strip()
    if not station_name:
        return None, "name", _("Digite o nome da rádio.")
    if len(station_name) > DIRECTORY_NAME_LIMIT:
        return (
            None,
            "name",
            _("O nome pode ter no máximo {limit} caracteres.").format(limit=DIRECTORY_NAME_LIMIT),
        )

    raw_url = str(url or "").strip()
    if not raw_url:
        return None, "url", _("Digite o endereço do stream.")
    stream_url = _http_url(raw_url)
    if not stream_url:
        return None, "url", _("O endereço do stream precisa começar com http:// ou https://.")

    raw_country = str(country_code or "").strip()
    if raw_country and (len(raw_country) != 2 or not raw_country.isalpha()):
        return None, "country_code", _("O código do país fica em branco ou tem duas letras, como BR.")

    raw_homepage = str(homepage or "").strip()
    site = _http_url(raw_homepage)
    if raw_homepage and not site:
        return None, "homepage", _("O site precisa começar com http:// ou https://.")

    raw_icon = str(favicon or "").strip()
    icon = _http_url(raw_icon)
    if raw_icon and not icon:
        return None, "favicon", _("O endereço do ícone precisa começar com http:// ou https://.")

    return (
        RadioDirectorySubmission(
            name=station_name,
            url=stream_url,
            country_code=raw_country.upper(),
            language_codes=_comma_list(language_codes),
            tags=_comma_list(tags),
            homepage=site or "",
            favicon=icon or "",
        ),
        "",
        "",
    )
