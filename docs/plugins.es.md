# Plugins de KeyTune 2

Idiomas: [Español](plugins.es.md) · [English](plugins.en.md) · [Português](plugins.md). Consulta también el [manual del usuario](manual.es.md). Las versiones HTML se incluyen en la carpeta `docs` del reproductor.

KeyTune 2 ofrece una API pública basada en permisos, descubrimiento por manifiesto, un gestor accesible, paquetes verificables y un marketplace mantenido mediante pull requests en GitHub.

## Crear un plugin

Un paquete `.ktplugin` es un ZIP con `keytune-plugin.json` en la raíz:

```json
{
  "id": "org.example.my-plugin",
  "name": "Mi plugin",
  "version": "1.0.0",
  "api_version": "2.0",
  "minimum_keytune_version": "2.0.0",
  "entrypoint": "plugin:Plugin",
  "author": "Ejemplo",
  "description": "Una integración de ejemplo.",
  "license": "MIT",
  "isolation": "process",
  "permissions": ["playback.read", "notifications", "ui.menu"]
}
```

El objeto de entrada recibe la API en su constructor y puede implementar `on_start()`, `on_event(name, data)` y `on_stop()`.

```python
class Plugin:
    def __init__(self, api):
        self.api = api

    def on_start(self):
        self.api.add_menu_action("announce", "Anunciar pista", self.announce)

    def announce(self):
        state = self.api.playback_state()
        self.api.notify(state.get("media_path") or "Nada en reproducción")
```

