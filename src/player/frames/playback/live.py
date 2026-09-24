"""Live-broadcast helpers for the playback frame."""


def is_live_media(media) -> bool:
    """True only for a media object explicitly flagged as a live broadcast.

    The strict ``is True`` keeps test doubles and half-initialised players
    (whose attributes are truthy mocks) from being mistaken for a live.
    """
    return getattr(media, "is_live", False) is True
