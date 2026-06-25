import os
import sys

from player.mpv_runtime import bootstrap_mpv_runtime


def _normalize_launch_path(path):
    normalized_path = str(path or "").strip().strip('"')
    if not normalized_path:
        return ""
    return os.path.normcase(os.path.abspath(normalized_path))


def _collect_initial_paths(argv=None, *, launch_targets=None):
    raw_paths = list(sys.argv[1:] if argv is None else argv)
    normalized_launch_targets = {
        normalized_target
        for normalized_target in (
            _normalize_launch_path(target)
            for target in (launch_targets or (sys.executable, sys.argv[0]))
        )
        if normalized_target
    }

    initial_paths = []
    for path in raw_paths:
        normalized_path = _normalize_launch_path(path)
        if not normalized_path or normalized_path in normalized_launch_targets:
            continue
        initial_paths.append(path)

    return initial_paths


def main():
    bootstrap_mpv_runtime()

    initial_paths = _collect_initial_paths()

    if initial_paths:
        from player.single_instance import try_send_to_existing_instance

        if try_send_to_existing_instance(initial_paths):
            return

    from player.app import main as app_main

    app_main(initial_paths=initial_paths)


if __name__ == "__main__":
    main()
