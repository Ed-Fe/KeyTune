# Manual de KeyTune

KeyTune es un reproductor multimedia creado para usarse con teclado y con foco en la accesibilidad. Está pensado para funcionar bien con playlists, navegación por carpetas y para conservar lo que estabas haciendo entre una apertura y otra.

Este proyecto fue desarrollado con asistencia de IA, incluyendo GitHub Copilot, Codex de OpenAI y Claude Code de Anthropic.

Este manual presenta las funciones principales de la aplicación y las acciones más comunes para empezar a usar el reproductor con rapidez.

## Qué ofrece KeyTune

- Reproducción multimedia con control por teclado
- Playlists en pestañas
- Una cola de reproducción para organizar lo que sonará después
- Búsqueda dentro de la playlist o carpeta actual, con navegación entre los resultados por teclado
- Biblioteca inteligente con búsqueda global, favoritos, valoraciones, historial y reanudación por archivo
- Temporizador con duraciones predefinidas o pausa al final de la pista
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
- `Ctrl+Shift+C`: copiar el enlace o ruta del elemento actualmente en reproducción
- `Ctrl+Shift+S`: guardar la playlist actual
- `Ctrl+B`: alternar foco entre el navegador de elementos y el reproductor
- `Ctrl+F`: localizar un elemento en la playlist o carpeta actual
- `Ctrl+G`: buscar en toda la biblioteca (listas, carpetas e historial)
- `Ctrl+D`: marcar o desmarcar la selección como favorita
- `Ctrl+0` a `Ctrl+5`: valorar la selección de cero a cinco estrellas
- `Ctrl+Shift+H`: abrir el historial de reproducción
- `Ctrl+Shift+R`: continuar escuchando lo que quedó a medias
- `F3` / `Shift+F3`: siguiente o anterior resultado de la búsqueda

### Cola de reproducción

La cola de reproducción organiza lo que debe sonar después de la pista actual, sin depender del orden de la playlist que estés navegando. Siempre pertenece a la playlist que está sonando en ese momento.

Usa `Ctrl+Shift+F` o el menú **Reproducción > Agregar a la Cola de Reproducción** para agregar o quitar elementos de la cola. Para ver, quitar, reordenar o vaciar toda la cola, usa `Ctrl+Shift+Q` o el menú **Reproducción > Administrar la Cola de Reproducción**.

Si la cola está vacía, el administrador te lo indica y te pide que primero agregues elementos.

### Temporizador

El temporizador pausa la reproducción por sí solo después del tiempo acordado, útil para escuchar algo antes de dormir sin dejar el reproductor sonando toda la noche. **Pausa** en lugar de detener, así que la posición del archivo se conserva y basta con `Espacio` para continuar donde quedó.

Usa `Ctrl+Shift+D` o el menú **Reproducción > Temporizador** para configurarlo. Las opciones son:

- **Duraciones predefinidas**: 5, 10, 15, 30, 45, 60, 90 o 120 minutos, disponibles directamente en el submenú.
- **Tiempo personalizado**: cualquier valor de 1 a 720 minutos, en el cuadro de configuración.
- **Al final de la pista actual**: la reproducción termina cuando acabe la pista, sin avanzar a la siguiente, sin repetir y sin traer contenido relacionado.
- **No usar temporizador**: cancela la programación.

El submenú también incluye **Tiempo restante**, que anuncia cuánto falta, y **Cancelar temporizador**, activo solo cuando hay un temporizador programado.

Mientras corre la cuenta regresiva, el reproductor avisa cuando faltan 5 minutos y cuando falta 1 minuto. El estado del temporizador también entra en el anuncio de estado de la tecla `S`.

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
- `Ctrl+Shift+D`: configurar el temporizador
- `T`: anunciar el tiempo actual del medio
- `V`: anunciar el volumen actual
- `S`: anunciar el estado del reproductor
- `Ctrl+L`: marcar con me gusta el medio actual en YouTube Music
- `Ctrl+Shift+L`: marcar el medio actual como no me gusta en YouTube Music (y pasar a la siguiente pista)

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

#### Búsqueda en la playlist o carpeta actual

