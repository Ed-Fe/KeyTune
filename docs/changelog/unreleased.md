## [Não lançado]

### Adicionado

- **Diagnóstico** (**Ajuda > Diagnóstico**): testa o que o KeyTune precisa para tocar e mostra, em uma caixa de leitura, o que está errado e o que fazer em cada caso.
  - Verifica a biblioteca do MPV e as dependências dela no Windows, o início do player, os dispositivos de áudio, o `yt-dlp`, o Node.js, o YouTube.js, o FFmpeg, a conta do YouTube e, resolvendo um vídeo público de verdade, se o YouTube responde ao YouTube.js e ao `yt-dlp`.
  - Se o player não iniciar ao abrir o KeyTune, o diagnóstico roda sozinho e mostra o motivo antes de o aplicativo fechar. Antes a janela ficava aberta sem funcionar.
  - Ele só lê e testa; não instala nem altera nada no computador.
  - O teste do vídeo usa a internet e não envia os cookies da conta.

### Corrigido

- **O KeyTune não abria o MPV em computadores com driver de vídeo antigo**: a janela mostrava "ctypes.CDLL could not load it" e nada tocava. O loader do Vulkan que vem com drivers de 2016 ou mais velhos não tem funções que o MPV atual precisa, e o Windows recusava carregar a biblioteca.
  - O KeyTune agora leva o próprio `vulkan-1.dll` na pasta `mpv` e usa os drivers de vídeo instalados como antes.
  - Se o MPV não carregar por outro motivo, o diagnóstico diz qual DLL ou função está faltando, ou se o Windows ou o antivírus bloqueou o arquivo.
- **Cookies bons do YouTube Music eram recusados na hora de conectar**: em algumas contas a conexão falhava com "não contém um cookie de autenticação compatível" ou com um erro em inglês sobre `__Secure-3PAPISID`, mesmo com a exportação certa.
  - Um cookie com espaço, acento ou outro caractere fora do padrão escondia todos os que vinham depois dele, inclusive o de autenticação. Agora ele é deixado de lado e o resto é lido.
  - Dá para colar só o valor do cabeçalho `Cookie`, um `cookies.txt` cujas tabulações viraram espaços ao copiar, ou os cabeçalhos sem o `X-Goog-AuthUser`.
  - Se o YouTube confirma que a sessão está conectada mas o menu da conta vem em um formato que o KeyTune não reconhece, a conta é aceita mesmo assim, sem o nome.
  - Quando os cookies já foram trocados pelo navegador, a mensagem diz isso e explica como exportar de novo.
- **Com a conta do YouTube conectada, o MPV não conseguia criar um player novo**: depois que o KeyTune falava com a conta, qualquer player criado em seguida falhava com "access violation". Isso atingia a troca para um vídeo depois de outra mídia e a recriação do player. A biblioteca da conta mudava uma configuração regional do processo que o MPV exige; agora o KeyTune a restaura antes de criar cada player.