El ejemplo mantenido en [examples/plugins/now-playing](https://github.com/Ed-Fe/KeyTune/tree/main/examples/plugins/now-playing) demuestra menús, dos pantallas, reproducción, biblioteca y ajustes privados. Ejecuta `python scripts/package_example_plugin.py` desde el repositorio para generar `examples/plugins/now-playing/now-playing-example-1.1.0.ktplugin`.

## Ciclo de vida y aislamiento

En modo `process`, el host conserva el identificador de la acción y envía `ui.action` al worker, donde se ejecuta el callback del menú. El plugin también puede manejar ese evento directamente. Las fábricas wxPython de pestañas y pantallas requieren `in_process`; por eso el ejemplo mantenido utiliza ese modo.

`in_process` ejecuta código dentro de KeyTune y requiere plena confianza. El modo predeterminado `process` separa fallos comunes, elimina variables de entorno sensibles heredadas y accede a los recursos del reproductor mediante la API versionada. El plugin sigue siendo Python normal y puede acceder directamente a archivos, red, subprocesos y bibliotecas. **El proceso separado no es una sandbox de seguridad para código no confiable.**

Las llamadas son síncronas. Los plugins en proceso deben ejecutar red, yt-dlp y análisis fuera del hilo de la interfaz y devolver las actualizaciones mediante wxPython. Los plugins aislados realizan RPC desde el worker. Los resultados son compatibles con JSON y no exponen objetos internos mutables. `api.data_directory` ofrece la ruta de datos privados; los métodos de conveniencia no impiden utilizar bibliotecas Python directamente.

Los eventos estables son `playback.media_changed` (ruta, título, artista e índice de playlist), `tab.changed` (índice) y `ui.action` (identificador registrado). `on_start()` se ejecuta después de restaurar la sesión, con las playlists cargadas.

## Permisos y referencia de la API 2.0

Antes de instalar o actualizar, KeyTune muestra los datos del manifiesto, permisos y aislamiento. La confirmación instala y activa el plugin con esos permisos. Las llamadas sin permiso producen `PermissionDeniedError`.

| Método | Permiso | Resultado |
| --- | --- | --- |
| `playback_state()` | `playback.read` | Medio, posición, volumen, velocidad, tono y estado |
| `playback(action, **arguments)` | `playback.control` | `play_pause`, `stop`, `next` o `previous` |
| `playlists()` / `active_playlist()` | `library.read` | Pestañas cargadas, elementos, etiquetas y selección |
| `library_search(query, limit=50)` | `library.read` | Registros de la biblioteca inteligente |
| `add_to_playlist(media_paths, playlist_index=None)` | `library.write` | Cantidad añadida |
| `youtube_music_account()` | `youtube_music.read` | Conexión y nombre de cuenta, nunca cookies |
| `youtube_music_search(query, scope="music_songs")` | `youtube_music.read` | Resultados normalizados |
| `youtube_music_playlists(limit=100)` | `youtube_music.read` | Playlists de la cuenta conectada |
| `youtube_music_playlist(playlist_id)` | `youtube_music.read` | Contenido normalizado |
| `youtube_music_rate(media_path, rating)` | `youtube_music.write` | Evaluar un medio |
| `youtube_music_create_playlist(title, description="", video_ids=())` | `youtube_music.write` | Identificador de la nueva playlist |
| `youtube_music_add_tracks(playlist_id, video_ids)` | `youtube_music.write` | Añadir pistas a una playlist de la cuenta |
| `resolve_media(media_path, use_account_auth=False)` | `yt_dlp` | URL reproducible y metadatos sin cookies ni cabeceras sensibles |
| `yt_dlp_info(media_path, flat_playlist=False, playlist_limit=100, use_account_auth=False)` | `yt_dlp` | Metadatos, formatos o entradas de playlist |
| `yt_dlp_download(media_path, destination_directory, ...)` | `yt_dlp` + `filesystem.write` | Rutas finales de los archivos descargados |
| `analyze_media(media_path, use_account_auth=False)` | `autodj.analyze` | BPM, beats, confianza, energía y tonalidad |
| `request(url, method="GET", body=None)` | `network` | Respuesta HTTP limitada a 2 MB |
| `read_text(path, encoding="utf-8", max_bytes=2097152)` | `filesystem.read` | Texto externo limitado a 2 MB |
| `write_text(path, text, encoding="utf-8")` | `filesystem.write` | Escritura externa limitada a 2 MB |
| `clipboard_text()` / `set_clipboard_text(text)` | `clipboard` | Leer/escribir texto del portapapeles |
| `get_setting(key, default=None)` / `set_setting(key, value)` | `settings` | Ajustes JSON privados y atómicos |
| `notify(message)` | `notifications` | Anuncio accesible |
| `add_menu_action(identifier, label, callback, submenu="")` | `ui.menu` | Registrar una acción de menú |
| `add_tab(identifier, label, factory)` | `ui.tab` | Pestaña wxPython, solo en proceso |
| `add_view(identifier, label, factory)` | `ui.view` | Pantalla wxPython, solo en proceso |

Los parámetros opcionales después de los argumentos principales se pasan por nombre, excepto `limit` de `library_search` y `default` de `get_setting`. Las firmas exactas están en el [código de la API](https://github.com/Ed-Fe/KeyTune/blob/main/src/player/plugins/api.py).

## Biblioteca cargada y YouTube Music

`playlists()` consulta las playlists y carpetas abiertas, con sus elementos y etiquetas visibles. `library_search()` devuelve una lista vacía si la biblioteca inteligente está desactivada. YouTube Music reutiliza la sesión y servicios de KeyTune sin entregar cookies, archivos de autenticación ni cabeceras sensibles. Evaluar medios, crear playlists y añadir pistas exige `youtube_music.write`.

## yt-dlp y AutoDJ en línea

KeyTune administra el ejecutable oficial de yt-dlp; no entrega un objeto Python `YoutubeDL`. `yt_dlp_info()` y `yt_dlp_download()` reutilizan ese ejecutable y los runtimes JavaScript del reproductor. El acceso es anónimo por defecto. `use_account_auth=True` requiere además `youtube_music.read` y utiliza internamente las credenciales protegidas.

```python
info = api.yt_dlp_info("https://www.youtube.com/watch?v=...")
files = api.yt_dlp_download(
    "https://www.youtube.com/watch?v=...",
    r"C:\Users\usuario\Videos",
    format_selector="best[ext=mp4]/best",
)
```

Las opciones de descarga por nombre son `format_selector="best[ext=mp4]/best"`, `filename_template="%(title).200B [%(id)s].%(ext)s"`, `playlist=False`, `playlist_limit=100` y `use_account_auth=False`. La plantilla no admite componentes de carpeta ni se aceptan argumentos arbitrarios de línea de comandos. El formato predeterminado prefiere MP4 progresivo para evitar FFmpeg externo; combinar vídeo y audio separados requiere un ejecutable FFmpeg compatible.

Usa `resolve_media()` si solo necesitas una URL reproducible. `analyze_media()` acepta archivos locales, URLs y referencias de YouTube Music. El contenido privado requiere autenticación y `youtube_music.read`. Para contenido en línea descarga como máximo 120 MB a almacenamiento temporal, transmite internamente las cabeceras necesarias, decodifica con los codecs FFmpeg incluidos en PyAV y analiza con librosa 0.11. El resultado remoto se conserva siete días; el archivo temporal se elimina inmediatamente. Se analizan como máximo los primeros 15 minutos.

librosa proporciona beats, ataques, RMS y cromagrama. PyAV evita necesitar FFmpeg externo para el análisis. Un error de decodificación no interrumpe la reproducción normal. Instala los recursos opcionales de YouTube/AutoDJ necesarios desde las preferencias antes de utilizar estos servicios.

## Marketplace en GitHub

El [repositorio comunitario](https://github.com/Ed-Fe/keytune-plugins) mantiene `catalog.json` con `schema_version: 1` y una lista `plugins`. Cada entrada contiene `id`, `name`, `version`, `description`, `author`, `homepage`, `download_url` HTTPS, `sha256` y `verified`.

1. Publica el `.ktplugin` en una GitHub Release.
2. Calcula el SHA-256 del archivo final.
3. Abre una pull request añadiendo o actualizando la entrada con `verified: false`.
4. Supera la validación de esquema, identificadores únicos, HTTPS, checksum, manifiesto y compatibilidad.
5. Los mantenedores pueden conceder `verified` tras revisar la procedencia; no garantiza seguridad.

El cliente descarga fuera del hilo de interfaz, exige HTTPS incluso tras redirecciones, limita tamaños, bloquea rutas ZIP peligrosas y nombres inválidos de Windows, verifica SHA-256/identificador/versión e instala transaccionalmente. Después muestra el manifiesto real, permisos y estado de verificación antes de instalar y activar.

## Compatibilidad

KeyTune 2.0.0 introduce `api_version: "2.0"`. El número principal define cambios incompatibles. Las versiones menores añaden métodos y eventos; eliminar API requiere una versión principal y aviso previo. Ignora eventos y campos desconocidos. Guarda datos privados por identificador sin depender de estructuras internas.

## Diagnóstico y distribución

Los fallos se registran en `plugin-logs/<id>.log`. Los paquetes se instalan en `plugins/<id>`; estado y consentimiento están en `plugins/registry.json`, dentro del directorio de datos del usuario de KeyTune. No incluyas secretos en paquetes o manifiestos. Publica una nueva versión en lugar de sustituir archivos ya catalogados.