Para buscar en listas grandes, usa la búsqueda completa en lugar de la escritura rápida. Encuentra el texto en **cualquier parte** del nombre del elemento, no solo al comienzo.

- `Ctrl+F`: abre el cuadro **Localizar elemento**. Escribe el texto y confirma con `Enter` o con el botón **Localizar**.
- `F3`: va al siguiente resultado.
- `Shift+F3`: vuelve al resultado anterior.

La búsqueda también se abre desde el menú **Ver > Localizar elemento**, que igualmente ofrece **Siguiente resultado** y **Resultado anterior**.

Detalles útiles:

- La búsqueda ignora acentos y diferencias entre mayúsculas y minúsculas, igual que la escritura rápida.
- Recorre los elementos mostrados en la pestaña activa, así que funciona tanto en playlists locales como en carpetas y en listas provenientes de YouTube Music.
- La primera búsqueda considera el elemento ya seleccionado; a partir de ahí, `F3` y `Shift+F3` avanzan o retroceden.
- El lector de pantalla lee el nombre del elemento encontrado. La posición en la búsqueda aparece en la barra de estado, como en «Búsqueda "rock": resultado 2 de 7.», junto con un aviso cuando la búsqueda da la vuelta a la lista.
- El texto buscado se guarda durante la sesión: `F3` repite la última búsqueda sin reabrir el cuadro. Si aún no hay texto, `F3` abre el cuadro de búsqueda.
- Si nada coincide, se mantiene la selección actual y el reproductor informa que no hay elementos correspondientes.

Para tareas de organización, conviene pensar en las pestañas como espacios de trabajo independientes: una pestaña para reproducir algo ahora, otra para revisar la biblioteca y otra para pruebas o colecciones temporales.

## Biblioteca inteligente

Mientras `Ctrl+F` busca en la lista que está abierta, la **biblioteca inteligente** recuerda lo que ya abriste y escuchaste, y lo deja todo consultable de una vez. También guarda favoritos, valoraciones, el historial de reproducción y el punto donde se detuvo cada medio largo.

Todo vive en una base de datos local (`smart_library.db`) en la misma carpeta de datos que las preferencias. Nada sale de tu equipo, y la función entera se puede desactivar en `Ctrl+,` > **Biblioteca**.

El menú **Biblioteca** reúne todos los comandos.

### Qué entra en el índice

- Los medios de cualquier playlist o carpeta que abras entran en el índice en segundo plano.
- **Biblioteca > Indexar una carpeta en la biblioteca...** elige una carpeta y recorre también sus subcarpetas, sin frenar la reproducción. El reproductor avisa al terminar.
- **Biblioteca > Actualizar las carpetas indexadas** vuelve a recorrer las carpetas ya indexadas y descarta los archivos que ya no existen.
- **Biblioteca > Resumen de la biblioteca** anuncia cuántos medios, carpetas, favoritos y reproducciones hay guardados.
- **Biblioteca > Vaciar la biblioteca...** borra todo (índice, favoritos, valoraciones, historial y puntos de reanudación), con confirmación.

Si prefieres que solo entren las carpetas que elijas tú, desactiva **Indexar automáticamente las carpetas abiertas en el navegador** en las preferencias.

### Búsqueda global

- `Ctrl+G` abre el cuadro **Buscar en la biblioteca**.
- Escribe el texto y confirma con `Intro` o con el botón **Buscar**. La búsqueda ignora acentos y mayúsculas, y cada palabra que escribas debe aparecer en algún lugar del nombre del elemento o de la carpeta.
- El campo **Filtrar** restringe la búsqueda a **Todo en la biblioteca**, **Solo favoritos**, **Solo valorados** o **Solo ya reproducidos**. Los tres últimos funcionan incluso con el campo de texto vacío.
- Los resultados aparecen en una lista con columnas de elemento, valoración y carpeta, así que el lector de pantalla lee las tres al recorrerla con las flechas. El foco pasa a la lista en cuanto termina la búsqueda.
- La búsqueda se resuelve con un índice de texto completo, así que sigue siendo instantánea incluso con decenas de miles de archivos. Casa el principio de cada palabra («estrad» encuentra «Estrada»); cuando así no aparece nada, el reproductor todavía hace un recorrido que encuentra fragmentos en medio de la palabra («onita» encuentra «Bonita»).
- `Intro` (o el botón **Reproducir**) abre **todos** los resultados en una lista nueva y empieza por la pista seleccionada: así una búsqueda se convierte en una lista utilizable, no en una pista suelta.
- **Añadir a la cola** encola solo el elemento seleccionado en la lista que está sonando.

