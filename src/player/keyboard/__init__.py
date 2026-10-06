"""Personalização do teclado: catálogo de ações, atalhos globais e a tela de edição."""

from .shortcuts import (
    SCOPE_GLOBAL,
    SCOPE_LOCAL,
    Keymap,
    actions,
    effective_bindings,
    format_shortcut,
    is_bare_shortcut,
    normalize_overrides,
    normalize_shortcut,
)

__all__ = [
    "SCOPE_GLOBAL",
    "SCOPE_LOCAL",
    "KeyboardCustomizationDialog",
    "Keymap",
    "actions",
    "effective_bindings",
    "format_shortcut",
    "is_bare_shortcut",
    "normalize_overrides",
    "normalize_shortcut",
]


def __getattr__(name):
    # A tela puxa o wx; as preferências só precisam do catálogo.
    if name == "KeyboardCustomizationDialog":
        from .dialog import KeyboardCustomizationDialog

        return KeyboardCustomizationDialog
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
