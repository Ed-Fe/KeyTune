# Manual de KeyTune

KeyTune es un reproductor multimedia creado para usarse con teclado y con foco en la accesibilidad. Está pensado para funcionar bien con playlists, navegación por carpetas y para conservar lo que estabas haciendo entre una apertura y otra.

Este proyecto fue desarrollado con asistencia de IA, incluyendo GitHub Copilot, Codex de OpenAI y Claude Code de Anthropic.

Este manual presenta las funciones principales de la aplicación y las acciones más comunes para empezar a usar el reproductor con rapidez.

## Qué ofrece KeyTune

- Reproducción multimedia con control por teclado
- Playlists en pestañas
- Una cola de reproducción para organizar lo que sonará después
- Navegación por carpetas con vista previa
- Ecualizador por pestaña con predefinidos y presets personalizados
- Un panel de letras con búsqueda automática y copia del texto
- Pestaña dedicada de YouTube Music, abierta con `Ctrl+Shift+Y`
- Carga y guardado de playlists
- Restauración de lo que estaba abierto en la última sesión
- Lista de archivos, carpetas y playlists recientes
- Anuncios de accesibilidad cuando hay lectores de pantalla disponibles

## Primeros pasos

1. Descarga el instalador `KeyTune-Setup.exe` más reciente en la página de [lanzamientos](https://github.com/ed-fe/KeyTune/releases).
2. Ejecuta el instalador y sigue los pasos. En la página de tareas adicionales puedes marcar la creación de un acceso directo en el escritorio y elegir qué formatos de audio, video y playlist quieres asociar con KeyTune; todo es opcional y está desmarcado de forma predeterminada. Asociar un formato registra KeyTune como opción en el menú *Abrir con*; para que abra esos archivos automáticamente, todavía debes confirmarlo como predeterminado en la configuración de Windows.
3. Al final, el instalador ofrece iniciar KeyTune y abrir este manual.
4. En ejecuciones futuras, cuando haya una actualización disponible, la propia aplicación muestra un diálogo con las novedades y pide confirmación antes de descargarla e instalarla (consulta [Actualizaciones](#actualizaciones)).

KeyTune depende del runtime de MPV para reproducir medios. El instalador ya incluye ese runtime; si el reproductor abre pero no reproduce nada, consulta la sección [Solución de problemas](#solución-de-problemas).

## Interfaz

Al abrir KeyTune por primera vez, la ventana principal muestra una sola pestaña de playlist vacía, sin nada para reproducir todavía. La ventana se divide en cuatro áreas:

- **Barra de menús**, en la parte superior: **Archivo** (abrir medios/carpeta/playlist, recientes, guardar), **Reproducción** (reproducir/pausar, pista anterior/siguiente, aleatorio, repetición, dispositivo de audio, anuncios), **Ver** (alternar foco, ecualizador, YouTube Music), **Pestañas** (nueva pestaña, navegación entre pestañas, cerrar), **Configuración** (preferencias) y **Ayuda** (manual, atajos, buscar actualizaciones).
- **Área de pestañas**, que ocupa la mayor parte de la ventana: cada pestaña representa una playlist o una carpeta abierta (consulta [Playlist, carpetas y pestañas](#playlist-carpetas-y-pestañas)). Dentro de cada pestaña, el espacio se divide en dos partes lado a lado:
    - a la **izquierda**, el navegador de elementos: la lista de la playlist o el contenido de la carpeta actual;
    - a la **derecha**, el área del reproductor. Cuando el medio actual es un video, esta área muestra el cuadro de video; para audio, o cuando no hay nada cargado, muestra un texto de apoyo con los atajos más usados para empezar.
- **Panel de tiempo**, debajo del área de pestañas: muestra el tiempo transcurrido y la duración del medio actual, una barra de progreso visual y un resumen de los atajos principales.
- **Barra de estado**, en el borde inferior de la ventana: muestra mensajes breves y temporales sobre la última acción realizada (por ejemplo, al abrir un archivo o guardar una playlist).

Usa `Tab` o `Ctrl+B` para mover el foco entre el navegador de elementos y el reproductor dentro de la pestaña activa, y `F1` en cualquier momento para abrir la ayuda rápida de atajos.

## Cómo abrir medios

Puedes abrir archivos multimedia, una playlist local, una carpeta o una ruta y enlace compatible usando los atajos o el menú **Archivo**:

- `Ctrl+Alt+O` - diálogo unificado que acepta cualquier tipo: archivo, carpeta, playlist, enlace o ID de YouTube Music.
- `Ctrl+O` - abre archivos multimedia o una playlist `.m3u`/`.m3u8`.
- `Ctrl+Shift+O` - abre una carpeta directamente en el navegador de carpetas.
- `Ctrl+V` - pega una ruta o enlace desde el portapapeles en la playlist actual.
- `Ctrl+Shift+V` - pega y abre en una nueva playlist.

Formatos multimedia compatibles directamente:

- Audio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Video: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

El menú **Archivo > Recientes** guarda por separado los últimos **Archivos recientes**, **Carpetas recientes** y **Playlists recientes**, lo que facilita volver a abrir lo que usaste antes sin tener que navegar de nuevo.

## Playlist, carpetas y pestañas

Cada playlist queda en una pestaña separada. Esto ayuda a separar contextos, como una lista de canciones para escuchar ahora, una carpeta con archivos locales o una colección que quieres mantener organizada.

La pestaña activa define lo que se está reproduciendo y lo que aparece en el navegador lateral. Puedes mantener una pestaña para una playlist guardada, otra para una carpeta completa y otras para listas temporales, sin mezclar todo en el mismo contexto. Las pestañas se pueden abrir, alternar y cerrar sin afectar a las demás.

### Atajos de pestañas y elementos

Los atajos para abrir medios, carpetas, playlists y enlaces están en la sección [Cómo abrir medios](#cómo-abrir-medios), más arriba. Los atajos siguientes son específicos de las pestañas y de la playlist actual:

- `Ctrl+T`: abrir una nueva pestaña de playlist
- `Ctrl+W`: cerrar la pestaña o playlist actual
- `Ctrl+Shift+W`: cerrar el medio actual
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: navegar a la pestaña siguiente o anterior
- `Ctrl+Shift+E`: abrir el ecualizador de la pestaña activa
- `Ctrl+C`: copiar la ruta o enlace del elemento seleccionado
- `Ctrl+Shift+S`: guardar la playlist actual
- `Ctrl+B`: alternar foco entre el navegador de elementos y el reproductor

### Cola de reproducción

La cola de reproducción organiza lo que debe sonar después de la pista actual, sin depender del orden de la playlist que estés navegando. Siempre pertenece a la playlist que está sonando en ese momento.

Usa `Ctrl+Shift+F` o el menú **Reproducción > Agregar a la Cola de Reproducción** para agregar o quitar elementos de la cola. Para ver, quitar, reordenar o vaciar toda la cola, usa `Ctrl+Shift+Q` o el menú **Reproducción > Administrar la Cola de Reproducción**.

Si la cola está vacía, el administrador te lo indica y te pide que primero agregues elementos.

### Atajos de reproducción

- `Espacio`: reproducir o pausar
- `Flecha izquierda` / `Flecha derecha`: retroceder o avanzar en el medio actual
- `Shift+Flecha izquierda` / `Shift+Flecha derecha`: retroceder o avanzar 1 minuto en el medio actual
- `Home` / `End`: ir al inicio o al final del medio
- `Flecha arriba` / `Flecha abajo`: subir o bajar el volumen
- `Ctrl+.`: detener la reproducción
- `Ctrl+PageUp` / `Ctrl+PageDown`: pista anterior o siguiente en la playlist
- `Alt+Flecha izquierda` / `Alt+Flecha derecha`: pista anterior o siguiente en la playlist (alternativa a `Ctrl+PageUp`/`Ctrl+PageDown`)
- `Alt+Flecha arriba` / `Alt+Flecha abajo`: mover el elemento actual hacia arriba o hacia abajo en la playlist
- `Alt+Home` / `Alt+End`: ir al primer o al último elemento de la playlist
- `E`: alternar modo aleatorio
- `R`: alternar modo de repetición
- `A`: alternar la reproducción de contenido relacionado de YouTube Music (radio automática al final de la playlist)
- `]` / `[`: aumentar o disminuir la velocidad de reproducción
- `Shift+]` / `Shift+[`: aumentar o disminuir el tono de la reproducción en semitonos
- `Shift+\`: restaurar el tono original
- `Ctrl+Alt+L`: alternar el panel de letras
- `Ctrl+Shift+F`: agregar el elemento seleccionado a la cola de reproducción
- `Ctrl+Shift+Q`: administrar la cola de reproducción
- `T`: anunciar el tiempo actual del medio
- `V`: anunciar el volumen actual
- `S`: anunciar el estado del reproductor
- `Ctrl+L`: marcar con me gusta el medio actual en YouTube Music
- `Ctrl+Shift+L`: marcar el medio actual como no me gusta en YouTube Music

El atajo `Ctrl+W` cierra directamente la pestaña activa; el atajo `Ctrl+Shift+W` cierra o descarga el medio actual en la pestaña activa.

### Navegador de elementos

El navegador está a la izquierda de la ventana y opera en dos modos distintos según lo que haya en la pestaña activa: **modo playlist** y **modo carpeta**. Usa `Tab` o `Ctrl+B` para alternar el foco entre el navegador y el reproductor.

#### Modo playlist

Cuando la pestaña contiene una playlist, el navegador muestra todos los elementos de la secuencia. El elemento en reproducción queda marcado con `▶` al inicio de la línea. Los atajos disponibles son:

- `Enter`: reproduce el elemento seleccionado inmediatamente.
- `Delete`: elimina el elemento seleccionado de la playlist.
- `Shift+F10`: abre el menú contextual con acciones adicionales sobre el elemento o sobre toda la selección (la lista acepta selección múltiple). Además de copiar, pegar y eliminar, el menú trae las acciones de YouTube Music cuando la selección contiene pistas de ese origen: **Me gusta**/**No me gusta**, **Agregar a playlist de YouTube Music...** y, cuando la pestaña actual es una playlist tuya de YouTube Music, **Quitar de la playlist de YouTube Music**. Consulta [Administrar playlists de YouTube Music](#administrar-playlists-de-youtube-music).
- `Tab` / `Esc`: devuelve el foco al reproductor.

#### Modo carpeta

Cuando la pestaña proviene de una carpeta abierta con `Ctrl+Shift+O`, el navegador muestra el contenido del directorio actual: subcarpetas y archivos multimedia. A medida que avanza la reproducción, el elemento correspondiente al medio actual se resalta automáticamente. Al mover la selección a un archivo multimedia, el reproductor ya inicia la reproducción de ese archivo. Los atajos disponibles son:

- `Enter`: entra en la subcarpeta seleccionada o reproduce el archivo multimedia.
- `Backspace`: vuelve a la carpeta superior (equivale a seleccionar `..`).
- `Shift+F10`: abre el menú contextual.
- `Tab` / `Esc`: devuelve el foco al reproductor.

#### Localización rápida por escritura

En ambos modos, escribir letras o números mueve la selección al primer elemento cuyo nombre comienza con los caracteres escritos. La búsqueda ignora acentos y diferencias entre mayúsculas y minúsculas. Después de un segundo sin escribir, el acumulador de caracteres se reinicia y la siguiente letra inicia una nueva búsqueda.

Para tareas de organización, conviene pensar en las pestañas como espacios de trabajo independientes: una pestaña para reproducir algo ahora, otra para revisar la biblioteca y otra para pruebas o colecciones temporales.

## Configuración

Las preferencias están en `Ctrl+,` y se dividen en cuatro pestañas: **General**, **Reproducción**, **Accesibilidad** y **Recursos adicionales**.

### General

La pestaña **General** reúne las opciones que controlan cómo KeyTune vuelve a funcionar en la próxima apertura:

- **Restaurar sesión al iniciar**: reabre las pestañas e intenta retomar el estado de la ejecución anterior.
- **Recordar tamaño de la ventana**: guarda y restaura el tamaño de la ventana principal entre ejecuciones.
- **Recordar última carpeta usada**: usa la última carpeta abierta como directorio inicial en los diálogos de abrir y guardar.
- **Confirmar al salir**: pide confirmación antes de cerrar el reproductor.

En esta misma pestaña está la sección **Asociación de archivos** (Windows). El botón **Registrar como reproductor predeterminado** agrega KeyTune al menú *Abrir con* para formatos de audio, video y playlists. Después de registrar, define la app como predeterminada en la configuración de Windows si quieres que esos archivos se abran directamente en KeyTune. El botón **Anular registro de asociaciones** deshace ese registro.

La pestaña **General** también incluye la sección **Registro de logs**:

- **Registrar logs de diagnóstico**: cuando está activado, el reproductor graba un archivo de log rotativo en disco. Útil para depurar problemas y adjuntarlo al reporte de errores. Los logs se graban en inglés.
- **Nivel de detalle**: controla cuánta información se registra. *Solo errores* es el más silencioso; *Depuración* es el más detallado y puede generar archivos grandes. Solo está disponible cuando el registro está activado.
- **Abrir carpeta de logs**: abre en el explorador de archivos la carpeta donde se guardan los archivos de log.

Los logs se rotan automáticamente cada 2 MB y se conservan hasta 3 archivos anteriores. Los archivos de sesiones anteriores quedan en `keytune.log.1`, `.2` y `.3` en la misma carpeta.

### Reproducción

La pestaña **Reproducción** controla el comportamiento de audio y el estado inicial de nuevas playlists:

- **Volumen predeterminado**: volumen al iniciar el reproductor (0-100).
- **Paso de volumen**: cuánto aumenta o disminuye el volumen cada pulsación de `Flecha arriba`/`Flecha abajo` (1-25).
- **Crossfade (segundos)**: superposición de audio entre pistas en la transición automática (0-12 s). Usa 0 para desactivarlo. El crossfade solo se aplica entre archivos de audio.
- **Paso de búsqueda (segundos)**: cuánto avanza o retrocede en el medio cada pulsación de `Flecha izquierda`/`Flecha derecha` (1-120 s).
- **Repetición predeterminada**: modo de repetición aplicado automáticamente a playlists nuevas. Las opciones son *Repetición desactivada*, *Repetir pista actual* y *Repetir playlist*.
- **Dispositivo de audio**: salida de sonido usada en la reproducción. *Predeterminado del sistema* sigue el dispositivo principal de Windows.
- **Activar aleatorio en nuevas playlists**: activa automáticamente el modo aleatorio en playlists creadas después de guardar.
- **Aplicar crossfade al cambiar de pista manualmente**: cuando está activado, el crossfade también se usa al avanzar o retroceder manualmente; de forma predeterminada solo vale al final natural de cada pista.
- **Desactivar salida de video (reproducir solo audio)**: mantiene la reproducción solo en audio, incluso en archivos de video. Útil para evitar ventanas externas de video.

### Accesibilidad

La pestaña **Accesibilidad** tiene una sola opción: **Activar anuncios de accesibilidad**. Cuando está activada, el reproductor anuncia cambios de tiempo, volumen, cambio de pestañas y estado al lector de pantalla. Cuando está desactivada, esos anuncios se suprimen. Los atajos de anuncio bajo demanda (`T`, `V`, `S`) siguen funcionando independientemente de esta configuración; consulta [Recursos de accesibilidad](#recursos-de-accesibilidad) para ver detalles.

### Recursos adicionales

La pestaña **Recursos adicionales** concentra las integraciones opcionales. Actualmente reúne los controles de YouTube Music y YouTube en dos secciones.

#### Integración con YouTube Music y YouTube

- **Activar recursos adicionales para YouTube Music y YouTube (yt-dlp y ytmusicapi)**: descarga y mantiene un ejecutable `yt-dlp` y los paquetes Python necesarios en una carpeta local. Sin esto, la pestaña de YouTube Music no funciona. En la primera ejecución, la descarga puede tardar algunos minutos y requiere internet. Al desactivar, los archivos ya descargados no se eliminan.
- **Actualizar automáticamente las dependencias de YouTube Music**: verifica y aplica actualizaciones en el intervalo definido abajo. Solo aparece cuando la opción anterior está activada.
- **Usar versión nightly de yt-dlp (recomendado)**: descarga builds nightly de `yt-dlp`. Recomendado porque YouTube y YouTube Music cambian los mecanismos de extracción con frecuencia y la nightly suele recibir correcciones antes que el canal estable. Solo aparece cuando la integración está activada.
- **Intervalo de actualización (horas)**: cada cuánto tiempo el reproductor intenta actualizar las dependencias cuando se abre la pestaña YouTube Music (1-720 h). Solo está disponible cuando la actualización automática está activada.

#### Biblioteca de YouTube Music

Esta sección solo aparece cuando la integración está activada.

- **Playlists cargadas por vez**: cuántas playlists de la biblioteca se traen en cada carga (5-200). Valores menores aceleran la apertura; al llegar al final de la lista el reproductor ofrece cargar más.
- **Mixes personalizadas para descubrir**: límite máximo de elementos recorridos en la página inicial de YouTube Music para encontrar mixes personalizadas (5-200). Valores menores hacen que la sincronización sea más rápida.
- **Reproducir contenido relacionado al final de la playlist (radio automática)**: cuando la última pista de YouTube Music termina naturalmente - o cuando pides la siguiente pista estando en la última -, el reproductor busca pistas relacionadas (la radio de YouTube Music) y continúa reproduciendo automáticamente. Para una transición continua, la búsqueda empieza poco antes del final de la última pista y el enlace de la siguiente ya se resuelve con anticipación, evitando una pausa mientras se descubre el contenido. También se puede activar o desactivar con la tecla `A` durante la reproducción.
- **Guardar canciones escuchadas en el historial de YouTube Music**: activada de forma predeterminada. Al escuchar una pista de YouTube Music durante el tiempo suficiente (cerca del 30% de la duración, entre 15 y 30 segundos), el reproductor marca esa pista como vista en el historial de tu cuenta de YouTube Music. Desactívala para reproducir pistas de YouTube Music sin registrar nada en el historial.

## Ecualizador

El ecualizador se abre por pestaña con `Ctrl+Shift+E`, así que cada playlist puede tener su propio ajuste.

En la práctica, esto permite dejar una playlist con graves reforzados y otra con un ajuste más neutro sin tener que rehacer todo cada vez que cambias de contexto.

### Cómo usar

Al abrir el ecualizador, el campo **Pestaña destino** muestra qué playlist recibirá los ajustes. Usa la casilla **Activar ecualizador en esta pestaña** para activar o desactivar el efecto solo en esa pestaña.

El campo **Preset** lista todos los presets disponibles. Los integrados aparecen con el sufijo *(integrado)*. Al seleccionar uno, el campo **Descripción** muestra una nota sobre el perfil sonoro y la sección **Resumen del preset** muestra los valores de preamplificación y de cada banda para revisarlos antes de aplicar.

#### Botones de gestión de presets

- **Nuevo...**: crea un preset personalizado desde cero. Abre el editor para que definas el nombre, la preamplificación y la ganancia de cada banda. Usa este botón cuando quieras una curva que no existe entre los presets integrados.
- **Editar...**: edita un preset personalizado ya existente. Este botón solo aparece así cuando el preset seleccionado es personalizado.
- **Guardar copia...**: cuando el preset seleccionado es integrado, el botón cambia de nombre a **Guardar copia...** y crea una versión editable basada en él. Usa este camino para partir de un preset integrado y ajustarlo.
- **Duplicar...**: crea una copia de un preset personalizado con un nuevo nombre, manteniendo el original intacto. No disponible para presets integrados.
- **Eliminar**: elimina permanentemente el preset personalizado seleccionado. No disponible para presets integrados.
- **Aplicar a todas las pestañas**: copia el preset y el estado de activación de la pestaña actual a todas las pestañas de medios abiertas.

#### Editor de preset

El editor muestra el campo de nombre, el control de preamplificación y un control por banda de frecuencia. Cada banda acepta valores de -12,0 dB a +12,0 dB. Los valores positivos refuerzan la frecuencia; los valores negativos atenúan. La preamplificación ajusta la ganancia general antes de todas las bandas.

### Presets integrados

KeyTune incluye 18 presets listos para usar:

| Preset | Perfil |
|---|---|
| Predeterminado | Curva neutra, mantiene el sonido original |
| Clásico | Realza definición y brillo sin exagerar los graves |
| Club | Graves y agudos más animados |
| Dance | Más impacto en los graves y brillo en la parte alta |
| Graves profundos | Prioriza subgraves y graves para dar peso al beat |
| Graves y agudos | Curva en V con graves fuertes y agudos brillantes |
| Agudos realzados | Destaca detalles, voces y brillo general |
| Auriculares | Equilibrio pensado para auriculares con sensación de claridad |
| Sala amplia | Crea una sensación más abierta y amplia |
| En vivo | Presencia de escenario y ambiente |
| Fiesta | Curva para volúmenes casuales y música animada |
| Pop | Voz, brillo y graves limpios |
| Reggae | Más cuerpo en los graves con medios relajados |
| Rock | Ataque de guitarras, caja y presencia general |
| Ska | Bajo firme con medios y agudos vivos |
| Suave | Escucha suave, reduce agresividad |
| Rock suave | Equilibrio con leve presencia de voz y brillo |
| Techno | Beat, subgrave y brillo electrónico |

### Consejos

- Reduce la preamplificación si el sonido empieza a distorsionar.
- Haz ajustes pequeños en las bandas para evitar exageraciones.
- Usa **Guardar copia...** sobre un preset integrado para partir de una curva lista y ajustar solo lo necesario.
- Usa **Duplicar...** en vez de editar directamente cuando quieras experimentar sin perder la versión anterior.

## YouTube Music

KeyTune incluye una pestaña dedicada a YouTube Music. Usa `Ctrl+Shift+Y` para abrirla. Funciona como una pestaña separada, así que puedes dejar la biblioteca local en una pestaña y YouTube Music en otra.

Para que la pestaña funcione, es necesario activar la integración en `Ctrl+,` > **Recursos adicionales** y conectar una cuenta.

La integración de YouTube Music depende de la forma en que cambia el sitio y de cómo `yt-dlp` interpreta esas páginas. Por eso, puede haber errores, fallas temporales e incluso paradas sin explicación aparente; cuando eso ocurra, normalmente es necesario actualizar las dependencias o intentar de nuevo más tarde.

### Cuenta y biblioteca

La sección **Cuenta y biblioteca** muestra el estado de la cuenta conectada, el resumen de la biblioteca cargada y el último mensaje de operación. Tiene tres botones:

- **Conectar cuenta...**: abre el diálogo para conectar una cuenta de YouTube Music o renovar la autenticación guardada.
- **Desconectar cuenta**: elimina la autenticación guardada de esta instalación.
- **Actualizar biblioteca**: vuelve a buscar las playlists y mixes disponibles en la cuenta conectada.

Debajo de la sección de cuenta queda la lista **Playlists y mixes** con todas las playlists y mixes de la biblioteca. Usa el campo **Filtro** para localizar elementos por nombre. El contador sobre la lista muestra cuántos elementos están visibles después del filtro. Debajo de la lista están las acciones:

- **Abrir selección**: abre la playlist o mix seleccionado en una nueva pestaña (`Enter` en la lista hace lo mismo).
- **Nueva playlist...**: crea una playlist nueva en tu cuenta. El reproductor pide el nombre y la privacidad (Privada, No listada o Pública). Consulta [Administrar playlists de YouTube Music](#administrar-playlists-de-youtube-music).
- **Eliminar playlist...**: elimina la playlist seleccionada de tu cuenta, con confirmación. Solo funciona en playlists que creaste; mixes, listas de éxitos y playlists de terceros no se pueden eliminar.
- **Cargar más playlists**: trae el siguiente lote cuando hay más playlists para cargar. También puedes presionar `Page Down` estando al final de la lista.

### Búsqueda en el catálogo y en YouTube

La sección **Búsqueda en el catálogo y en YouTube** está contraída de forma predeterminada. Expándela para buscar. Tiene:

- **Campo de búsqueda**: escribe lo que quieres buscar y presiona `Enter` o haz clic en **Buscar**.
- **Alcance**: elige dónde se hará la búsqueda. Las opciones disponibles son:
    - *YouTube Music - canciones*: pistas del catálogo de YouTube Music.
    - *YouTube Music - videos*: videoclips y contenido en video de YouTube Music.
    - *YouTube Music - playlists*: playlists del catálogo de YouTube Music.
    - *YouTube - videos*: videos de YouTube en general, sin exigir cuenta.
- **Explorar**: cuatro botones traen más contenido a la misma lista de resultados:
    - **En tendencia...**: abre un menú con *Global* en la parte superior y los demás países agrupados en submenús por continente. Al elegir un país, las listas de éxitos y los destacados en tendencia de YouTube Music aparecen en la lista, como playlists que puedes abrir o guardar en la biblioteca. No exige cuenta conectada.
    - **Moods y géneros...**: abre un menú con las categorías de moods y géneros de YouTube Music (por ejemplo *Enfoque*, *Entrenamiento*, *Pop*, *Rock*). Al elegir una categoría, sus playlists aparecen en la lista. No exige cuenta conectada.
    - **Me gusta**: carga las pistas marcadas con me gusta (la playlist *Liked Music* de tu cuenta). Exige cuenta conectada.
    - **Historial**: carga tu historial de reproducción de YouTube Music, desde la pista más reciente hasta la más antigua. Exige cuenta conectada.
- **Lista de resultados**: muestra los elementos encontrados (de la búsqueda, de las listas en tendencia, de moods y géneros, de los me gusta o del historial). La lista permite **selección múltiple**: usa `Ctrl+Flechas` para mover el foco sin alterar la selección, `Ctrl+Espacio` para marcar o desmarcar el elemento enfocado y `Shift+Flechas` para seleccionar un intervalo. `Enter` agrega la selección a la playlist actual; `Ctrl+Enter` abre la selección en una nueva playlist; `Shift+F10` o el botón **Acciones...** abre el menú contextual con opciones adicionales.
- **Guardar en Music**: guarda la selección en la biblioteca de YouTube Music cuando el resultado es compatible (playlists o pistas).

### Abrir playlist o video

La sección **Abrir playlist o video** también está contraída de forma predeterminada. Expándela para pegar un enlace de playlist, mix o video de YouTube Music o de YouTube. Haz clic en **Abrir enlace** o presiona `Enter` en el campo para abrir.

### Administrar playlists de YouTube Music

Además de abrir y guardar playlists, KeyTune permite editar tus playlists directamente en la cuenta conectada. Todas estas acciones exigen cuenta conectada y modifican la playlist **en tu cuenta de YouTube Music**; lo que involucra eliminar se confirma antes y el reproductor no puede deshacerlo.

**Agregar pistas a una playlist.** Selecciona una o más pistas de YouTube Music (en la playlist actual o en la lista de resultados de búsqueda) y usa **Agregar a playlist de YouTube Music...** en el menú contextual (`Shift+F10`), o presiona `Ctrl+Shift+A` para agregar la pista que está sonando. Aparece una lista de tus playlists editables; mixes y radios personalizadas no entran en esa lista porque no aceptan edición. En la parte superior de la lista está la opción **Crear nueva playlist...**, que crea una playlist nueva ya con la selección actual (el mismo comportamiento de la app de YouTube Music).

**Quitar pistas de una playlist.** Con una playlist tuya de YouTube Music abierta en la pestaña actual, selecciona las pistas y usa **Quitar de la playlist de YouTube Music** en el menú contextual. El reproductor pide confirmación y, al concluir, también quita las pistas de la pestaña abierta para que la lista siga reflejando la cuenta. La eliminación solo se ofrece en playlists que creaste o donde eres colaborador.

**Crear una playlist.** Usa **Nueva playlist...** en la sección *Playlists y mixes* para crear una playlist vacía, o **Crear nueva playlist...** en el diálogo de agregar pistas para crearla ya con la selección. En ambos casos el reproductor abre un diálogo donde informas el **nombre** y eliges la **privacidad**: *Privada* (solo tú la ves), *No listada* (visible para quien tenga el enlace) o *Pública* (aparece en tu perfil y puede aparecer en búsquedas). El valor predeterminado es Privada. Después de crearla, la biblioteca se actualiza para que la nueva playlist aparezca en la lista.

**Eliminar una playlist.** Selecciona la playlist en la lista *Playlists y mixes* y usa **Eliminar playlist...**. Solo se pueden eliminar playlists que creaste; el reproductor confirma antes y actualiza la biblioteca enseguida.

### Sesión de YouTube Music

#### Qué son las cookies

Las cookies son pequeños archivos de texto que los navegadores almacenan para recordar tus preferencias e información de inicio de sesión en sitios web. Cuando inicias sesión en YouTube Music, el navegador guarda cookies que contienen tu autenticación. Al exportar esas cookies, estás transfiriendo esa información de sesión iniciada a KeyTune, lo que permite que la aplicación acceda a tu cuenta sin pedir tu contraseña.

#### Por qué usar una ventana de incógnito

Usar una ventana de incógnito (también llamada navegación privada) es importante porque Google renueva constantemente las cookies en las ventanas normales. Si exportaras cookies de una sesión regular, se volverían inválidas rápidamente a medida que el navegador las renovara. En la ventana de incógnito, como la sesión no se sigue usando después de cerrarla, las cookies no se renuevan y permanecen válidas por mucho más tiempo.

#### Paso a paso: exportar cookies de YouTube Music

**Requisito previo:** instala la extensión [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) en tu navegador (funciona en Chrome, Edge y navegadores basados en Chromium).

**1. Activar la extensión en pestañas de incógnito**

Primero, configura la extensión para funcionar en pestañas privadas:

1. Presiona `Ctrl+L` para enfocar la barra de direcciones.
2. Presiona `Esc` para salir del cuadro de edición de la barra de direcciones.
3. Presiona `Alt+F` para abrir el menú del navegador.
4. Navega con las flechas hasta **Extensiones**, expande el submenú presionando `Enter` y elige **Administrar extensiones**.
5. Localiza **Get cookies.txt LOCALLY** y haz clic en **Detalles** (o "Más información").
6. En la página de detalles, localiza la opción **Permitir en pestañas privadas** o **Permitir en incógnito** y actívala.
7. Cierra la página y vuelve a tu navegador.

**2. Iniciar sesión y exportar cookies**

1. Abre una nueva pestaña de incógnito/privada (generalmente `Ctrl+Shift+N` o `Ctrl+Shift+P`).
2. Navega a [music.youtube.com](https://music.youtube.com/).
3. Inicia sesión con tu cuenta de Google y elige tu cuenta de música, si hay varias opciones.
4. Después de completar el inicio de sesión, presiona `Ctrl+L` para enfocar la barra de direcciones.
5. Presiona `Esc` para salir del cuadro de edición de la barra de direcciones (puede ser necesario).
6. Navega con `Tab` hasta alcanzar la sección de **Extensiones**. Expándela presionando `Enter`.
7. Continúa navegando con `Tab` hasta encontrar la extensión **Get cookies.txt LOCALLY** y haz clic en ella (o presiona `Enter`).
8. Se abrirá una página con las cookies. Busca el botón **Exportar** o **Download** (generalmente el primer botón de la página) y haz clic para descargar el archivo `cookies.txt`.
9. **Importante**: cierra la pestaña de incógnito **sin navegar a ningún otro sitio**. Esto garantiza que las cookies no se renueven.

**3. Importar en KeyTune**

1. En KeyTune, abre la pestaña de YouTube Music (`Ctrl+Shift+Y`).
2. En la sección **Cuenta y biblioteca**, haz clic en **Conectar cuenta...**.
3. Se abrirá un diálogo que ofrece la opción de importar una sesión. Elige el archivo `cookies.txt` que acabas de descargar.
4. La cuenta se conectará y podrás usar YouTube Music normalmente.

#### Información de seguridad

El archivo `cookies.txt` exportado contiene información de autenticación de tu cuenta. Por seguridad:

- Usa el archivo solo en tu propio equipo.
- No compartas el archivo con otras personas.
- Elimina el archivo después de importarlo en KeyTune si lo deseas (KeyTune mantiene una copia interna y segura).
- Si desconectas la cuenta en KeyTune, las cookies almacenadas se eliminarán.

### Atajos

- `Ctrl+Shift+Y`: abrir la pestaña de YouTube Music
- `Ctrl+Shift+A`: agregar el medio actual a una playlist de YouTube Music
- `Enter` en el campo de búsqueda: ejecutar la búsqueda
- `Enter` en la lista de resultados: agregar el elemento a la playlist actual
- `Ctrl+Enter` en la lista de resultados: abrir el elemento en una nueva playlist
- `Ctrl+Espacio` en la lista de resultados: marcar o desmarcar el elemento enfocado (selección múltiple)
- `Ctrl+Flechas` en la lista de resultados: mover el foco sin alterar la selección
- `Shift+Flechas` en la lista de resultados: seleccionar un intervalo de elementos
- `Shift+F10` en la lista de resultados: abrir el menú de acciones
- `Enter` en la lista de playlists de la biblioteca: abrir la selección
- `Page Down` al final de la lista de playlists: cargar más playlists
- `Esc`: cerrar la pestaña cuando esté enfocada

## Recursos de accesibilidad

La aplicación fue diseñada para lectores de pantalla y uso por teclado. En general:

- el foco evita saltos innecesarios al área nativa de video;
- los anuncios de estado y de navegación se hacen cuando el soporte de accesibilidad está disponible;
- los campos, botones y listas tienen nombres y descripciones legibles por lectores de pantalla.

Si usas lector de pantalla, los atajos de anuncio bajo demanda `T`, `V` y `S` (descritos en [Atajos de reproducción](#atajos-de-reproducción)) y la ayuda rápida `F1` ayudan a orientarte sin depender de los eventos automáticos.

Los anuncios automáticos, como cambio de pista, cambio de pestaña y alteración de volumen, se pueden activar o desactivar en `Ctrl+,` > **Accesibilidad**.

El panel de letras también está pensado para ese uso: `Ctrl+Alt+L` o la casilla **Letras** en el área de tiempo muestran u ocultan el panel, y el texto se puede leer, navegar con las flechas y copiar con el botón **Copiar letra completa**. Cuando cambia la pista, el reproductor intenta buscar la letra automáticamente primero en LRCLIB y después en YouTube Music.

## Actualizaciones

Al iniciar, KeyTune puede verificar actualizaciones automáticamente. Para verificar manualmente en cualquier momento, usa el menú **Ayuda > Buscar actualizaciones**.

Cuando haya una versión nueva, la aplicación muestra un diálogo con las notas del lanzamiento, el nombre del archivo y el tamaño de la descarga antes de pedir confirmación. Si aceptas, la aplicación descarga el paquete, muestra el avance de la descarga y pide permiso para instalar después de que el archivo esté listo. Si cancelas o cierras el diálogo, no se instala nada y el reproductor continúa funcionando normalmente.

## Solución de problemas

Si la aplicación no abre correctamente, primero confirma si la instalación se completó sin errores (reinstalar con el instalador más reciente resuelve la mayoría de los casos) y si el sistema tiene permiso para acceder a los archivos o carpetas que intentaste abrir.

Si el reproductor no encuentra el runtime de MPV, verifica si está en una de estas rutas: una carpeta `mpv/` junto al ejecutable, `MPV_HOME`, `MPV_DLL_DIR`, la caché guardada de la ejecución anterior o una instalación de Chocolatey compatible.

Si un medio no abre, prueba otro archivo local para separar un problema de ruta inválida, permiso o tipo de archivo incompatible.

Si la asociación de archivos no funciona como se esperaba, hay dos pasos separados que confirmar: primero, que KeyTune fue registrado como opción (durante la instalación o después en **Configuración > General > Registrar como reproductor predeterminado**); segundo, que fue elegido como aplicación predeterminada para esos formatos en la configuración de apps predeterminadas de Windows. El registro por sí solo no convierte a KeyTune automáticamente en el predeterminado.

Si la restauración de sesión falla, abre la app una vez sin depender de la sesión anterior y verifica si la configuración de ventana y carpeta se está guardando normalmente.

Si la pestaña de YouTube Music no carga o muestra errores de dependencias, abre `Ctrl+,` > **Recursos adicionales** y confirma que la opción **Activar recursos adicionales para YouTube Music y YouTube** esté marcada. La descarga inicial puede tardar algunos minutos y requiere internet. Si las dependencias ya están instaladas pero la búsqueda o la carga fallan, usa la versión nightly de `yt-dlp` en las mismas preferencias; suele recibir correcciones antes que el canal estable.

Si la sesión de YouTube Music expira o el reproductor pide autenticación de nuevo, exporta las cookies del navegador como se describe en la sección [Sesión de YouTube Music](#sesión-de-youtube-music) y reconecta la cuenta.

Para investigar otros problemas, activa el registro de logs en `Ctrl+,` > **General** > **Registro de logs**. Con **Registrar logs de diagnóstico** activado y el nivel ajustado a *Depuración*, el reproductor graba información detallada en `keytune.log` en la carpeta de datos. Usa **Abrir carpeta de logs** para localizar el archivo y, si necesitas reportar un problema, adjúntalo a la issue.

## Para desarrolladores

KeyTune es un proyecto de código abierto. El repositorio, issues, pull requests y releases están en [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). El fuente de este manual está en [docs/manual.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md).