### Favoritos y valoraciones

Los dos comandos actúan sobre lo que esté seleccionado en la lista de elementos; sin selección, actúan sobre el medio que está sonando.

- `Ctrl+D`: marca o desmarca como favorito. Con varios elementos seleccionados, los marca todos.
- `Ctrl+0` a `Ctrl+5`: da de cero a cinco estrellas.
- **Biblioteca > Anunciar las marcas de la selección**: lee si el elemento es favorito, su valoración y cuántas veces se reprodujo.
- **Biblioteca > Abrir favoritos en una lista nueva**: arma una lista con todo lo que marcaste.

Los mismos comandos están en el menú contextual de la lista de elementos (`Shift+F10`).

Los favoritos y las valoraciones aparecen junto al nombre en la propia lista de elementos —por ejemplo `2. Estrada — favorito, 5 estrellas`—, tanto en las listas como en el navegador de carpetas. Así el lector de pantalla anuncia la marca junto con el elemento, sin necesidad de ningún comando. El sufijo es solo visual: la búsqueda `Ctrl+F`, los nombres de las pestañas y la sesión guardada siguen usando el nombre puro.

### Historial de reproducción

- `Ctrl+Shift+H` abre el **Historial de reproducción**.
- El campo **Ver** elige entre tres vistas, y las columnas cambian con ella:
  - **Todas las reproducciones**: una fila por cada vez que el medio sonó, con cuándo sonó, en qué punto se detuvo y su origen (lista local, carpeta, medio remoto o YouTube Music).
  - **Agrupado por medio**: una fila por medio, con cuántas veces sonó, la última vez y sus marcas. Escuchar la misma pista cuarenta veces deja de llenar la lista.
  - **Más reproducidas**: la misma agrupación, de la más reproducida a la menos reproducida.
- El campo **Filtrar por texto** reduce la lista; `Intro` (o **Reproducir**) la reproduce de nuevo y **Añadir a la cola** la encola.
- **Quitar la entrada** saca una reproducción de la lista sin borrar el medio del índice. En las vistas agrupadas el botón pasa a ser **Quitar del historial** y borra todas las reproducciones de ese medio. **Vaciar el historial** lo borra todo, con confirmación.
- Una pista solo entra en el historial después de sonar lo suficiente para contar como escuchada (alrededor del 25% de su duración, como máximo 20 segundos).
- El historial se recorta al límite fijado en las preferencias, descartando las entradas más antiguas.

Este historial es local e independiente de **Guardar las canciones escuchadas en el historial de YouTube Music**, que registra en tu cuenta de YouTube Music.

### Reanudar donde lo dejaste

Los pódcast, audiolibros y vídeos largos vuelven a sonar desde donde se detuvieron, y la barra de estado muestra «Reanudando … en …». La regla es conservadora a propósito:

- vale solo para archivos locales: los streams no tienen una línea de tiempo estable entre sesiones;
- solo para medios por encima de la **duración mínima** configurada (10 minutos por defecto);
- detenerse dentro del **margen** configurado (30 segundos por defecto) al principio o al final no crea punto de reanudación;
- llegar al final de la pista borra la marca, así que la próxima vez empieza desde el principio.

**Biblioteca > Continuar escuchando** (`Ctrl+Shift+R`) abre una lista con todo lo que está a medias, de lo más reciente a lo más antiguo, y cada elemento muestra dónde se detuvo: así reencuentras el pódcast que dejaste por la mitad sin tener que recordar dónde estaba.

**Biblioteca > Borrar las posiciones de reanudación** las limpia todas de una vez.

### Listas inteligentes

Una lista inteligente es una regla guardada, no una lista fija: se arma cada vez que la abres, así que sigue tus cambios de valoración y de historial. «Cinco estrellas que no suenan desde hace 30 días» sigue siendo correcta un mes después, sola.

