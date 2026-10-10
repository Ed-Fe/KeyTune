# Manual de KeyTune

KeyTune es un reproductor de medios pensado para usarse con el teclado, con la accesibilidad en primer lugar. Funciona bien con playlists, con la navegación por carpetas y con la vuelta al punto en el que lo dejaste la última vez.

Este proyecto se desarrolló con asistencia de IA, incluidos GitHub Copilot, Codex de OpenAI y Claude Code de Anthropic.

Aquí encontrarás las funciones de la aplicación y el paso a paso de las tareas más comunes. Si solo quieres empezar a escuchar, lee [Primeros pasos](#primeros-pasos) y [Cómo abrir medios](#como-abrir-medios). El resto sirve de consulta.

## Qué ofrece KeyTune

- Reproducción de audio y vídeo controlada con el teclado
- Playlists en pestañas, con una cola de reproducción independiente
- Explorador de carpetas junto a las pestañas
- Búsqueda en la playlist o en la carpeta actual, con navegación entre los resultados
- Biblioteca inteligente: búsqueda global, favoritos, valoraciones, historial y reanudación por archivo
- Temporizador con duraciones predefinidas o pausa al final de la pista
- Ecualizador para todas las pestañas o solo para una, con preajustes y presets propios
- Panel de letras con búsqueda automática
- Pestaña KeyTube, con YouTube Music y YouTube (`Ctrl+Shift+Y`)
- Transmisiones en vivo de YouTube, con audio y vídeo opcional
- Radios en línea de todo el mundo (`Ctrl+Shift+N`)
- Descarga de canciones y vídeos de YouTube (`Ctrl+Shift+B`)
- Conversión de audio y vídeo entre formatos (`Ctrl+Shift+K`)
- AutoDJ, que mezcla las pistas de la playlist
- Plugins y marketplace
- Restauración de lo que estaba abierto en la última sesión
- Anuncios para lectores de pantalla

## Primeros pasos

1. Descarga el `KeyTune-Setup.exe` más reciente desde la página de [releases](https://github.com/ed-fe/KeyTune/releases).
2. Ejecuta el instalador y sigue los pasos. En la página de tareas adicionales puedes crear un acceso directo en el escritorio y elegir qué formatos de audio, vídeo y playlist asociar a KeyTune. Todo es opcional y viene sin marcar. Asociar un formato añade KeyTune al menú *Abrir con*; para que abra esos archivos por sí solo, aún hay que definirlo como predeterminado en la configuración de Windows.
3. A partir de ahí, cuando haya una versión nueva, KeyTune muestra las novedades y pide confirmación antes de descargar e instalar (consulta [Actualizaciones](#actualizaciones)).

KeyTune reproduce los medios con el runtime de MPV, y el instalador ya lo incluye. Si el reproductor se abre pero no reproduce nada, consulta [Solución de problemas](#solucion-de-problemas).

## Interfaz

La primera vez que lo abres, la ventana muestra una pestaña de playlist vacía. Tiene estas áreas:

- **Barra de menús**, arriba: **Archivo**, **Reproducción**, **Ver**, **Biblioteca**, **Pestañas**, **Configuración** y **Ayuda**.
- **Área de pestañas**, que ocupa casi toda la ventana. Cada pestaña es una playlist (consulta [Playlists, carpetas y pestañas](#playlists-carpetas-y-pestanas)) y se divide en dos partes lado a lado: a la izquierda, el navegador de elementos, que es la lista de la playlist; a la derecha, el área del reproductor. Para un vídeo, el área del reproductor muestra el cuadro de vídeo. Para audio, o sin nada cargado, muestra un texto de apoyo con los atajos más usados.
- **Explorador de carpetas**, a la izquierda de las pestañas cuando se abre con `Ctrl+E`. Muestra las carpetas y los archivos de medios del equipo (consulta [Explorador de carpetas](#explorador-de-carpetas)).
- **Panel de tiempo**, debajo de las pestañas: tiempo transcurrido, duración, barra de progreso y un resumen de los atajos principales.
- **Barra de estado**, en el borde inferior: el resultado de la última acción.

`Tab` o `Ctrl+B` alternan el foco entre el navegador de elementos y el reproductor (con el explorador abierto, `Tab` también pasa por él). `F1`, en cualquier momento, abre la ayuda rápida de atajos.

## Cómo abrir medios

Hay tres formas de poner medios en KeyTune: abrir, pegar y usar el explorador de carpetas. Las tres funcionan igual: lo que entra va a la **playlist actual** y empieza a sonar. Con `Shift`, entra **sin reproducir**, al final de la lista, y lo que sonaba continúa.

| Para | Reproduciendo | Sin reproducir |
| --- | --- | --- |
| Elegir archivos | `Ctrl+O` (**Archivo > Abrir...**) | `Ctrl+Shift+O` (**Archivo > Abrir sin reproducir...**) |
| Pegar del portapapeles | `Ctrl+V` | `Ctrl+Shift+V` |
| Usar el explorador de carpetas | `Enter` | `Shift+Enter` |

- Un archivo `.m3u` o `.m3u8` abierto con `Ctrl+O` se convierte en una playlist.
- `Ctrl+V` acepta enlaces, rutas en texto y archivos o carpetas copiados en el Explorador de archivos de Windows. De una carpeta entran todos los medios, incluidos los de las subcarpetas. Los enlaces de playlist de YouTube Music se reconocen por el parámetro `list=` y se abren como la playlist completa.

Para empezar una lista aparte, crea una playlist nueva con `Ctrl+T` y abre o pega en ella. Para abrir un enlace, cópialo y usa `Ctrl+V`.

Formatos de medios compatibles directamente:

- Audio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Vídeo: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

**Archivo > Recientes** guarda, en listas separadas, los últimos archivos, carpetas y playlists que usaste.

### Escuchar un archivo directamente desde el Explorador de archivos de Windows

Con KeyTune definido como reproductor predeterminado, `Enter` sobre un archivo de audio en el Explorador de archivos abre el **reproductor rápido**: una ventana pequeña que reproduce el archivo al momento, sin cargar pestañas, playlists ni la sesión anterior.

1. En el Explorador de archivos, selecciona el archivo y pulsa `Enter`.
2. Escucha. El lector de pantalla anuncia el nombre del archivo en el título de la ventana.
3. Pulsa `Esc` o `Alt+F4` para cerrar.

`Enter` sobre otro archivo, con el reproductor rápido abierto, cambia lo que suena por el archivo nuevo, en la misma ventana. El foco sigue en el Explorador de archivos, y KeyTune no anuncia nada: oyes empezar el archivo nuevo.

| Acción | Atajo |
| --- | --- |
| Reproducir o pausar | `Espacio` |
| Retroceder o avanzar | `Flecha izquierda` / `Flecha derecha` |
| Retroceder o avanzar 1 minuto | `Shift+Flecha izquierda` / `Shift+Flecha derecha` |
| Volumen | `Flecha arriba` / `Flecha abajo` |
| Ir al inicio o al final | `Home` / `End` |
| Velocidad | `]` aumenta, `[` disminuye, `\` vuelve a la normal |
| Oír el tiempo, el volumen o el estado | `T` / `V` / `S` |
| Continuar en KeyTune completo | `Ctrl+Enter` (o el botón **Continuar en KeyTune completo**) |
| Cerrar | `Esc` o `Alt+F4` |

Las teclas y los anuncios son los mismos del reproductor de la ventana principal: cambiar el volumen o avanzar no dice nada, y `V` y `T` dicen el volumen y el tiempo cuando quieras.

`Ctrl+Enter` abre la ventana principal y lleva el medio a una playlist nueva. El sonido no se interrumpe: el medio sigue sonando desde donde estaba, con el mismo volumen y la misma velocidad, mientras vuelven las pestañas de la última sesión. Abrir KeyTune desde el menú Inicio con el reproductor rápido abierto hace lo mismo.

El reproductor rápido no guarda nada: el archivo no entra en los recientes, en el historial ni en la sesión, y el volumen cambiado en él vale solo hasta cerrarlo o hasta continuar en KeyTune completo, que lo mantiene. Empieza con el volumen de la última sesión, o con el volumen predeterminado si la sesión no se restaura.

Se abren directamente en la ventana principal, como antes: playlists `.m3u` y `.m3u8`, vídeos cuando la salida de vídeo está activada, y cualquier archivo cuando KeyTune completo ya está abierto (va a la playlist actual). Para usar siempre la ventana principal, desmarca **Usar el reproductor rápido al abrir archivos desde Windows** en `Ctrl+,` > **General**.

## Reproducción

### Atajos de reproducción

| Tecla | Qué hace |
| --- | --- |
| `Espacio` | Reproducir o pausar |
| `Enter` | Con el foco en el reproductor, reproducir la playlist de la pestaña a la vista, desde donde se detuvo |
| `Flecha izquierda` / `Flecha derecha` | Retroceder o avanzar en el medio (el paso se configura en **Preferencias > Reproducción**) |
| `Shift+Flecha izquierda` / `Shift+Flecha derecha` | Retroceder o avanzar 1 minuto |
| `Inicio` / `Fin` | Ir al principio o al final del medio |
| `Flecha arriba` / `Flecha abajo` | Subir o bajar el volumen |
| `Ctrl+.` | Detener |
| `Ctrl+RePág` / `Ctrl+AvPág` | Pista anterior o siguiente |
| `Alt+Flecha izquierda` / `Alt+Flecha derecha` | Lo mismo, como alternativa |
| `Alt+Flecha arriba` / `Alt+Flecha abajo` | Mover el elemento actual hacia arriba o hacia abajo en la playlist |
| `Alt+Inicio` / `Alt+Fin` | Ir al primer o al último elemento de la playlist |
| `E` | Alternar el modo aleatorio |
| `R` | Alternar el modo de repetición |
| `]` / `[` | Subir o bajar la velocidad |
| `\` | Volver a la velocidad normal |
| `Shift+]` / `Shift+[` | Subir o bajar el tono, en semitonos |
| `Shift+\` | Volver al tono original |
| `Alt+D` | Elegir la salida de audio |
| `Ctrl+Alt+L` | Mostrar u ocultar el panel de letras |
| `Ctrl+Alt+V` | Alternar el vídeo de las transmisiones en vivo |
| `Ctrl+Shift+F` | Poner el elemento seleccionado en la cola |
| `Ctrl+Shift+Q` | Gestionar la cola |
| `Ctrl+Shift+D` | Configurar el temporizador |
| `T`, `V`, `S` | Anunciar el tiempo, el volumen y el estado |

Los atajos de YouTube Music, de descargar y de convertir están en [KeyTube](#keytube-youtube-y-youtube-music), [Descargar de YouTube](#descargar-de-youtube) y [Convertir medios](#convertir-medios).

`Ctrl+W` cierra la pestaña activa. `Ctrl+Shift+W` cierra, o descarga de memoria, solo el medio actual.

### Cola de reproducción

La cola define qué suena después de la pista actual, sin depender del orden de la playlist que estás viendo. Siempre pertenece a la playlist que está sonando.

`Ctrl+Shift+F` (o **Reproducción > Agregar a la cola de reproducción**) pone un elemento en la cola o lo quita. `Ctrl+Shift+Q` (o **Reproducción > Gestionar cola de reproducción**) muestra la cola y deja quitar, reordenar o vaciar.

### Temporizador

El temporizador pausa la reproducción pasado un tiempo acordado, útil para escuchar algo antes de dormir. **Pausa** en lugar de detener: la posición queda guardada y `Espacio` continúa desde donde se quedó.

Ábrelo con `Ctrl+Shift+D` o **Reproducción > Temporizador**. Las opciones:

- **Duraciones predefinidas**: 5, 10, 15, 30, 45, 60, 90 o 120 minutos, directamente en el submenú.
- **Tiempo personalizado**: de 1 a 720 minutos, en el cuadro de configuración.
- **Al final de la pista actual**: la reproducción termina cuando acabe la pista, sin avanzar, sin repetir y sin traer contenido relacionado. No vale para transmisiones en vivo.
- **No usar temporizador**: cancela la programación.

El submenú también tiene **Tiempo restante** y **Cancelar temporizador**. El reproductor avisa cuando faltan 5 minutos y cuando falta 1.

### Letras

`Ctrl+Alt+L`, o la casilla **Letras** del panel de tiempo, muestra u oculta el panel de letras. Al cambiar de pista, KeyTune busca la letra por sí solo, primero en LRCLIB y después en YouTube Music. El botón **Copiar letra completa** lleva el texto al portapapeles.

## Playlists, carpetas y pestañas

Cada playlist vive en una pestaña, lo que ayuda a separar contextos: una lista para escuchar ahora, una colección organizada, una de pruebas. La pestaña a la vista decide qué aparece en el navegador de elementos.

Cambiar de pestaña no toca lo que está sonando: puedes recorrer las playlists, o crear una nueva con `Ctrl+T`, sin interrumpir la música. Una playlist solo asume la reproducción cuando reproduces algo en ella.

- `Enter` sobre un elemento lo reproduce, y su playlist pasa a ser la que suena.
- Cada playlist guarda la pista y la posición en que se detuvo. `Enter` sobre esa pista, en una playlist que no es la que suena, retoma desde ese punto en vez de empezar de nuevo.
- `Espacio`, las flechas de avance y de volumen, **Siguiente** y **Anterior** actúan siempre sobre lo que está sonando, sea cual sea la pestaña a la vista. Si no hay nada cargado, `Espacio` retoma la playlist a la vista.
- `Enter`, con el foco en el reproductor, pasa la reproducción a la playlist a la vista: vuelve a sonar desde donde se había detenido, y la que sonaba guarda su posición.
- Aleatorio y repetición también valen para la playlist que está sonando. Si no hay nada cargado, valen para la playlist a la vista.
- El título de la ventana y el estado (`S`) dicen qué está sonando. `S` también dice la pestaña a la vista cuando es otra.

### Atajos de pestañas y elementos

- `Ctrl+T`: nueva pestaña de playlist
- `Ctrl+W`: cerrar la pestaña actual
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: pestaña siguiente o anterior
- `Ctrl+Shift+E`: ecualizador
- `Ctrl+C`: copiar la selección como texto y, en el caso de archivos del equipo, también como archivos. Se puede pegar en otra playlist, en un campo de texto o en el Explorador de Windows
- `Ctrl+Shift+C`: copiar el enlace o la ruta del medio actual (en el explorador de carpetas, la ruta de la selección)
- `Ctrl+Shift+S`: guardar la playlist actual
- `Ctrl+B`: alternar el foco entre el navegador de elementos y el reproductor
- `Ctrl+F`: buscar un elemento en la playlist o en la carpeta actual
- `Ctrl+G`: buscar en toda la biblioteca
- `Ctrl+D`: marcar o desmarcar como favorita la selección
- `Ctrl+0` a `Ctrl+5`: valorar la selección de cero a cinco estrellas
- `Ctrl+Shift+H`: historial de reproducción
- `Ctrl+Shift+R`: seguir escuchando lo que quedó a medias
- `F3` / `Shift+F3`: resultado siguiente o anterior de la búsqueda

### Navegador de elementos

El navegador está a la izquierda de cada pestaña y lista los elementos de la playlist. Lo que está sonando lleva `▶` al principio de la línea.

- `Enter`: reproduce el elemento seleccionado.
- `Delete`: quita el elemento de la playlist.
- `Shift+F10`: abre el menú contextual del elemento o de la selección. Además de copiar, pegar (reproduciendo o no) y quitar, el menú trae las acciones de YouTube cuando la selección tiene elementos de ese origen: **Me gusta**, **No me gusta**, **Ver detalles**, **Ver comentarios** y **Agregar a la playlist de YouTube Music...**. Cuando la pestaña es una playlist tuya de YouTube Music, también aparece **Quitar de la playlist de YouTube Music**. Consulta [Gestionar playlists de YouTube Music](#gestionar-playlists-de-youtube-music).
- `Tab` o `Esc`: devuelve el foco al reproductor.

### Cómo funcionan las listas

El explorador de carpetas, KeyTube y las radios en línea se recorren del mismo modo: entras en los elementos, ves lo que hay dentro y vuelves. Las teclas son las mismas en los tres.

- `Enter`: entra en el elemento cuando contiene otros elementos (una carpeta, un canal, un artista, un país) y **reproduce** cuando es algo que suena (un archivo, una pista, un vídeo, una radio). Los álbumes y las playlists entran completos en la playlist actual.
- `Shift+Enter`: añade a la playlist actual **sin reproducir**.
- `Flecha derecha`: muestra lo que hay dentro del elemento, en la misma lista, incluso cuando `Enter` reproduciría.
- `Retroceso`: vuelve a la lista anterior, con la selección en el elemento que habías abierto. En KeyTube y en las radios, `Flecha izquierda` y `Alt+Flecha izquierda` también vuelven.
- `Flecha abajo` o `AvPág` en el último elemento: carga más, en KeyTube y en las radios.
- Letras: saltan al elemento que empieza por ellas.
- `Shift+F10`, la tecla Aplicaciones o el botón derecho del ratón: abren el menú de acciones del elemento.
- Selección múltiple: `Shift+Flechas` seleccionan un intervalo y `Ctrl+Flechas` mueven el foco sin cambiar la selección. `Ctrl+Espacio` marca o desmarca el elemento con el foco (en el explorador, `Ctrl+Espacio` abre la ordenación).

### Explorador de carpetas

`Ctrl+E` (o **Archivo > Explorador de carpetas**) abre, a la izquierda de las pestañas, la lista de carpetas y de archivos de medios del equipo. No ocupa una pestaña: se queda junto a cualquier playlist y sirve para montarla poco a poco, sin interrumpir lo que suena. Con el foco en él, `Ctrl+E` cierra la lista; con el foco en otro sitio, lleva el foco hasta ella.

Empieza en **Este equipo**, con las carpetas Música, Vídeos, Descargas, Escritorio y Documentos y las unidades de disco. La carpeta en la que te quedaste y la ordenación elegida quedan guardadas para la próxima vez, y las carpetas de **Archivo > Recientes > Carpetas recientes** también se abren aquí.

Además de las teclas de [Cómo funcionan las listas](#como-funcionan-las-listas):

- `Enter` entra en la carpeta o reproduce el archivo, añadiéndolo a la playlist actual. Con `Shift+Enter`, de una carpeta entran todos los medios, incluidos los de las subcarpetas.
- `Ctrl+Shift+F` añade la selección a la cola, y `Ctrl+Shift+K` convierte los archivos seleccionados (consulta [Convertir medios](#convertir-medios)).
- `Retroceso` sube a la carpeta superior.
- `Ctrl+C` copia los archivos o carpetas seleccionados, para pegar en una playlist o en el Explorador de Windows. `Ctrl+Shift+C` copia las rutas como texto.
- `Ctrl+Espacio` abre el menú de ordenación: por nombre, fecha de modificación, fecha de creación, tipo o tamaño, en orden ascendente o descendente.
- `F5` actualiza la carpeta.
- `Shift+F10` abre el menú con todas las acciones: **Reproducir ahora**, **Añadir a la playlist sin reproducir**, **Añadir a la cola de reproducción**, **Abrir en una playlist nueva**, **Añadir toda la carpeta actual a la playlist**, **Convertir selección...**, **Indexar carpeta en la biblioteca**, **Copiar**, **Copiar ruta**, **Mostrar en el Explorador de archivos de Windows**, la ordenación, **Actualizar** y **Cerrar explorador**.
- `Esc` devuelve el foco a donde estaba antes de que abrieras el explorador.

### Buscar elementos

**Escritura rápida.** En la playlist y en el explorador, escribir letras o números lleva la selección al primer elemento cuyo nombre empieza por lo que escribiste. La búsqueda ignora los acentos y las mayúsculas. Tras un segundo sin escribir, la siguiente letra empieza una búsqueda nueva.

**Búsqueda completa.** Para listas grandes, usa `Ctrl+F` (o **Ver > Localizar elemento...**), que encuentra el texto en **cualquier parte** del nombre, y no solo al principio.

- `Ctrl+F` abre el cuadro **Localizar elemento**. Escribe el texto y confirma con `Enter` o con el botón **Localizar**.
- `F3` va al resultado siguiente y `Shift+F3`, al anterior. El menú **Ver** tiene los mismos comandos.
- La búsqueda recorre los elementos de la pestaña activa: playlists, carpetas y listas de KeyTube.
- `F3` repite la última búsqueda sin abrir el cuadro. Si todavía no hubo ninguna búsqueda, abre el cuadro.

## Descargar y convertir

### Descargar de YouTube

`Ctrl+Shift+B` descarga canciones y vídeos de YouTube y de YouTube Music. Sigue la misma regla que `Ctrl+Shift+K` (convertir): con el foco en una lista (la playlist o los resultados de KeyTube), descarga la **selección**; con el foco en el reproductor, descarga el **medio actual**. Los mismos comandos están en **Archivo > Descargar de YouTube**: **Descargar medio actual**, **Descargar selección** y **Descargar playlist completa**. La descarga usa `yt-dlp`, el mismo que ya reproduce esos medios, y ocurre en segundo plano: la reproducción continúa con normalidad.

1. Selecciona lo que quieres descargar, o deja el foco en el reproductor para descargar el medio actual.
2. Pulsa `Ctrl+Shift+B`.
3. En el diálogo, elige **Audio** o **Vídeo**, la calidad, la frecuencia de muestreo (solo para audio convertido) y la carpeta. Tu última elección pasa a ser el valor predeterminado de las Preferencias.
4. Confirma.

Cosas que conviene saber:

- **Sin diálogo.** Desmarca **Mostrar siempre este diálogo al descargar** para que las próximas descargas empiecen directamente, con las opciones de la pestaña **Descarga** de las Preferencias.
- **Calidad no disponible.** Si la calidad elegida no existe para ese medio, KeyTune descarga en la original y te avisa.
- **Nombre del archivo.** El archivo recibe el mismo nombre que KeyTune muestra para la pista (`Artista — Título.mp3`). Una descarga nunca reemplaza un archivo que ya está en la carpeta: si el nombre existe, el nuevo recibe « (2)», « (3)» y así sucesivamente.
- **Progreso.** Pulsa `Ctrl+Shift+B` otra vez durante una descarga para oír el progreso o cancelar.
- **FFmpeg.** Convertir el audio (MP3, FLAC u otra frecuencia de muestreo) y descargar vídeo en alta resolución exigen FFmpeg. Si no se encuentra, KeyTune pregunta si puede descargarlo (unos 90 MB). Si lo rechazas, la descarga continúa en la calidad original, sin conversión. También se usa un FFmpeg ya instalado en el sistema.

**Varios elementos a la vez.** **Descargar selección** descarga los elementos seleccionados, y **Descargar playlist completa** descarga todos los de la pestaña en una subcarpeta con el nombre de la playlist. Los dos están en **Archivo > Descargar de YouTube** y en el menú contextual de la lista. KeyTune pide confirmación antes de empezar.

Los elementos se descargan de uno en uno, con las mismas opciones. Al final, el reproductor resume cuántos salieron bien y cuántos fallaron, y `Ctrl+Shift+B` informa de la posición y permite cancelar. Un elemento que falla no interrumpe a los demás, y KeyTune ofrece una lista con cada fallo y su motivo, con el botón **Copiar lista**. Una cola admite como máximo 200 elementos.

Solo se pueden descargar medios de YouTube y de YouTube Music, de uno en uno.

### Convertir medios

KeyTune convierte archivos de audio y de vídeo del equipo sin salir del reproductor. `Ctrl+Shift+K` sigue la misma regla que `Ctrl+Shift+B`: con el foco en una lista (la playlist o el explorador de carpetas), convierte la **selección**; con el foco en el reproductor, convierte el **medio actual**. Los mismos comandos están en **Archivo > Convertir** (**Convertir medio actual** y **Convertir selección**) y en el menú contextual de las listas.

KeyTune pregunta qué hacer y muestra solo las opciones que sirven para el tipo de archivo:

- **Audio a vídeo**: genera un vídeo a partir del audio, con una imagen fija. Elige MP4, MKV o WebM y la resolución (480p, 720p o 1080p). Si el audio tiene una carátula de álbum incrustada, esta se convierte en la imagen; sin carátula, el fondo es negro.
- **Vídeo a audio**: extrae el sonido del vídeo a MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC o WAV.
- **Audio a otro formato de audio**: convierte entre MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC y WAV. La carátula y la información de la pista acompañan la conversión a MP3, M4A y FLAC.
- **Vídeo a otro formato de vídeo**: cambia solo el formato (MP4, MKV, WebM, AVI o MOV). Las pistas compatibles con el nuevo formato se copian sin recodificar, lo cual es rápido y no pierde calidad; las incompatibles se recodifican. Los subtítulos solo se conservan en MKV.

En el diálogo, además del formato, defines:

- la calidad de los formatos con pérdida (128, 192, 256 o 320 kbps);
- la frecuencia de muestreo (original, 44100 o 48000 Hz; Opus siempre usa 48000 Hz);
- dónde guardar: **Misma carpeta del archivo original** (el valor predeterminado) u **Otra carpeta**, que habilita el campo de la carpeta y el botón **Elegir carpeta**.

El diálogo recuerda tus últimas elecciones. El archivo original nunca se modifica ni se sobrescribe: si ya existe un archivo con el mismo nombre, el nuevo recibe « (1)», « (2)» y así sucesivamente.

**Varios archivos.** Selecciónalos en la playlist o en el explorador y pulsa `Ctrl+Shift+K`. KeyTune pregunta el modo y muestra a cuántos archivos se aplica cada uno. Solo se convierten los del tipo correcto. Las opciones valen para todos. Con **Misma carpeta del archivo original**, cada archivo va a la carpeta de su propio original; con **Otra carpeta**, todos van a la carpeta elegida. Los archivos se convierten de uno en uno, con un resumen al final. Un error en un archivo no interrumpe a los demás, y la lista de fallos se puede abrir y copiar, como en las descargas.

La conversión se ejecuta en segundo plano, y la reproducción continúa. Pulsa `Ctrl+Shift+K` durante una conversión para oír el progreso o cancelar; nunca se deja un archivo incompleto.

La conversión usa FFmpeg, el mismo de la descarga. Si no se encuentra, KeyTune pregunta si puede descargarlo, como se describe en [Descargar de YouTube](#descargar-de-youtube). Solo se convierten archivos del equipo; para medios de YouTube, usa `Ctrl+Shift+B`.

## Biblioteca inteligente

Mientras `Ctrl+F` busca en la lista que está abierta, la **biblioteca inteligente** recuerda lo que ya abriste y escuchaste y lo deja todo disponible para buscar de una vez. También guarda favoritos, valoraciones, el historial de reproducción y el punto en el que se quedó cada medio largo.

Todo queda en una base de datos local (`smart_library.db`), en la misma carpeta de datos de las preferencias. Nada sale de tu equipo, y la función entera se puede desactivar en `Ctrl+,` > **Biblioteca**. El menú **Biblioteca** reúne los comandos.

### Qué entra en el índice

- Los medios de cualquier playlist o carpeta que abres entran en el índice, en segundo plano.
- **Biblioteca > Indexar una carpeta en la biblioteca...** recorre una carpeta y sus subcarpetas.
- **Biblioteca > Actualizar las carpetas indexadas** vuelve a recorrer las carpetas ya indexadas y descarta los archivos que ya no existen.
- **Biblioteca > Resumen de la biblioteca** anuncia cuántos medios, carpetas, favoritos y reproducciones hay guardados.
- **Biblioteca > Vaciar la biblioteca...** borra todo (índice, favoritos, valoraciones, historial y reanudación), con confirmación.

Si prefieres que solo las carpetas que elijas entren en el índice, desactiva **Indexar automáticamente las carpetas abiertas en el navegador** en las preferencias. Navegar por el explorador no indexa nada por sí solo: entran en el índice las carpetas abiertas desde Recientes y las que indexes desde el menú contextual del explorador.

### Búsqueda global

`Ctrl+G` abre el cuadro **Buscar en la biblioteca**. Escribe el texto y confirma con `Enter` o con el botón **Buscar**.

- La búsqueda ignora los acentos y las mayúsculas, y cada palabra escrita debe aparecer en algún lugar del nombre del elemento o de la carpeta.
- El campo **Filtrar** limita la búsqueda a **Todo en la biblioteca**, **Solo favoritos**, **Solo valorados** o **Solo ya reproducidos**. Los tres últimos funcionan incluso con el texto vacío.
- Los resultados llegan en una lista con columnas de elemento, valoración y carpeta.
- La búsqueda es instantánea incluso con decenas de miles de archivos. Coincide con el principio de cada palabra («estrad» encuentra «Estrada») y, si no aparece nada, también busca en medio de la palabra («onita» encuentra «Bonita»).
- `Enter` (o el botón **Reproducir**) abre **todos** los resultados en una playlist nueva y empieza por la pista seleccionada, de modo que una búsqueda se convierte en una lista utilizable.
- **Agregar a la cola** pone en cola solo el elemento seleccionado, en la playlist que está sonando.

### Favoritos y valoraciones

Los comandos actúan sobre lo que esté seleccionado en la lista; sin selección, actúan sobre el medio que está sonando.

- `Ctrl+D`: marca o desmarca como favorito.
- `Ctrl+0` a `Ctrl+5`: da de cero a cinco estrellas.
- **Biblioteca > Anunciar las marcas de la selección**: lee el favorito, la valoración y el número de reproducciones del elemento.
- **Biblioteca > Abrir favoritos en una lista nueva**: monta una playlist con todo lo que marcaste como favorito.

Los mismos comandos están en el menú contextual de la lista (`Shift+F10`).

El favorito y la valoración aparecen junto al nombre, en la propia lista, por ejemplo `Estrada — favorito, 5 estrellas`, tanto en las playlists como en el explorador de carpetas. Así el lector de pantalla dice la marca junto con el elemento.

### Historial de reproducción

`Ctrl+Shift+H` abre el **Historial de reproducción**. El campo **Ver** elige entre tres vistas, y las columnas cambian con ella:

- **Todas las reproducciones**: una línea por cada vez que sonó el medio, con cuándo sonó, dónde se detuvo y el origen (playlist local, carpeta, medio remoto o YouTube Music).
- **Agrupado por medio**: una línea por medio, con cuántas veces sonó, la última vez y las marcas.
- **Más reproducidas**: la misma agrupación, de la más reproducida a la menos reproducida.

**Filtrar por texto** reduce la lista. `Enter` (o **Reproducir**) vuelve a reproducir, y **Agregar a la cola** pone en cola. **Quitar la entrada** saca una reproducción de la lista sin borrar el medio del índice; en las vistas agrupadas el botón pasa a ser **Quitar del historial** y borra todas las reproducciones de ese medio. **Vaciar el historial** borra todo, con confirmación.

Una pista solo entra en el historial después de sonar lo bastante para contar como escuchada, y las entradas más antiguas salen cuando el historial supera el límite de las preferencias.

Este historial es local y no tiene relación con **Guardar lo que escuché en el historial de YouTube Music**, que se registra en tu cuenta de YouTube Music.

### Reanudar donde lo dejaste

Los podcasts, audiolibros y vídeos largos vuelven a sonar desde el punto en el que se detuvieron. La regla es conservadora a propósito:

- vale solo para archivos locales, porque los streams no tienen una línea de tiempo estable entre sesiones;
- vale solo para medios que superan la **duración mínima** configurada (10 minutos, por defecto);
- detenerse dentro del **margen** configurado (30 segundos, por defecto) del principio o del final no crea un punto de reanudación;
- llegar al final de la pista borra la marca, y la próxima vez empieza desde el principio.

**Biblioteca > Continuar escuchando** (`Ctrl+Shift+R`) abre una playlist con todo lo que quedó a medias, del más reciente al más antiguo, y cada elemento muestra dónde se detuvo. **Biblioteca > Borrar las posiciones de reanudación** las borra todas de una vez.

### Listas inteligentes

Una lista inteligente es una regla guardada, no una lista fija. Se monta cada vez que la abres, así que sigue los cambios de valoración y de historial: «cinco estrellas que no escucho desde hace 30 días» sigue siendo correcta un mes después, por sí sola.

**Biblioteca > Listas inteligentes** muestra las reglas guardadas, para abrir con un solo comando, y **Gestionar listas inteligentes...** crea, edita y elimina. En el editor, todo son campos de teclado, sin constructor visual:

- **Solo favoritos** y **Valoración mínima** filtran por tus marcas.
- **Sin reproducir desde hace al menos (días)** encuentra lo que anda olvidado, e **Incluir medios nunca reproducidos** decide si lo que nunca sonó entra también.
- **Reproducciones mínimas** va por el otro lado: solo lo que ya escuchaste mucho.
- **Limitar a la carpeta** restringe a una carpeta y a todo lo que está debajo de ella.
- **Incluir medios remotos** trae también enlaces de YouTube Music y radios, que por defecto quedan fuera.
- **Ordenar por** y **Número máximo de elementos** definen qué sale y en qué orden.

Cada cambio actualiza el **Resumen de la regla**, al final del cuadro, en una frase: la forma más rápida de comprobar qué reunirá la regla antes de guardar.

## KeyTube: YouTube y YouTube Music

KeyTube es la central de KeyTune para YouTube Music y el YouTube normal. En las versiones hasta la 2.0.6 se llamaba YouTube Music y se ocupaba solo de la música; hoy reúne también vídeos, canales, suscripciones y comentarios de YouTube. Ábrela con `Ctrl+Shift+Y` (o **Ver > KeyTube por pestaña**). Es una pestaña aparte, así que puedes dejar la biblioteca local en una y KeyTube en otra.

Para que la pestaña funcione, activa la integración en `Ctrl+,` > **Recursos adicionales** y conecta una cuenta de YouTube. La misma cuenta sirve para YouTube y para YouTube Music.

La integración depende de cómo cambia el sitio y de cómo `yt-dlp` lee esas páginas. Por eso pueden producirse errores, fallos temporales y paradas sin explicación aparente. Cuando ocurre, normalmente basta con actualizar las dependencias o intentarlo más tarde.

### Cuenta y biblioteca

La pestaña tiene dos partes. Arriba, la sección **Cuenta y biblioteca**; abajo, el campo de búsqueda y **una sola lista**, por la que pasa todo lo demás: tu biblioteca, la búsqueda y lo que hay dentro de cada elemento.

**Cuenta y biblioteca** muestra la cuenta conectada, el resumen de la biblioteca cargada y el último mensaje de operación. Los botones:

- **Conectar cuenta...**: abre el diálogo para conectar una cuenta o renovar la autenticación guardada.
- **Desconectar cuenta**: quita la autenticación guardada en esta instalación.
- **Actualizar biblioteca**: vuelve a buscar las playlists y mixes de la cuenta y actualiza las valoraciones de canciones visibles en la cuenta.
- **Nueva playlist...**: crea una playlist en tu cuenta. El reproductor pide el nombre y la privacidad (consulta [Gestionar playlists de YouTube Music](#gestionar-playlists-de-youtube-music)).

**Me gusta** y **No me gusta** se envían a la cuenta conectada, así que aparecen también en YouTube Music del móvil y de otros dispositivos. KeyTune quita las pistas marcadas como «no me gusta» de las playlists y radios de la cuenta. Una valoración hecha fuera de KeyTune solo se detecta cuando la pista vuelve a aparecer; **Actualizar biblioteca** fuerza la comprobación.

### La lista

La lista funciona como el explorador de carpetas (consulta [Cómo funcionan las listas](#como-funcionan-las-listas)) y empieza en **Inicio**, con siete elementos:

- **Tus playlists y mixes**: las de la cuenta conectada. `Enter` abre la playlist en una pestaña propia, desde donde se puede editar en la cuenta; `Flecha derecha` muestra las pistas en la propia lista. Requiere cuenta conectada.
- **Me gusta**: las pistas con «me gusta» (la playlist *Me gusta* de tu cuenta). Requiere cuenta conectada.
- **Historial**: tu historial de reproducción de YouTube Music. Requiere cuenta conectada.
- **Videos de las suscripciones**: los vídeos nuevos de los canales a los que estás suscrito, con duración, visualizaciones y fecha. Requiere cuenta conectada y YouTube.js activado.
- **Canales suscritos**: los canales a los que estás suscrito. Cada uno se abre como cualquier canal, para elegir entre vídeos, Shorts, transmisiones en vivo y playlists. Requiere cuenta conectada y YouTube.js activado. Las dos listas de suscripciones son de solo lectura: suscribirse y cancelar la suscripción se siguen haciendo en YouTube.
- **Tendencias**: *Global* y los continentes. Entra en un continente, elige el país, y las listas y destacados en tendencia aparecen como playlists que puedes reproducir, abrir o guardar en la biblioteca. No requiere cuenta.
- **Estados de ánimo y géneros**: las categorías de estados de ánimo y géneros de YouTube Music (*Concentración*, *Entrenamiento*, *Pop*, *Rock*...). Entra en una categoría para ver sus playlists. No requiere cuenta.

En KeyTube, además:

- `Retroceso` vuelve un nivel cada vez, hasta **Inicio**. Se puede encadenar: de un artista a un álbum, de un canal a una playlist suya.
- Cada lista trae 20 elementos cada vez.
- El botón **Acciones...** abre el menú del elemento: **Reproducir**, **Añadir sin reproducir**, **Ver contenido**, **Volver a la lista anterior**, **Ver comentarios**, **Ver detalles**, **Ir al canal** (o **Ir al artista**, seguido del nombre), **Agregar selección...** (en una playlist nueva o en una abierta), **Descargar selección...** y **Guardar en YouTube Music** (playlists o pistas compatibles). En una de tus playlists, el menú también trae **Eliminar playlist de YouTube Music...**, que la elimina de la cuenta, con confirmación, y solo vale para playlists que creaste. En un comentario, trae **Leer el comentario completo**.
- `Shift+Enter` en una de tus playlists añade las pistas a la playlist actual sin reproducir.
- `Ctrl+Shift+B` (o **Descargar selección...**) descarga lo que está seleccionado. Con una **playlist o un álbum**, KeyTune busca todas las pistas de dentro y lo descarga todo. Tú eliges la carpeta de destino; cada playlist o álbum se convierte en una **subcarpeta con su nombre**, y las pistas y vídeos sueltos quedan en la propia carpeta, incluso en una selección mixta. Dos listas con el mismo nombre reciben carpetas separadas (*Mix* y *Mix (2)*), y una pista que está en dos playlists se descarga en las dos, para que cada carpeta quede completa.

Justo encima de la lista, una línea indica dónde estás y cuántos elementos hay (por ejemplo, *Tendencias — Europa: 24 elementos*).

### Buscar y abrir enlaces

- **Buscar o pegar un enlace**: escribe lo que buscas y pulsa `Enter`. Los resultados entran encima de **Inicio**, y `Retroceso` vuelve a él.
- **Pegar un enlace**: un enlace de playlist, mix o vídeo de YouTube Music o de YouTube pegado en ese campo se abre con `Enter`, en lugar de buscarse.
- **En** y **Tipo**: dos cuadros junto al campo. **En** elige dónde buscar (*YouTube Music* o *YouTube*) y **Tipo**, qué buscar allí. En ambos, la primera letra salta a la opción.
    - En *YouTube Music*: *Canciones* (pistas del catálogo), *Vídeos* (videoclips y vídeos de YouTube Music), *Álbumes* (álbumes, sencillos y EP), *Artistas* y *Playlists* (del catálogo de YouTube Music).
    - En *YouTube*: *Vídeos* (en general, sin exigir cuenta), *Canales* y *Playlists*.
- **Dentro de un canal o artista**: al entrar, la lista muestra primero lo que hay para ver. En un canal de YouTube: *Vídeos*, *Shorts*, *En vivo* y *Playlists*. En un artista de YouTube Music: *Canciones*, *Álbumes*, *Sencillos y EP*, *Vídeos* y *Artistas similares*. Entra en lo que quieras; `Retroceso` vuelve para elegir otro.

### Detalles de vídeos y canciones

**Ver detalles**, en el menú **Acciones...** (o en el menú contextual de la playlist, para un elemento de YouTube), abre un cuadro de lectura con título, canal y suscriptores, duración, visualizaciones, «me gusta», fecha de publicación y la descripción completa. Para el medio que está sonando, usa `Ctrl+Shift+I` (**Reproducción > Ver detalles del medio actual**). El botón **Ir al canal**, o **Ir al artista** en una pista de YouTube Music, abre el canal o el artista en KeyTube; el mismo comando está en el menú **Acciones...**.

### Comentarios

**Ver comentarios**, en el menú **Acciones...** de un vídeo o de una canción, abre los comentarios en la propia lista, encima de lo que veías; `Retroceso` vuelve. Para el medio que está sonando, usa `Ctrl+Shift+M` (**Reproducción > Ver comentarios del contenido actual**), que abre la pestaña ya en los comentarios.

- Cada línea trae el autor, el texto, la fecha, los «me gusta» y cuántas respuestas hay. El comentario fijado por el canal aparece marcado como *fijado*.
- `Enter` abre el comentario completo en un cuadro de lectura; `Esc` lo cierra.
- `Flecha derecha`, en un comentario con respuestas, abre las respuestas.

Con YouTube.js activado (**Preferencias > Recursos adicionales**), los comentarios llegan en menos de un segundo, en el idioma del contenido, con paginación y respuestas. Sin él, KeyTune usa yt-dlp, que es más lento, trae solo los 20 primeros comentarios, sin respuestas, y con las fechas en inglés.

### Idioma del audio

**Reproducción > Idioma del audio del contenido actual...** lista las pistas de audio del vídeo de YouTube que está sonando (la original y los doblajes) y pasa a reproducir la elegida desde el mismo punto. La elección vale para ese medio hasta que cierres KeyTune. Para que valga para todos, usa **Audio de los vídeos doblados** en las preferencias.

### Transmisiones en vivo

Pega el enlace de una transmisión en vivo de YouTube en el campo **Buscar o pegar un enlace** (o usa `Ctrl+V`, como con cualquier enlace). KeyTune reconoce la transmisión por sí solo.

- Suena en el momento actual, sin reanudar desde una posición guardada. La barra de tiempo muestra una etiqueta fija en lugar de la duración, y `T` informa de cuánto tiempo llevas viéndola.
- Con **Mostrar el video de las transmisiones en vivo** activado (el valor predeterminado), la imagen aparece en el área del reproductor incluso con **Desactivar salida de video** marcado. El vídeo se limita a 720p. Desactivado, la transmisión suena solo en audio, en la variante más ligera. `Ctrl+Alt+V` alterna la opción y reinicia la transmisión en el nuevo modo.
- No se puede avanzar, retroceder ni ir al principio o al final. Pausar y reanudar continúa desde donde se quedó.
- Si la conexión se corta, el reproductor intenta reconectar hasta tres veces y te avisa. Si la transmisión ya terminó, el reproductor avisa en lugar de reproducir la grabación desde el principio.
- Una transmisión programada que aún no empezó avisa; inténtalo de nuevo cuando empiece.
- Las transmisiones en vivo quedan fuera de AutoDJ y del crossfade, no tienen letra y no generan punto de reanudación.

### Radio a partir de la pista actual

Con una canción de YouTube Music sonando, pulsa `Ctrl+R` (o usa **Reproducción > Iniciar radio desde esta pista**). KeyTune abre una pestaña nueva, mantiene la posición de la reproducción y pone la pista actual como elemento 1, sin continuar la cola de la radio anterior.

KeyTune evita repetir pistas de la playlist de origen y de las últimas radios que abriste. Como quien elige los candidatos es YouTube Music, no hay garantía de canciones distintas; si no hay novedades, la pestaña nueva se queda solo con la pista inicial.

No lo confundas con las [radios en línea](#radios-en-linea), que son emisoras de radio de verdad.

### Gestionar playlists de YouTube Music

Además de abrir y guardar playlists, KeyTune edita tus playlists directamente en la cuenta conectada. Todo esto requiere cuenta conectada y cambia la playlist **en tu cuenta de YouTube Music**. Eliminar no se puede deshacer desde el reproductor.

**Agregar pistas.** Selecciona una o más pistas de YouTube Music (en la playlist actual o en los resultados de la búsqueda) y usa **Agregar a la playlist de YouTube Music...** en el menú contextual (`Shift+F10`). Para agregar la pista que está sonando, pulsa `Ctrl+Shift+A`. Aparece la lista de tus playlists editables; los mixes y las radios personalizadas no entran porque no admiten edición. Arriba hay **Crear nueva playlist...**, que crea una playlist ya con la selección.

**Quitar pistas.** Con una playlist tuya abierta en la pestaña actual, selecciona las pistas y usa **Quitar de la playlist de YouTube Music** en el menú contextual. El reproductor pide confirmación. La eliminación solo se ofrece en playlists que creaste o en las que eres colaborador.

**Crear una playlist.** Usa **Nueva playlist...** (en la sección *Playlists y mixes*) para crear una vacía, o **Crear nueva playlist...** en el diálogo de agregar pistas para crearla ya con la selección. En ambos casos el reproductor pide el **nombre** y la **privacidad**: *Privada* (solo tú la ves), *No listada* (visible para quien tenga el enlace) o *Pública* (aparece en tu perfil y puede salir en búsquedas). El valor predeterminado es Privada.

**Eliminar una playlist.** Selecciona la playlist en *Playlists y mixes* y usa **Eliminar playlist...**. Solo se pueden eliminar playlists que creaste.

### Conectar tu cuenta

Para usar tu biblioteca (listas guardadas, historial, me gusta y valoraciones), conecta una cuenta. KeyTune no pide tu contraseña: usa las cookies del navegador en el que iniciaste sesión en YouTube.

Abre KeyTube (`Ctrl+Shift+Y`) y, en la sección **Cuenta y biblioteca**, activa **Conectar cuenta...**. El diálogo **Conectar a YouTube** tiene dos modos:

1. **Introducir manualmente (archivo o texto)**: el modo predeterminado y el que dura. Exportas un `cookies.txt` desde una ventana privada y eliges el archivo.
2. **Extraer del navegador instalado**: más rápido, pero la conexión se cae cuando vuelves a usar YouTube en ese navegador.

El botón **Cómo exportar las cookies...** abre un resumen de estas instrucciones en un cuadro de lectura.

#### Qué son las cookies

Las cookies son pequeños archivos de texto que los navegadores guardan para recordar preferencias e inicios de sesión. Cuando entras en YouTube Music, el navegador guarda cookies con tu autenticación. Al conectar la cuenta en KeyTune, la aplicación usa esa sesión para acceder a tu biblioteca.

#### Por qué se cae la conexión: el cambio de cookies

Por seguridad, YouTube cambia las cookies de la cuenta con frecuencia mientras usas el sitio. Cuando el navegador recibe las cookies nuevas, las que guardó KeyTune dejan de valer, y la cuenta aparece como desconectada aunque ayer funcionara. No es un fallo de KeyTune ni de tu cuenta.

El cambio solo ocurre en una sesión que se sigue usando. Por eso el camino que dura es exportar las cookies de una sesión que el navegador no volverá a abrir: una ventana privada, cerrada justo después de la exportación.

Cuando las cookies dejan de valer, KeyTune avisa de que YouTube ya no las acepta. Conecta de nuevo con un archivo nuevo; el anterior no vuelve a funcionar.

#### Conectar con un cookies.txt (recomendado)

**Antes de empezar**, instala en el navegador la extensión [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).

**1. Activar la extensión en ventanas privadas.**

1. Pulsa `Ctrl+L` para enfocar la barra de direcciones.
2. Pulsa `Escape` para salir del cuadro de edición de la barra de direcciones.
3. Pulsa `Alt+F` para abrir el menú del navegador.
4. Con las flechas, ve a **Extensiones**, abre el submenú con `Enter` y elige **Gestionar extensiones**.
5. Busca **Get cookies.txt LOCALLY** y haz clic en **Detalles** (o "Más información").
6. En la página de detalles, activa **Permitir en pestañas privadas** (o **Permitir en modo incógnito**).
7. Cierra la página y vuelve al navegador.

**2. Iniciar sesión y exportar las cookies.**

1. Abre una ventana privada (`Ctrl+Shift+N` o `Ctrl+Shift+P`). Debe ser la única ventana privada abierta.
2. Ve a [music.youtube.com](https://music.youtube.com/) e inicia sesión con tu cuenta de Google.
3. Abre la extensión **Get cookies.txt LOCALLY** y haz clic en **Exportar** (o **Download**) para guardar el `cookies.txt`.
4. Cierra la ventana privada sin abrir nada más en ella.

Esto suele bastar. Si la cuenta se cae igualmente, repite la exportación con un paso más, recomendado por `yt-dlp`: después de iniciar sesión y antes de exportar, pulsa `Ctrl+L`, escribe `youtube.com/robots.txt` y pulsa `Enter`. Se abre una página solo de texto; no hace falta hacer nada en ella. Exporta las cookies con esa página abierta y cierra la ventana.

**3. Importar en KeyTune.**

1. En el diálogo **Conectar a YouTube**, deja elegido **Introducir manualmente (archivo o texto)**.
2. En **Archivo de conexión**, elige el `cookies.txt` descargado y activa **Conectar**.

En lugar del archivo, también puedes pegar en **Datos copiados del navegador** el contenido del `cookies.txt`, las cabeceras HTTP de una petición de YouTube Music o solo el valor de la cabecera `Cookie`.

#### Conectar desde el navegador instalado

Usa este modo si no quieres instalar la extensión. Copia la sesión normal del navegador con `yt-dlp`, así que vale lo dicho en [Por qué se cae la conexión](#por-que-se-cae-la-conexion-el-cambio-de-cookies): la conexión dura mientras no uses YouTube en ese navegador. Funciona mejor con un navegador en el que no ves YouTube.

1. Inicia sesión en tu cuenta en [YouTube Music](https://music.youtube.com/) en ese navegador y ciérralo por completo.
2. En el diálogo **Conectar a YouTube**, elige **Extraer del navegador instalado**.
3. Elige el navegador en la lista y activa **Conectar**.

Firefox es el que mejor funciona. En Windows, Chrome, Edge y Brave protegen las cookies de una forma que `yt-dlp` no puede abrir, y la exportación suele fallar; en ese caso usa Firefox o el modo manual.

#### Más de una cuenta de Google

Si la sesión tiene más de una cuenta de Google, KeyTune pregunta cuál usar justo después de conectar. La biblioteca y las suscripciones pasan a ser de esa cuenta. Para cambiarla después, activa **Actualizar acceso...** y conecta de nuevo.

#### Seguridad

El `cookies.txt` guarda la autenticación de tu cuenta. Por eso:

- usa el archivo solo en tu propio equipo;
- no lo compartas con nadie;
- bórralo después de importarlo, si quieres: la copia interna de KeyTune tiene solo las cookies de YouTube necesarias para la conexión;
- al desconectar la cuenta en KeyTune, se eliminan las cookies guardadas.

### Atajos de KeyTube

- `Ctrl+Shift+Y`: abrir KeyTube
- `Ctrl+R`: iniciar una radio a partir de la pista actual
- `Ctrl+Shift+A`: agregar el medio actual a una playlist de YouTube Music
- `Ctrl+Shift+I`: ver los detalles del medio actual
- `Ctrl+Shift+M`: ver los comentarios del medio actual
- `Ctrl+L`: dar «me gusta» al medio actual
- `Ctrl+Shift+L`: marcar el medio actual como «no me gusta» (y pasar a la siguiente pista)
- `A`: activar o desactivar el contenido relacionado al final de la playlist
- `Enter` en el campo de búsqueda: buscar; con resultados, el foco pasa a la lista
- `Esc`: cerrar la pestaña, cuando tiene el foco

## Radios en línea

`Ctrl+Shift+N` (o **Ver > Radios en línea en una pestaña**) abre una pestaña para escuchar radios de todo el mundo. Las emisoras vienen de [Radio Browser](https://www.radio-browser.info/), un directorio abierto mantenido por la comunidad. No hace falta cuenta ni activar nada en **Recursos adicionales**: las radios suenan directamente, sin pasar por `yt-dlp`.

La pestaña tiene un campo de búsqueda y, debajo, una sola lista que funciona como el explorador de carpetas y como la lista de KeyTube: entras en los elementos y vuelves.

### El inicio

La lista empieza en **Inicio**, con estos elementos:

- **Radios favoritas**: las que marcaste con `Ctrl+D`.
- **Escuchadas recientemente**: las últimas radios que reprodujiste.
- **Radios de tu país**: las del país que KeyTune usa como el tuyo. Por defecto es el de Windows; puedes elegir otro en **Preferencias > Radios en línea**, en **Mi país**, o en el menú de acciones del país, dentro de la pestaña (**Establecer ... como mi país**).
- **Más escuchadas en el mundo**.
- **Países**: elige un país y mira las **Más escuchadas**, **Todas, en orden alfabético** o **Por estado o región**.
- **Géneros**: elige un género para ver sus radios.
- **Idiomas**: elige un idioma para ver sus radios.

### Teclas y acciones

Además de las teclas de [Cómo funcionan las listas](#como-funcionan-las-listas):

- `Ctrl+D`: añade la radio a favoritas o la quita. Es el mismo favorito de las playlists, y la lista marca la radio como «favorita».
- `Ctrl+C`: copia la dirección del stream de la radio seleccionada.
- El botón **Acciones...** abre el menú con **Reproducir**, **Añadir sin reproducir**, **Ver contenido**, **Volver a la lista anterior**, **Añadir a favoritas** (o **Quitar de favoritas**), **Ver detalles de la radio**, **Abrir el sitio web de la radio en el navegador**, **Copiar la dirección del stream** y **Votar por esta radio en el directorio**. Con una radio sonando, el menú también permite marcarla como favorita aunque no esté seleccionada.

**Ver detalles de la radio** abre un cuadro de lectura con nombre, país, estado o región, idioma, géneros, calidad (códec y tasa de bits), votos, oyentes en las últimas 24 horas, sitio web y dirección del stream, con un botón para abrir el sitio. **Votar por esta radio en el directorio** registra tu voto en Radio Browser.

### Buscar y pegar direcciones

Escribe el nombre de una radio en el campo de búsqueda y pulsa `Enter`. El cuadro **En** elige dónde buscar: **Todo el mundo** o solo tu país. Si pegas en el campo la dirección de un stream, suena directamente, sin búsqueda.

### Cómo suena la radio

La radio entra en la playlist actual con el nombre de la emisora. Suena como una transmisión en vivo solo de audio: no se puede avanzar ni retroceder, y queda fuera de AutoDJ y del crossfade.

La canción que anuncia la emisora aparece en la barra de estado, con el formato *Emisora: título*, y entra en el anuncio de estado (`S`). Las recientes salen del historial de reproducción.

## Ecualizador

`Ctrl+Shift+E` (o **Ver > Ecualizador**) abre el ecualizador. El ajuste vale para todo lo que KeyTune reproduce: todas las pestañas, las que abras después y el reproductor rápido.

### Cómo usarlo

La casilla **Activar ecualizador** activa o desactiva el efecto.

El campo **Preset** lista todos los presets. Los integrados llevan el sufijo *(integrado)*. Al elegir uno, **Descripción** muestra una nota sobre el perfil sonoro y **Resumen del preset** trae la preamplificación y el valor de cada banda, para que lo compruebes antes de aplicar.

#### Botones de gestión

- **Nuevo...**: crea un preset personalizado desde cero. El editor pide el nombre, la preamplificación y la ganancia de cada banda. Úsalo cuando quieras una curva que no existe entre los integrados.
- **Editar...**: edita un preset personalizado. Solo aparece así cuando el seleccionado es personalizado.
- **Guardar copia...**: cuando el seleccionado es integrado, este es el botón que aparece. Crea una versión editable basada en él, el camino correcto para partir de un preset listo y ajustar.
- **Duplicar...**: copia un preset personalizado con otro nombre, sin tocar el original. No vale para los integrados.
- **Eliminar**: elimina de forma definitiva el preset personalizado seleccionado. No vale para los integrados.

#### Ecualizador solo para una pestaña

Una playlist puede sonar distinta de las demás: audiolibros con la voz realzada, por ejemplo. Con ella sonando, abre el ecualizador y marca **Usar un ecualizador solo para esta pestaña**. El campo **Pestaña destino** muestra de qué playlist se trata.

- Marcada, la pestaña parte del ajuste que ya estaba en uso, y lo que cambies se queda solo en ella.
- Sin marcar, la pestaña vuelve a seguir el ecualizador de todas las pestañas.

#### Editor de presets

El editor tiene el campo del nombre, la preamplificación y un control por banda de frecuencia. Cada banda va de -12,0 dB a +12,0 dB: los valores positivos refuerzan la frecuencia y los negativos la atenúan. La preamplificación ajusta la ganancia general antes de todas las bandas.

### Presets integrados

KeyTune trae 18 presets:

| Preset | Perfil |
|---|---|
| Predeterminado | Curva neutra, mantiene el sonido original |
| Clásica | Realza la definición y el brillo sin exagerar los graves |
| Club | Graves y agudos más animados |
| Dance | Más impacto en el grave y brillo arriba |
| Graves profundos | Prioriza subgraves y graves, para dar peso al ritmo |
| Graves y agudos | Curva en V, con graves fuertes y agudos brillantes |
| Agudos realzados | Destaca detalles, voces y brillo general |
| Auriculares | Equilibrio pensado para auriculares, con sensación de claridad |
| Sala amplia | Crea una sensación más abierta y amplia |
| En vivo | Presencia de escenario y ambiente |
| Fiesta | Curva para volúmenes casuales y música animada |
| Pop | Voz, brillo y graves limpios |
| Reggae | Más cuerpo en los graves, con medios relajados |
| Rock | Ataque de guitarras, caja y presencia general |
| Ska | Bajo firme, con medios y agudos vivos |
| Suave | Escucha tranquila, reduce la agresividad |
| Rock suave | Equilibrio con ligera presencia de voz y brillo |
| Techno | Ritmo, subgrave y brillo electrónico |

### Consejos

- Reduce la preamplificación si el sonido empieza a distorsionar.
- Para ajustar una curva lista, usa **Guardar copia...** sobre el preset integrado. Para experimentar sin perder la versión actual, usa **Duplicar...**.

## AutoDJ

AutoDJ mezcla las pistas de la playlist como lo haría un DJ, en lugar de cortar de una a otra. No forma parte del instalador: KeyTune descarga las bibliotecas de análisis (`librosa`, NumPy, SciPy, Numba y PyAV) después de que confirmes, en **Preferencias > Recursos adicionales**. Una vez instalado, **Reproducción > Activar AutoDJ** lo activa y desactiva.

Analiza la pista actual y las siguientes opciones en segundo plano y elige la siguiente por la energía, la tonalidad, el volumen y el tempo, evitando repetir artistas recientes. Cuando el ritmo es fiable, alinea los tiempos de las dos pistas durante el solapamiento. La cola manual siempre tiene prioridad. Si el análisis se retrasa, falla o no tiene confianza, el reproductor usa el crossfade normal o pasa a la siguiente pista con normalidad.

**Reproducir playlist con AutoDJ** crea una pestaña aparte, sin tocar la playlist original. La pista actual empieza al instante, y KeyTune mantiene hasta cinco canciones preparadas por delante. La pestaña tiene un campo de lectura con el origen, cuántas pistas están preparadas, la actividad del análisis y la próxima transición: BPM, ajuste de tempo y, cuando hace falta una transición normal, el motivo. Cada elemento aparece como reproducido, sonando, siguiente o preparado.

Los controles de la sesión cambian la siguiente pista, recalculan la secuencia, añaden archivos, pausan o reanudan la preparación y finalizan la sesión conservando el tramo ya preparado. Las mismas acciones están en `Shift+F10`, sobre la lista. La sesión se restaura junto con el reproductor.

Las opciones de AutoDJ están en **Preferencias > Reproducción** y **Recursos adicionales**; consulta [Configuración](#configuracion).

## Personalizar el teclado

**Configuración > Personalizar teclado** muestra cada acción del reproductor con el atajo vigente. La pantalla tiene dos pestañas: **Atajos del reproductor**, que funcionan con la ventana de KeyTune en primer plano, y **Atajos globales**, que funcionan desde cualquier lugar de Windows.

En cada pestaña:

- **Filtrar acciones** busca por el nombre de la acción, la categoría o el propio atajo. Escribir "volumen" o "Ctrl+Shift" ya reduce la lista.
- `Intro` en la lista (o **Cambiar atajo**) abre un campo que captura la combinación que pulses. `Tab` sale del campo, `Intro` confirma y `Esc` cancela.
- `Supr` en la lista (o **Quitar atajo**) deja la acción sin atajo.
- **Restaurar predeterminado** devuelve el atajo original de la acción; **Restaurar todos** lo hace con toda la pestaña.
- Nada cambia hasta que eliges **Guardar**.

Si el atajo elegido ya pertenece a otra acción, KeyTune dice cuál y pregunta si puede pasarlo a la nueva; la anterior queda sin atajo. Así nunca hay dos acciones con el mismo atajo.

Algunas teclas no se pueden usar porque sirven para navegar y editar: `Tab`, `Shift+Tab`, `Ctrl+Tab`, `Esc`, `Intro`, `Alt+F4`, `Shift+F10`, `Ctrl+A`, `Ctrl+C`, `Ctrl+V`, `Ctrl+X` y `Ctrl+Z`.

Un atajo sin `Ctrl` ni `Alt` (como `Espacio`, `P` o `Shift+Flecha derecha`) se comporta como los predeterminados: solo actúa con el foco en el reproductor. En la lista de elementos y en los campos de texto la tecla sigue siendo del control. Los atajos con `Ctrl` o `Alt` actúan en cualquier parte de la ventana, salvo dentro de un campo de texto.

Los menús muestran el atajo nuevo, y `F1` enumera al final de la ayuda lo que cambiaste.

### Atajos globales

Funcionan con KeyTune minimizado, en la bandeja del sistema o con otro programa en primer plano. Están desactivados hasta que marques **Activar atajos globales** en la pestaña **Atajos globales**. Solo en Windows.

| Atajo predeterminado | Acción |
| --- | --- |
| `Ctrl+Alt+Shift+P` | Reproducir o pausar |
| `Ctrl+Alt+Shift+Flecha derecha` / `Flecha izquierda` | Siguiente pista / pista anterior |
| `Ctrl+Alt+Shift+X` | Detener |
| `Ctrl+Alt+Shift+Flecha arriba` / `Flecha abajo` | Subir / bajar el volumen (se anuncia el volumen nuevo) |
| `Ctrl+Alt+Shift+I` | Anunciar estado |
| `Ctrl+Alt+Shift+T` | Anunciar tiempo |
| `Ctrl+Alt+Shift+K` | Mostrar u ocultar KeyTune en la bandeja del sistema |
| `Ctrl+Alt+Shift+M` | Minimizar o restaurar la ventana |

Avanzar, retroceder, aleatorio, modo de repetición, anunciar volumen y traer KeyTune al frente vienen sin atajo; puedes definir uno en la misma pantalla. Los atajos globales necesitan `Ctrl`, `Alt` o la tecla `Windows`; si no, la tecla dejaría de funcionar en otros programas. Si otro programa ya usa la combinación, KeyTune avisa al guardar y ese atajo no hace nada hasta que elijas otro.

### Bandeja del sistema

**Archivo > Ocultar en la bandeja del sistema** (o `Ctrl+Alt+Shift+K`, con los atajos globales activados) oculta la ventana y deja un icono junto al reloj, y la música sigue sonando. Para llegar al icono con el teclado, usa `Windows+B` y las flechas. `Intro` en el icono vuelve a mostrar la ventana; su menú contextual (`Shift+F10` o la tecla de aplicaciones) tiene **Mostrar KeyTune**, **Reproducir o pausar**, **Pista anterior**, **Siguiente pista**, **Detener**, **Anunciar estado** y **Salir de KeyTune**. Al volver, el foco queda donde estaba.

En **Preferencias > General > Bandeja del sistema**, **Al minimizar, ocultar en la bandeja del sistema** hace lo mismo al minimizar, y **Al cerrar, ocultar en la bandeja del sistema** hace que cerrar la ventana solo la oculte. Con esa opción activada, sal con **Archivo > Salir** o **Salir de KeyTune** en el menú del icono.

## Configuración

Las preferencias se abren con `Ctrl+,` y se dividen en ocho pestañas: **General**, **Reproducción**, **Accesibilidad**, **Biblioteca**, **Descarga**, **KeyTube**, **Radios en línea** y **Recursos adicionales**.

### General

**Restaurar sesión al iniciar**, **Recordar tamaño de la ventana**, **Recordar última carpeta usada** y **Confirmar al salir** hacen lo que dice su nombre. **Usar el reproductor rápido al abrir archivos desde Windows** viene marcado y decide si un archivo de audio abierto desde el Explorador de archivos suena en la ventana pequeña o en la ventana principal (consulta [Escuchar un archivo directamente desde el Explorador de archivos de Windows](#escuchar-un-archivo-directamente-desde-el-explorador-de-archivos-de-windows)).

La sección **Bandeja del sistema** tiene **Al minimizar, ocultar en la bandeja del sistema** y **Al cerrar, ocultar en la bandeja del sistema**; consulta [Bandeja del sistema](#bandeja-del-sistema).

La sección **Asociación de archivos** (Windows) tiene el botón **Registrar como reproductor predeterminado**, que añade KeyTune al menú *Abrir con* para formatos de audio, vídeo y playlists. Después de registrar, define la aplicación como predeterminada en la configuración de Windows, si quieres que esos archivos se abran directamente en ella. **Anular registro de asociaciones** deshace el registro.

La sección **Registro de logs** ayuda a investigar problemas. **Registrar logs de diagnóstico** escribe un archivo de registro, en inglés, en la carpeta de datos, útil para adjuntar a un informe de errores. **Nivel de detalle** va de *Solo errores*, el más silencioso, a *Depuración*, que genera archivos grandes. **Abrir la carpeta de logs** te lleva hasta ellos.

### Reproducción

- **Crossfade (segundos)**: el solapamiento de audio entre pistas en el cambio automático (0 a 12 s). Usa 0 para desactivarlo. Solo vale entre archivos de audio.
- **Aplicar el crossfade al cambiar de pista manualmente**: con la opción activada, el crossfade también se aplica al avanzar o retroceder con los controles; por defecto, solo en el final natural de la pista. Cuando hay una transición de AutoDJ lista, avanzar usa ese plan incluso con la opción desactivada.
- **Dispositivo de audio**: la salida de sonido. *Predeterminado del sistema* sigue el dispositivo principal de Windows.
- **Desactivar salida de video (reproducir solo el audio)**: reproduce solo el audio, incluso de archivos de vídeo. Evita ventanas externas de vídeo.
- **Mostrar el video de las transmisiones en vivo**: muestra la imagen de las transmisiones de YouTube en el área del reproductor incluso con la salida de vídeo desactivada para el resto de la aplicación. Desmarcado, la transmisión suena solo en audio. `Ctrl+Alt+V` lo alterna durante una transmisión.

El **volumen predeterminado**, los pasos de **volumen** y de **búsqueda** (cuánto cambia cada flecha), la **repetición predeterminada** y el **modo aleatorio** de las playlists nuevas completan la pestaña y también hacen lo que dice su nombre.

Con AutoDJ instalado, hay dos opciones más: **Perfil de AutoDJ** (*Suave* hace una mezcla larga y equilibrada; *Fiesta* concentra el cambio de graves en el centro y sube la energía poco a poco; *Electrónica* usa cortes más fuertes y un cambio más rápido, pensado para ritmos marcados) y **Duración de la transición de AutoDJ** (8, 16 o 32 pulsos, independiente del crossfade normal).

### Accesibilidad

Tiene una sola opción: **Activar anuncios de accesibilidad**. Activada, el reproductor anuncia al lector de pantalla los cambios de tiempo, volumen, cambio de pestañas y estado. Desactivada, esos anuncios se detienen. Los atajos de anuncio bajo demanda (`T`, `V` y `S`) funcionan en cualquier caso. Consulta [Funciones de accesibilidad](#funciones-de-accesibilidad).

### Biblioteca

Controla la [biblioteca inteligente](#biblioteca-inteligente). Desactivar **Activar la biblioteca inteligente** desactiva la función entera y deshabilita las demás opciones.

- **Indexar automáticamente las carpetas abiertas en el navegador**: al abrir una carpeta, sus medios entran en el índice en segundo plano.
- **Guardar un historial local de reproducción** y **Reproducciones guardadas en el historial** (50 a 20000): al pasar del límite, salen las más antiguas.
- **Recordar la posición de los medios largos**, **Duración mínima para recordar la posición** (1 a 240 minutos) y **Margen ignorado al principio y al final** (5 a 300 segundos): consulta [Reanudar donde lo dejaste](#reanudar-donde-lo-dejaste).
- **Entradas guardadas en la caché** (100 a 100000): cuántos metadatos y análisis de audio se guardan.

### Descarga

Define los valores predeterminados de `Ctrl+Shift+B`:

- **Tipo de descarga predeterminado**: **Audio** o **Vídeo**.
- **Calidad del audio**: **Original (sin conversión)** mantiene el audio como lo entrega YouTube; **MP3** (128, 192, 256 o 320 kbps) y **FLAC (sin pérdida)** convierten el audio y exigen FFmpeg.
- **Frecuencia de muestreo del audio**: **Original**, 44100 Hz o 48000 Hz. Solo vale cuando el audio se convierte. YouTube entrega 44,1 o 48 kHz, así que frecuencias mayores no aportarían ganancia de calidad.
- **Calidad del vídeo**: **Mejor disponible** o una altura máxima de 2160p a 144p. Si la altura elegida no existe, el vídeo se descarga en la mejor calidad disponible.
- **Carpeta de descarga**: dónde se guardan los archivos. Por defecto, **Descargas\KeyTune**, en la carpeta de tu usuario.
- **Mostrar siempre el diálogo al descargar**: activado (el valor predeterminado), cada descarga abre el diálogo de confirmación; desactivado, la descarga empieza directamente con las opciones de esta pestaña.

### KeyTube

Reúne las opciones de YouTube y de YouTube Music. Solo tienen efecto con la integración activada en **Recursos adicionales**.

**Biblioteca**

- **Playlists cargadas por vez**: cuántas playlists de la biblioteca llegan en cada carga (5 a 200). Los valores menores abren más rápido; al llegar al final de la lista, el reproductor ofrece cargar más.
- **Mixes personalizados para descubrir**: el máximo de elementos revisados en el inicio de YouTube Music para encontrar mixes personalizados (5 a 200). Los valores menores hacen la sincronización más rápida.

**Reproducción**

- **Reproducir pistas relacionadas al final de la playlist**: cuando termina la última pista de YouTube Music, o cuando pides la siguiente estando en la última, el reproductor busca pistas relacionadas (la radio de YouTube Music) y sigue sonando, sin pausa entre una y otra. La tecla `A` lo activa y desactiva durante la reproducción. Las pistas que ya están en la playlist no entran de nuevo.
- **Guardar lo que escuché en el historial de YouTube Music**: activada por defecto. Al escuchar una pista el tiempo suficiente (alrededor del 30% de la duración, entre 15 y 30 segundos), el reproductor la marca como vista en el historial de tu cuenta. Desactívala para reproducir sin registrar nada.

**Idioma y región**

- **Idioma del contenido**: el idioma que se pide a YouTube en las búsquedas y en los textos que devuelve (recuentos, fechas). El valor predeterminado es **El mismo de KeyTune**. Vale para las búsquedas de YouTube con YouTube.js activado; las búsquedas de YouTube Music usan solo la región.
- **Región del contenido**: el país que se usa en las búsquedas de YouTube y de YouTube Music. Con **Automática**, YouTube decide según tu conexión.
- **Audio de los vídeos doblados**: algunos vídeos traen el audio original y doblajes. Aquí eliges qué suena: **La que YouTube entregue** (el valor predeterminado), **Original del video** o el doblaje en un idioma. Los vídeos sin la pista pedida suenan con normalidad. Una pista que no es la predeterminada pasa por yt-dlp y tarda unos segundos más en empezar.

### Radios en línea

- **Mi país**: el país con el que se abre el inicio de la pestaña **Radios en línea** y que aparece como opción de búsqueda. Con **Automático (seguir el sistema)**, vale el país configurado en Windows. Un país que no está en la lista se puede definir en la propia pestaña, en el menú de acciones del país.

### Recursos adicionales

Reúne las integraciones y las bibliotecas opcionales de YouTube y de AutoDJ. Antes de la primera descarga, KeyTune muestra un diálogo con todos los componentes que se instalarán.

**Componentes de YouTube**

- **Activar la integración con YouTube y YouTube Music**: descarga y mantiene el ejecutable `yt-dlp`, los paquetes de Python necesarios y, si no hay uno compatible, un Node.js portátil para el resolutor EJS. Sin esto, KeyTube no funciona. La primera vez la descarga puede tardar unos minutos y requiere internet. Al desactivarla, los archivos ya descargados se quedan donde están.
- **Actualizar los componentes automáticamente**: busca y aplica actualizaciones en el intervalo definido abajo. Solo está disponible con la integración activada.
- **Usar la versión nightly de yt-dlp (recomendado)**: descarga las builds nightly de `yt-dlp`. YouTube cambia sus mecanismos de extracción con frecuencia, y la nightly suele recibir las correcciones antes que el canal estable.
- **Usar YouTube.js (recomendado)**: mejora la resolución y la reproducción. Instala YouTube.js y usa el mismo Node.js 24 o superior preparado para `yt-dlp`, que sigue como alternativa. El paquete entra en la comprobación periódica de actualizaciones.
- **Intervalo de actualización (horas)**: cada cuánto intenta el reproductor actualizar las dependencias cuando se abre KeyTube (1 a 720 h). Solo está disponible con la actualización automática activada.

**AutoDJ**

- **Descargar recursos y activar AutoDJ**: descarga aparte `librosa`, NumPy, SciPy, Numba y PyAV, que no vienen en el instalador. Al desactivarlo, los archivos descargados se quedan donde están.
- **Reproducir efectos de DJ durante las transiciones**, **Perfil de AutoDJ** y **Duración de la transición de AutoDJ** quedan disponibles con AutoDJ activado.

## Funciones de accesibilidad

KeyTune se pensó para lectores de pantalla y para usarse solo con el teclado:

- el foco evita saltos innecesarios al área nativa de vídeo;
- los estados y la navegación se anuncian cuando hay soporte de accesibilidad disponible;
- los campos, botones, listas y grupos tienen nombres y descripciones legibles por los lectores de pantalla.

Si usas un lector de pantalla, `T`, `V` y `S` (consulta [Atajos de reproducción](#atajos-de-reproduccion)) y la ayuda rápida `F1` te ayudan a orientarte sin depender de los anuncios automáticos. Esos anuncios, como el cambio de pista, el cambio de pestaña y el cambio de volumen, se pueden activar o desactivar en `Ctrl+,` > **Accesibilidad**.

Los favoritos y las valoraciones se dicen junto con el elemento, y los detalles, los comentarios y los permisos de los plugins aparecen en campos de lectura con etiqueta. El lector de pantalla también anuncia el nombre del grupo cuando el foco entra en él.

## Actualizaciones

Al iniciar, KeyTune puede comprobar las actualizaciones por sí solo. Para comprobarlas en cualquier momento, usa **Ayuda > Comprobar actualizaciones**.

Cuando hay una versión nueva, la aplicación muestra las notas de la release, el nombre del archivo y el tamaño de la descarga antes de pedir confirmación. Si aceptas, descarga el paquete, muestra el progreso y pide permiso para instalar cuando el archivo esté listo. Las notas llegan en el idioma de la interfaz.

Para leer qué cambió en cada versión, incluidas las anteriores, usa **Ayuda > Historial de cambios**: elige la versión en la lista y lee el texto justo debajo.

## Solución de problemas

**Empieza por el diagnóstico.** **Ayuda > Diagnóstico** prueba lo que KeyTune necesita para reproducir: la biblioteca de MPV y sus dependencias en Windows, el inicio del reproductor, los dispositivos de audio, `yt-dlp`, Node.js, YouTube.js, FFmpeg, la cuenta de YouTube y, resolviendo un video público de verdad, si YouTube responde a YouTube.js y a `yt-dlp`. El informe se abre en un cuadro de lectura, con los problemas primero y, en cada uno, qué hacer. **Copiar informe** lleva el texto al portapapeles, para adjuntarlo a un informe de error. El diagnóstico solo lee y prueba; no instala ni cambia nada.

Si el reproductor no consigue iniciarse al abrir KeyTune, el mismo diagnóstico se ejecuta solo, muestra el motivo y la aplicación se cierra a continuación.

**La aplicación no se abre bien.** Comprueba que la instalación terminó sin errores (reinstalar con el instalador más reciente resuelve la mayoría de los casos) y que el sistema tiene permiso para acceder a los archivos o carpetas que intentaste abrir.

**El reproductor no encuentra el runtime de MPV.** Comprueba que está en uno de estos lugares: una carpeta `mpv/` junto al ejecutable, `MPV_HOME`, `MPV_DLL_DIR`, la caché guardada de la ejecución anterior o una instalación compatible de Chocolatey.

**La asociación de archivos no funciona como esperabas.** Son dos pasos separados. Primero, KeyTune debe estar registrado como opción (durante la instalación, o después en **Configuración > Preferencias > General > Registrar como reproductor predeterminado**). Segundo, debe estar elegido como aplicación predeterminada para esos formatos en la configuración de aplicaciones predeterminadas de Windows. Registrar no basta para que KeyTune sea el predeterminado.

**KeyTube no carga o muestra errores de dependencias.** Abre `Ctrl+,` > **Recursos adicionales** y comprueba que **Activar la integración con YouTube y YouTube Music** está marcada. La descarga inicial puede tardar unos minutos y requiere internet. Si las dependencias ya están instaladas pero la búsqueda o la carga fallan, usa la versión nightly de `yt-dlp`, en las mismas preferencias: suele recibir correcciones antes que el canal estable.

**Una conversión falló.** Comprueba que el archivo se abre con normalidad en el reproductor y que la carpeta de destino admite escritura. El mensaje de FFmpeg se muestra y se anuncia; los archivos dañados o en formatos poco comunes pueden no convertirse.

**Una descarga o una transmisión en vivo no funciona.** Comprueba que los **Recursos adicionales** están activados y actualizados (`yt-dlp` cambia con frecuencia para seguir a YouTube). En una descarga, comprueba también que la carpeta existe y admite escritura. El error 429 indica un bloqueo temporal de YouTube por exceso de peticiones: espera unos minutos e inténtalo de nuevo.

**Una radio en línea no suena o la lista no se abre.** El directorio de Radio Browser y las propias emisoras a veces están fuera de servicio. Prueba otra radio de la lista, o vuelve a la lista y ábrela de nuevo.

**La cuenta de YouTube aparece desconectada, o el reproductor pide conectar de nuevo.** El navegador cambió las cookies que KeyTune había guardado; consulta [Por qué se cae la conexión](#por-que-se-cae-la-conexion-el-cambio-de-cookies). Exporta un `cookies.txt` nuevo desde una ventana privada, como en [Conectar con un cookies.txt](#conectar-con-un-cookies-txt-recomendado), y conecta de nuevo. Si la biblioteca aparece vacía o es de otra persona, la sesión tiene más de una cuenta de Google: conecta de nuevo y elige la cuenta correcta.

**Otros problemas.** Activa el registro de logs en `Ctrl+,` > **General** > **Registro de logs**. Con **Registrar logs de diagnóstico** activado y el nivel en *Depuración*, el reproductor escribe información detallada en `keytune.log`, en la carpeta de datos. **Abrir la carpeta de logs** te lleva hasta el archivo. Si vas a informar del problema, adjunta el log a la issue.

## Plugins y marketplace

Abre **Configuración > Gestionar plugins...** para instalar un archivo `.ktplugin` o elegir **Abrir marketplace**. Selecciona un plugin, comprueba autor, versión, origen, permisos y aislamiento y confirma con **Instalar y activar**. El gestor también activa, desactiva y desinstala plugins.

Las acciones que añaden los plugins están en **Configuración > Acciones de plugins**. Los plugins también pueden ofrecer pestañas y pantallas. Instala solo código de autores en quienes confíes: ejecutarse en un proceso aparte no es un sandbox de seguridad. El sello de verificación indica una revisión de procedencia, no una garantía de seguridad.

La [guía de desarrollo y API 2.0](plugins.es.md) incluye el manifiesto, los permisos, los métodos, los eventos y la publicación. Acompaña al reproductor y se puede leer sin conexión; los enlaces externos requieren internet.

## Para desarrolladores

KeyTune es un proyecto de código abierto. El repositorio, las issues, los pull requests y las releases están en [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). El código fuente de este manual está en [docs/manual.es.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.es.md).

Para ejecutar el proyecto desde el código, instala las dependencias con `uv sync` y abre el reproductor con `uv run keytune`. Las reglas de redacción del manual, el changelog y los commits están en `.github/instructions/writing.instructions.md`.
