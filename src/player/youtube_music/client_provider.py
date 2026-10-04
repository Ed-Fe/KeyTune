from ..log import get_logger
from ..i18n import _


_logger = get_logger(__name__)


def _supported_location(ytmusicapi_module, location):
    """*location* quando o ytmusicapi a aceita; senão vazio, para ele não recusar o cliente."""
    location = str(location or "").strip().upper()
    supported = getattr(getattr(ytmusicapi_module, "constants", None), "SUPPORTED_LOCATIONS", ())
    return location if location in supported else ""


class YouTubeMusicClientProvider:
    """Manages the creation and caching of ``YTMusic`` client instances.

    This class holds authenticated and public ``YTMusic`` clients so they are
    reused across calls instead of being rebuilt on every API operation.
    """

    def __init__(self):
        self._authenticated_client = None
        self._public_client = None
        self._location = ""

    def get_client(
        self, *, ytmusicapi_module, require_auth=True, auth_file_path=None, has_saved_auth=False, location=""
    ):
        """Return a cached or newly created ``YTMusic`` client.

        Parameters
        ----------
        ytmusicapi_module:
            The imported ``ytmusicapi`` module (obtained via
            ``import_ytmusicapi_module``).
        require_auth:
            When ``True``, return an authenticated client bound to the
            user's saved browser auth file.  When ``False``, return a
            public (anonymous) client.
        auth_file_path:
            Absolute path to the browser auth JSON file.  Required when
            *require_auth* is ``True``.
        has_saved_auth:
            Whether saved browser auth credentials exist on disk.
        location:
            Country code sent with every request; empty lets YouTube decide.
        """
        location = _supported_location(ytmusicapi_module, location)
        if location != self._location:
            self.clear_cache()
            self._location = location
        if require_auth and self._authenticated_client is not None:
            return self._authenticated_client
        if not require_auth and self._public_client is not None:
            return self._public_client

        YTMusic = ytmusicapi_module.YTMusic
        location_options = {"location": location} if location else {}

        if require_auth and not has_saved_auth:
            raise RuntimeError(_("Faça a autenticação do navegador antes de buscar playlists."))

        if require_auth:
            self._authenticated_client = YTMusic(auth_file_path, **location_options)
            _logger.debug("Authenticated YTMusic client created.")
            return self._authenticated_client

        self._public_client = YTMusic(**location_options)
        _logger.debug("Public YTMusic client created.")
        return self._public_client

    def clear_cache(self):
        """Discard cached client instances so they are rebuilt on next use."""
        self._authenticated_client = None
        self._public_client = None