**Biblioteca > Listas inteligentes** enumera las reglas guardadas para abrirlas con un solo comando, y **Gestionar listas inteligentes...** crea, edita y quita.

En el editor todo son campos de teclado, sin constructor visual de reglas:

- **Solo favoritos** y **Valoración mínima** filtran por tus marcas.
- **Sin sonar desde hace al menos (días)** encuentra lo que quedó olvidado; **Incluir medios nunca reproducidos** decide si lo que nunca sonó entra también.
- **Reproducciones mínimas** va por el otro lado: solo lo que ya escuchaste bastante.
- **Limitar a la carpeta** restringe a una carpeta y a todo lo que hay debajo.
- **Incluir medios remotos** trae también enlaces de YouTube Music y radios, que por defecto quedan fuera.
- **Ordenar por** y **Número máximo de elementos** deciden qué sale y en qué orden.

Cada cambio actualiza el **Resumen de la regla** al final del cuadro, en una frase: para quien usa lector de pantalla es la forma más rápida de comprobar qué reunirá la regla antes de guardar. Las reglas con nombre repetido reciben un sufijo numérico automático, y los cambios se guardan aunque cierres el cuadro con `Esc`.

### Caché de metadatos y análisis

La biblioteca guarda también los metadatos ya resueltos y los análisis de audio, para no repetir trabajo costoso en cada apertura. Una entrada se descarta automáticamente cuando el archivo cambia de tamaño o de fecha, y el número de entradas guardadas se ajusta en las preferencias.

## Configuración

Las preferencias están en `Ctrl+,` y se dividen en cinco pestañas: **General**, **Reproducción**, **Accesibilidad**, **Biblioteca** y **Recursos adicionales**.

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
- **Activar AutoDJ**: analiza en segundo plano la pista actual y hasta seis opciones siguientes, incluso en playlists nuevas, evita artistas recientes y elige por energía local de la transición, tonalidad mayor/menor, diferencia de volumen percibido y compatibilidad de tempo. Cuando la cuadrícula de beats es fiable, estima el primer tiempo del compás y los cambios de sección, alinea frases de cuatro compases, sincroniza ambas pistas y corrige pequeños desvíos de fase durante la superposición. El punto de entrada puede omitir una introducción silenciosa o débil; el intercambio progresivo de graves y medios termina cortando la pista saliente en el beat planificado. La cola manual siempre tiene prioridad. Si el análisis se retrasa, falla o no tiene suficiente confianza, el reproductor usa el crossfade normal configurado o avanza con normalidad.
- **Reproducir playlist con AutoDJ**: crea una pestaña dinámica separada sin modificar la playlist original, inicia inmediatamente la pista actual y mantiene hasta cinco canciones preparadas por adelantado. Un campo de solo lectura disponible mediante el foco normal de NVDA muestra la fuente, las cantidades preparadas y restantes, la actividad del análisis y los detalles de la próxima transición. Informa BPM, confianza rítmica, ajuste de tempo y el motivo cuando se requiere una transición normal; cada elemento también se marca como reproducido, en reproducción, próximo o preparado. Sus controles permiten cambiar la próxima pista, recalcular la secuencia futura, añadir archivos, pausar o reanudar la preparación y finalizar la sesión conservando el tramo preparado. `Tab` recorre el reproductor, la lista, la información y los controles de AutoDJ; `Shift+Tab` sigue el camino inverso. Las mismas acciones están disponibles con `Shift+F10` sobre la lista. La secuencia considera varias transiciones, evita choques probables de voces, acorta la superposición cuando es necesario y atenúa gradualmente una pista entrante más alta. La sesión, la fuente, el historial, el estado pausado y las pistas aún no planificadas se restauran con el reproductor.
- **Perfil de AutoDJ**: *Suave* usa una mezcla larga y equilibrada; *Fiesta* concentra el intercambio de graves en el centro y aumenta gradualmente la energía; *Electrónica* usa cortes más fuertes y un intercambio más rápido para ritmos marcados.
- **Duración de la transición de AutoDJ**: define una superposición de 8, 16 o 32 beats. Este valor es independiente de la duración del crossfade normal.
- **Paso de búsqueda (segundos)**: cuánto avanza o retrocede en el medio cada pulsación de `Flecha izquierda`/`Flecha derecha` (1-120 s).
- **Repetición predeterminada**: modo de repetición aplicado automáticamente a playlists nuevas. Las opciones son *Repetición desactivada*, *Repetir pista actual* y *Repetir playlist*.
- **Dispositivo de audio**: salida de sonido usada en la reproducción. *Predeterminado del sistema* sigue el dispositivo principal de Windows.
- **Activar aleatorio en nuevas playlists**: activa automáticamente el modo aleatorio en playlists creadas después de guardar.
- **Aplicar crossfade al cambiar de pista manualmente**: cuando está activado, el crossfade también se usa al avanzar o retroceder manualmente; de forma predeterminada solo vale al final natural de cada pista.
- **Desactivar salida de video (reproducir solo audio)**: mantiene la reproducción solo en audio, incluso en archivos de video. Útil para evitar ventanas externas de video.

