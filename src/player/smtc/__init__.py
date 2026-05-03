"""Windows System Media Transport Controls (SMTC) integration."""

from .service import (
    SmtcService,
    is_smtc_supported,
    smtc_dependency_error_message,
)

__all__ = [
    "SmtcService",
    "is_smtc_supported",
    "smtc_dependency_error_message",
]
