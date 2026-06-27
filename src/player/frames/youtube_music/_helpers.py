"""Module-level factories and lazy wrappers shared by the YouTube Music mixins.

These were previously defined at the top of the monolithic
``frames/youtube_music.py``. They are kept as plain module functions (not mixin
methods) because they encapsulate lazy imports of optional/heavy dependencies.
"""

import os

from player.youtube_music.auth import get_browser_auth_file_path


def _configure_youtube_dependency_management(*, managed_install_enabled, auto_update_enabled, prefer_nightly_yt_dlp):
    from player.youtube_music.dependencies import configure_youtube_dependency_management

    return configure_youtube_dependency_management(
        managed_install_enabled=managed_install_enabled,
        auto_update_enabled=auto_update_enabled,
        prefer_nightly_yt_dlp=prefer_nightly_yt_dlp,
    )


def _find_all_available_javascript_runtimes():
    from player.youtube_music.yt_dlp_runtime import find_all_available_javascript_runtimes

    return find_all_available_javascript_runtimes()


def _install_or_update_youtube_dependencies(*, force, include_prerelease):
    from player.youtube_music.dependencies import install_or_update_youtube_dependencies

    return install_or_update_youtube_dependencies(
        force=force,
        include_prerelease=include_prerelease,
    )


def _is_youtube_dependency_auto_update_due(last_update_epoch, *, interval_hours):
    from player.youtube_music.dependencies import is_youtube_dependency_auto_update_due

    return is_youtube_dependency_auto_update_due(last_update_epoch, interval_hours=interval_hours)


def _is_missing_javascript_runtime_error_message(error_message):
    from player.youtube_music.streams import is_missing_javascript_runtime_error_message

    return is_missing_javascript_runtime_error_message(error_message)


def _youtube_dependencies_available():
    from player.youtube_music.dependencies import youtube_dependencies_available

    return youtube_dependencies_available()


def _create_youtube_music_service():
    from player.youtube_music.service import YouTubeMusicService

    return YouTubeMusicService()


def _youtube_music_tab_panel_class():
    from player.youtube_music.panel import YouTubeMusicTabPanel

    return YouTubeMusicTabPanel


def _youtube_music_has_saved_auth():
    return os.path.isfile(get_browser_auth_file_path())


def find_all_available_javascript_runtimes():
    return _find_all_available_javascript_runtimes()


def is_missing_javascript_runtime_error_message(error_message):
    return _is_missing_javascript_runtime_error_message(error_message)