### Accesibilidad

La pestaña **Accesibilidad** tiene una sola opción: **Activar anuncios de accesibilidad**. Cuando está activada, el reproductor anuncia cambios de tiempo, volumen, cambio de pestañas y estado al lector de pantalla. Cuando está desactivada, esos anuncios se suprimen. Los atajos de anuncio bajo demanda (`T`, `V`, `S`) siguen funcionando independientemente de esta configuración; consulta [Recursos de accesibilidad](#recursos-de-accesibilidad) para ver detalles.

### Biblioteca

La pestaña **Biblioteca** controla la [biblioteca inteligente](#biblioteca-inteligente). Desactivar la primera opción desactiva la función entera y deshabilita las demás.

#### Índice de la biblioteca

- **Activar la biblioteca inteligente**: activa la búsqueda global (`Ctrl+G`), los favoritos, las valoraciones, el historial y la reanudación por archivo.
- **Indexar automáticamente las carpetas abiertas en el navegador**: al abrir una carpeta, sus medios entran en el índice en segundo plano.

#### Historial de reproducción

- **Guardar un historial local de reproducción**: registra cada pista que suene lo suficiente para contar como escuchada.
- **Reproducciones guardadas en el historial**: cuántas entradas mantiene el historial (50-20000). Al superarlo, se descartan las más antiguas.

#### Reanudar donde lo dejaste

- **Recordar la posición de los medios largos**: activa la reanudación por archivo.
- **Duración mínima para recordar la posición (minutos)**: los medios más cortos que eso siempre empiezan desde el principio (1-240 min).
- **Margen ignorado al principio y al final (segundos)**: detenerse dentro de ese margen no crea punto de reanudación (5-300 s).

#### Caché de metadatos y análisis

- **Entradas guardadas en la caché**: cuántos metadatos resueltos y análisis de audio se guardan (100-100000). Las entradas más antiguas se descartan al alcanzar el límite.

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
- **Reproducir contenido relacionado al final de la playlist (radio automática)**: cuando la última pista de YouTube Music termina naturalmente - o cuando pides la siguiente pista estando en la última -, el reproductor busca pistas relacionadas (la radio de YouTube Music) y continúa reproduciendo automáticamente. Para una transición continua, la búsqueda empieza poco antes del final de la última pista y el enlace de la siguiente ya se resuelve con anticipación, evitando una pausa mientras se descubre el contenido. También se puede activar o desactivar con la tecla `A` durante la reproducción. Las pistas que ya están en la playlist no se agregan de nuevo, y cuando la radio devuelve solo repetidas el reproductor busca a partir de una pista anterior antes de terminar.
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

1. **Extraer del navegador instalado:** Selecciona Firefox, Google Chrome, Microsoft Edge, Brave u Opera de la lista y haz clic en **Conectar**. KeyTune extraerá la sesión directamente del perfil mediante `yt-dlp`. Se recomienda Firefox porque ofrece mayor compatibilidad en Windows.
2. **Importación de archivo o texto manual:** Para navegadores no listados o configuraciones personalizadas, puedes importar un archivo `cookies.txt` exportado o pegar los encabezados HTTP de la sesión.

En Windows, Chrome, Edge y Brave pueden requerir que el navegador esté completamente cerrado y, en algunas versiones, la protección del propio navegador puede impedir la extracción. Si eso ocurre, usa Firefox o la importación manual.

#### Qué son las cookies

Las cookies son pequeños archivos de texto que los navegadores almacenan para recordar tus preferencias e información de inicio de sesión en sitios web. Cuando inicias sesión en YouTube Music, el navegador guarda cookies que contienen tu autenticación. Al conectar tu cuenta en KeyTune, la aplicación utiliza esa información de sesión iniciada para acceder a tu biblioteca sin pedir tu contraseña.

#### Cómo conectar mediante extracción directa del navegador

1. Asegúrate de tener la sesión iniciada en tu cuenta de [YouTube Music](https://music.youtube.com/) en tu navegador (Chrome, Edge, Firefox, Brave o Opera).
2. En KeyTune, abre la pestaña de YouTube Music (`Ctrl+Shift+Y`).
3. En la sección **Cuenta y biblioteca**, haz clic en **Conectar cuenta...**.
4. En el diálogo que se abre, selecciona la opción **Extraer del navegador instalado**.
5. Elige tu navegador en la lista y haz clic en el botón **Conectar**.

#### Paso a paso alternativo: exportación manual de cookies.txt

Si optas por el modo manual o usas un navegador no compatible directamente:

**Requisito previo:** instala la extensión [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) en tu navegador.

**1. Activar la extensión en pestañas de incógnito**

Usar una pestaña de incógnito/privada evita que Google renueve las cookies con frecuencia durante el uso normal del navegador.

1. Presiona `Ctrl+L` para enfocar la barra de direcciones.
2. Presiona `Esc` para salir del cuadro de edición de la barra de direcciones.
3. Presiona `Alt+F` para abrir el menú del navegador.
4. Navega con las flechas hasta **Extensiones**, expande el submenú presionando `Enter` y elige **Administrar extensiones**.
5. Localiza **Get cookies.txt LOCALLY** y haz clic en **Detalles** (o "Más información").
6. En la página de detalles, localiza la opción **Permitir en pestañas privadas** o **Permitir en incógnito** y actívala.
7. Cierra la página y vuelve a tu navegador.

**2. Iniciar sesión y exportar cookies**

1. Abre una nueva pestaña de incógnito/privada (`Ctrl+Shift+N` o `Ctrl+Shift+P`).
2. Navega a [music.youtube.com](https://music.youtube.com/).
3. Inicia sesión con tu cuenta de Google.
4. Abre la extensión **Get cookies.txt LOCALLY** y haz clic en **Exportar** o **Download** para guardar el archivo `cookies.txt`.
5. Cierra la pestaña de incógnito sin navegar a otros sitios.

**3. Importar en KeyTune**

1. En el diálogo **Conectar cuenta...** de KeyTune, selecciona **Importar archivo o texto manual**.
2. Selecciona el archivo `cookies.txt` descargado (o pega el texto de los encabezados) y haz clic en **Conectar**.

#### Información de seguridad

El archivo `cookies.txt` exportado contiene información de autenticación de tu cuenta. Por seguridad:

- Usa el archivo solo en tu propio equipo.
- No compartas el archivo con otras personas.
- Elimina el archivo después de importarlo en KeyTune si lo deseas. La copia interna contiene únicamente las cookies de YouTube necesarias para la conexión.
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

La búsqueda de elementos evita anuncios redundantes: como `Ctrl+F`, `F3` y `Shift+F3` mueven la selección al elemento encontrado, quien lee la pista es el propio lector de pantalla, y la posición en la búsqueda queda solo en la barra de estado. La biblioteca inteligente sigue la misma idea: las listas de resultados y del historial tienen columnas con nombre, el foco pasa a la lista en cuanto termina la búsqueda, y los favoritos y las valoraciones, que nunca aparecen en la etiqueta del elemento, siempre se anuncian al cambiar. El temporizador, a su vez, avisa al programarse, cuando faltan 5 minutos, cuando falta 1 minuto y al pausar la reproducción; su estado también aparece en el anuncio de la tecla `S`.

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
