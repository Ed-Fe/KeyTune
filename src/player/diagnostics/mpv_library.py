"""Por que a biblioteca do MPV não carregou.

Lê a tabela de imports da DLL e pergunta ao Windows por cada dependência, porque
o ``ctypes`` esconde o código de erro e a mensagem dele não diz o que falta.
Sem wxPython.
"""

from __future__ import annotations

import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from ..i18n import _
from ..log import get_logger
from ..mpv_runtime import find_runtime_library

_logger = get_logger(__name__)

_LOAD_WITH_DLL_DIR = 0x1100  # LOAD_LIBRARY_SEARCH_DEFAULT_DIRS | LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR
_LOAD_DEFAULT_DIRS = 0x1000  # pasta do aplicativo, System32 e as pastas de os.add_dll_directory
_ERROR_ACCESS_DENIED = 5
_ERROR_BAD_EXE_FORMAT = 193
_ERROR_VIRUS_INFECTED = 225
_VULKAN_LOADER = "vulkan-1.dll"
_VISUAL_CPP_PREFIXES = ("vcruntime", "msvcp", "vcomp", "concrt")
_UNIVERSAL_CRT_PREFIXES = ("api-ms-win-crt-", "ucrtbase")
VISUAL_CPP_REDISTRIBUTABLE_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"


@dataclass(frozen=True, slots=True)
class MpvLibraryDiagnosis:
    """O que o Windows respondeu ao carregar a DLL do MPV.

    ``dll_path`` é ``None`` quando nenhuma pasta candidata tem a DLL;
    ``error_code`` é 0 quando ela carregou. ``missing_functions`` traz pares
    ``(função, DLL que deveria tê-la)``; ``broken_libraries``, as DLLs da pasta
    do MPV que o Windows recusou sem que faltasse nada a elas.
    """

    dll_path: Path | None
    error_code: int = 0
    imported_libraries: tuple[str, ...] = ()
    missing_libraries: tuple[str, ...] = ()
    missing_functions: tuple[tuple[str, str], ...] = ()
    broken_libraries: tuple[str, ...] = ()

    @property
    def loaded(self) -> bool:
        return self.dll_path is not None and self.error_code == 0

    def imports(self, library_name: str) -> bool:
        return library_name.casefold() in {name.casefold() for name in self.imported_libraries}


def pe_imports(dll_path: Path) -> dict[str, list[str]]:
    """``{DLL importada: funções importadas por nome}`` da tabela de imports de um PE."""
    try:
        data = dll_path.read_bytes()
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        sections = struct.unpack_from("<H", data, pe + 6)[0]
        opt_size = struct.unpack_from("<H", data, pe + 20)[0]
        opt = pe + 24
        is_64_bit = struct.unpack_from("<H", data, opt)[0] == 0x20B
        import_rva = struct.unpack_from("<I", data, opt + (112 if is_64_bit else 96) + 8)[0]
        table = opt + opt_size
        spans = [struct.unpack_from("<IIII", data, table + 40 * i + 8) for i in range(sections)]

        def to_offset(rva: int) -> int:
            for virtual_size, virtual_address, raw_size, raw_pointer in spans:
                if virtual_address <= rva < virtual_address + max(virtual_size, raw_size):
                    return rva - virtual_address + raw_pointer
            raise ValueError(rva)

        def text_at(offset: int) -> str:
            return data[offset : data.index(bytes(1), offset)].decode("ascii", "replace")

        thunk_size = 8 if is_64_bit else 4
        ordinal_flag = 1 << (thunk_size * 8 - 1)
        imports: dict[str, list[str]] = {}
        if not import_rva:
            return imports
        cursor = to_offset(import_rva)
        while True:
            lookup_rva, _stamp, _chain, name_rva, address_rva = struct.unpack_from("<IIIII", data, cursor)
            if not name_rva:
                return imports
            functions = imports.setdefault(text_at(to_offset(name_rva)), [])
            thunk = to_offset(lookup_rva or address_rva)
            while True:
                entry = int.from_bytes(data[thunk : thunk + thunk_size], "little")
                if not entry:
                    break
                if not entry & ordinal_flag:
                    functions.append(text_at(to_offset(entry & 0x7FFFFFFF) + 2))
                thunk += thunk_size
            cursor += 20
    except (OSError, ValueError, struct.error):
        return {}


