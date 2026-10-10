## [Sin publicar]

### Corregido

- **Conectar la cuenta de YouTube justo después de abrir KeyTune**: la conexión con un `cookies.txt` o con las cookies pegadas fallaba con "no contiene una cookie de autenticación compatible", incluso con la exportación correcta. Le pasaba a quien conectaba la cuenta antes de usar cualquier cosa de YouTube, como justo después de instalar. Ahora la cuenta se conecta también en esa situación.
- **Cookies sin `LOGIN_INFO`**: quien copiaba las cookies desde la consola del navegador, o usaba un exportador que deja fuera las cookies protegidas, recibía el aviso de que habían caducado. Ahora el mensaje dice que falta `LOGIN_INFO` y pide exportar todas las cookies de youtube.com a un `cookies.txt`. Si la cuenta se conecta incluso sin ella, KeyTune avisa que las pistas que requieren la cuenta pueden no reproducirse.
