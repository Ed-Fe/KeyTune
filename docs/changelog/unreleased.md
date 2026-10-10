## [Não lançado]

### Corrigido

- **Conectar a conta do YouTube logo depois de abrir o KeyTune**: a conexão com um `cookies.txt` ou com os cookies colados falhava com "não contém um cookie de autenticação compatível", mesmo com a exportação certa. Acontecia com quem conectava a conta antes de usar qualquer coisa do YouTube, como logo depois de instalar. Agora a conta conecta nessa situação também.
- **Cookies sem o `LOGIN_INFO`**: quem copiava os cookies pelo console do navegador, ou usava um exportador que deixa de fora os cookies protegidos, recebia o aviso de que eles tinham vencido. Agora a mensagem diz que falta o `LOGIN_INFO` e pede para exportar todos os cookies de youtube.com em um `cookies.txt`. Se a conta conectar mesmo sem ele, o KeyTune avisa que faixas que exigem a conta podem não tocar.