def diagnose_mpv_library(dll_path: Path | None = None) -> MpvLibraryDiagnosis:
    """Tenta carregar a DLL do MPV e, se o Windows recusar, aponta o que falta."""
    if dll_path is None:
        dll_path = find_runtime_library()
    if dll_path is None:
        return MpvLibraryDiagnosis(dll_path=None)

    imports = pe_imports(dll_path)
    imported_libraries = tuple(imports)
    if not sys.platform.startswith("win"):
        return MpvLibraryDiagnosis(dll_path=dll_path, imported_libraries=imported_libraries)

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]
    kernel32.GetProcAddress.restype = ctypes.c_void_p
    kernel32.GetProcAddress.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    kernel32.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]

    ctypes.set_last_error(0)
    if kernel32.LoadLibraryExW(str(dll_path), None, _LOAD_WITH_DLL_DIR):
        return MpvLibraryDiagnosis(dll_path=dll_path, imported_libraries=imported_libraries)
    error_code = ctypes.get_last_error() or -1

    runtime_dir = dll_path.parent
    missing_libraries: list[str] = []
    missing_functions: list[tuple[str, str]] = []
    broken_libraries: list[str] = []
    visited: set[str] = set()

    def check(owner_imports: dict[str, list[str]]) -> None:
        for library_name, functions in owner_imports.items():
            key = library_name.casefold()
            if key in visited:
                continue
            visited.add(key)
            local_path = runtime_dir / library_name
            if local_path.is_file():
                handle = kernel32.LoadLibraryExW(str(local_path), None, _LOAD_WITH_DLL_DIR)
                if not handle:
                    # Só as DLLs que vêm com o MPV são abertas por dentro: as do
                    # Windows resolvem as próprias dependências.
                    found_before = len(missing_libraries) + len(missing_functions) + len(broken_libraries)
                    check(pe_imports(local_path))
                    if found_before == len(missing_libraries) + len(missing_functions) + len(broken_libraries):
                        broken_libraries.append(library_name)
                    continue
            else:
                handle = kernel32.LoadLibraryExW(library_name, None, _LOAD_DEFAULT_DIRS)
                if not handle:
                    missing_libraries.append(library_name)
                    continue
            resolved = ctypes.create_unicode_buffer(520)
            kernel32.GetModuleFileNameW(handle, resolved, 520)
            for function in functions:
                if not kernel32.GetProcAddress(handle, function.encode("ascii", "replace")):
                    missing_functions.append((function, resolved.value or library_name))

    check(imports)
    _logger.error(
        "MPV library %s failed to load (error %s). Missing libraries: %s; missing functions: %s; broken: %s",
        dll_path,
        error_code,
        missing_libraries,
        [f"{function} ({Path(owner).name})" for function, owner in missing_functions],
        broken_libraries,
    )
    return MpvLibraryDiagnosis(
        dll_path=dll_path,
        error_code=error_code,
        imported_libraries=imported_libraries,
        missing_libraries=tuple(missing_libraries),
        missing_functions=tuple(missing_functions),
        broken_libraries=tuple(broken_libraries),
    )


def _starts_with(library_name: str, prefixes: tuple[str, ...]) -> bool:
    return library_name.casefold().startswith(prefixes)


def explain_mpv_library(diagnosis: MpvLibraryDiagnosis) -> tuple[str, str]:
    """``(o que aconteceu, o que fazer)``; os dois vazios quando a DLL carregou."""
    if diagnosis.loaded:
        return "", ""
    if diagnosis.dll_path is None:
        return _("A biblioteca do MPV não foi encontrada na instalação."), _("Reinstale o KeyTune.")

    dll_name = diagnosis.dll_path.name
    if diagnosis.missing_functions:
        names = "; ".join(f"{function} ({Path(owner).name})" for function, owner in diagnosis.missing_functions[:6])
        detail = _("Estas funções não existem na DLL do sistema: {names}.").format(names=names)
        if any(Path(owner).name.casefold() == _VULKAN_LOADER for _function, owner in diagnosis.missing_functions):
            return detail, _(
                "O vulkan-1.dll em uso é antigo. Reinstale o KeyTune, que leva o próprio vulkan-1.dll na pasta mpv, "
                "ou atualize o driver de vídeo."
            )
        return detail, _("Instale as atualizações pendentes do Windows.")

    if diagnosis.missing_libraries:
        missing = diagnosis.missing_libraries
        detail = _("Faltam estas bibliotecas do Windows: {names}.").format(names=", ".join(missing))
        if any(_starts_with(name, _VISUAL_CPP_PREFIXES) for name in missing):
            return detail, _(
                "Instale o Microsoft Visual C++ Redistributable 2015-2022 (x64), disponível em {url}."
            ).format(url=VISUAL_CPP_REDISTRIBUTABLE_URL)
        if any(_starts_with(name, _UNIVERSAL_CRT_PREFIXES) for name in missing):
            return detail, _(
                "Falta o Universal C Runtime, que faz parte do Windows. Instale as atualizações pendentes do Windows."
            )
        if any(name.casefold() == _VULKAN_LOADER for name in missing):
            return detail, _(
                "Reinstale o KeyTune, que leva o próprio vulkan-1.dll na pasta mpv, ou atualize o driver de vídeo."
            )
        return detail, _("Reinstale o KeyTune. Se o erro continuar, instale as atualizações pendentes do Windows.")

    if diagnosis.broken_libraries:
        return (
            _("O Windows recusou estes arquivos da pasta do MPV: {names}. Eles estão danificados ou bloqueados.").format(
                names=", ".join(diagnosis.broken_libraries)
            ),
            _("Reinstale o KeyTune. Se o antivírus removeu os arquivos, adicione a pasta do KeyTune às exclusões."),
        )

    if diagnosis.error_code in (_ERROR_ACCESS_DENIED, _ERROR_VIRUS_INFECTED):
        return (
            _(
                "O Windows ou o antivírus bloqueou o carregamento de {name}. "
                "Restaure o arquivo da quarentena e adicione a pasta do KeyTune às exclusões."
            ).format(name=dll_name),
            "",
        )
    if diagnosis.error_code == _ERROR_BAD_EXE_FORMAT:
        return (
            _("{name} não é compatível com esta versão do aplicativo. Reinstale o KeyTune.").format(name=dll_name),
            "",
        )
    return (
        _("Erro {code} ao carregar {name}.").format(code=diagnosis.error_code, name=dll_name),
        _("Reinstale o KeyTune."),
    )


def describe_mpv_load_failure() -> str:
    """Uma frase para a mensagem de erro do player; vazia se a DLL carrega ou não existe."""
    diagnosis = diagnose_mpv_library()
    if diagnosis.dll_path is None:
        return ""
    return " ".join(part for part in explain_mpv_library(diagnosis) if part)
