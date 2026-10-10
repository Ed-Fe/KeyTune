## [Sin publicar]

### Agregado

- **Personalizar el teclado**: **Configuración > Personalizar teclado** muestra cada acción con el atajo vigente y permite cambiar, quitar o restaurar cualquiera.
  - `Intro` en una acción captura la combinación que pulses. `Supr` deja la acción sin atajo.
  - Un filtro busca por nombre, categoría o atajo.
  - Si el atajo ya es de otra acción, KeyTune pregunta antes de pasarlo, así dos acciones nunca comparten la misma tecla.
  - Los menús y la ayuda de `F1` muestran los atajos que cambiaste.
- **Atajos globales**: reproducir, pausar, cambiar de pista, cambiar el volumen, oír el estado y ocultar o mostrar KeyTune con la ventana minimizada u otro programa en primer plano. Están desactivados hasta que marques **Activar atajos globales** en la pestaña **Atajos globales**. Solo en Windows.
- **Bandeja del sistema**: **Archivo > Ocultar en la bandeja del sistema** oculta la ventana y la música sigue. El menú del icono tiene los controles básicos del reproductor.
  - En `Ctrl+,` > **General**, puedes minimizar o cerrar la ventana directamente a la bandeja.

- **Diagnóstico** (**Ayuda > Diagnóstico**): prueba lo que KeyTune necesita para reproducir y muestra, en un cuadro de lectura, qué está mal y qué hacer en cada caso.
  - Comprueba la biblioteca de MPV y sus dependencias en Windows, el inicio del reproductor, los dispositivos de audio, `yt-dlp`, Node.js, YouTube.js, FFmpeg, la cuenta de YouTube y, resolviendo un video público de verdad, si YouTube responde a YouTube.js y a `yt-dlp`.
  - Si el reproductor no se inicia al abrir KeyTune, el diagnóstico se ejecuta solo y muestra el motivo antes de que la aplicación se cierre. Antes la ventana quedaba abierta sin funcionar.
  - Solo lee y prueba; no instala ni cambia nada en el equipo.
  - La prueba del video usa internet y no envía las cookies de la cuenta.

- **Elección de la cuenta de YouTube**: si la sesión del navegador tiene más de una cuenta de Google, KeyTune pregunta cuál usar justo después de conectar. Antes usaba siempre la primera, y la biblioteca podía aparecer vacía o ser de otra cuenta. Las suscripciones siguen la misma cuenta.

### Cambiado

- **Conectar la cuenta de YouTube**: el diálogo ahora se abre en **Introducir manualmente (archivo o texto)**, el modo que dura.
  - YouTube cambia las cookies de la cuenta mientras usas el sitio, y las que guardó KeyTune dejan de valer. El modo **Extraer del navegador instalado** copia justo la sesión en uso, por eso la cuenta se caía al cabo de un tiempo. Sigue disponible, con ese aviso.
  - **Cómo exportar las cookies...** abre las instrucciones en un cuadro de lectura: exportar desde una ventana privada y cerrarla enseguida. El manual explica el cambio de cookies en **Conectar tu cuenta**.
  - En la lista de navegadores, Chrome, Edge y Brave avisan de que pueden fallar en Windows.
  - Cuando YouTube deja de aceptar las cookies, el mensaje lo dice, en lugar de "no se pudo validar la autenticación".

- **Campos de solo lectura**: todos se comportan ahora como el de la letra de la canción, sin ajuste automático de línea. Con el lector de pantalla, cada flecha lee una línea entera del texto (un párrafo, en texto corrido), y no el fragmento que cabía en el ancho de la ventana. Vale para la bienvenida, la ayuda de atajos (`F1`), las notas de la actualización, el historial de cambios, el diagnóstico, los detalles y comentarios de videos, los detalles de plugins y de radios, la descripción del preset del ecualizador y la información de la sesión AutoDJ. Las líneas largas se desplazan hacia el lado.

### Corregido

- **KeyTune no podía iniciar MPV en equipos con un driver de video antiguo**: la ventana mostraba "ctypes.CDLL could not load it" y no sonaba nada. El loader de Vulkan que viene con drivers de 2016 o anteriores no tiene funciones que el MPV actual necesita, y Windows se negaba a cargar la biblioteca.
  - KeyTune ahora lleva su propio `vulkan-1.dll` en la carpeta `mpv` y usa los drivers de video instalados como antes.
  - Si MPV no carga por otro motivo, el diagnóstico indica qué DLL o función falta, o si Windows o el antivirus bloqueó el archivo.
- **Las cookies válidas de YouTube Music se rechazaban al conectar**: en algunas cuentas la conexión fallaba con "no contiene una cookie de autenticación compatible" o con un error en inglés sobre `__Secure-3PAPISID`, incluso con la exportación correcta.
  - Una cookie con un espacio, una tilde u otro carácter fuera del estándar ocultaba todas las que venían después, incluida la de autenticación. Ahora se deja de lado y se lee el resto.
  - Puedes pegar solo el valor de la cabecera `Cookie`, un `cookies.txt` cuyas tabulaciones se convirtieron en espacios al copiar, o las cabeceras sin `X-Goog-AuthUser`.
  - Si YouTube confirma que la sesión está iniciada pero el menú de la cuenta llega en un formato que KeyTune no reconoce, la cuenta se acepta igualmente, sin el nombre.
  - Cuando el navegador ya cambió las cookies, el mensaje lo dice y explica cómo exportarlas de nuevo.
- **Con la cuenta de YouTube conectada, MPV no podía crear un reproductor nuevo**: después de que KeyTune hablaba con la cuenta, cualquier reproductor creado a continuación fallaba con "access violation". Esto afectaba al cambio a un video después de otro medio y a la recreación del reproductor. La biblioteca de la cuenta cambiaba una configuración regional del proceso que MPV exige; ahora KeyTune la restaura antes de crear cada reproductor.
