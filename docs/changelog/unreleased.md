## [Não lançado]

### Adicionado

- **Player rápido**: `Enter` num arquivo de áudio no Explorador de Arquivos abre uma janela pequena que toca na hora, sem carregar abas, playlists nem a sessão anterior.
  - `Enter` em outro arquivo troca o que está tocando, na mesma janela. `Esc` fecha.
  - As teclas e os anúncios são os mesmos da janela principal.
  - `Ctrl+Enter` continua no KeyTune completo, com a mídia numa playlist nova.
  - Ele não grava recentes, histórico nem sessão.
- **`Enter` no player**: com o foco no player, toca a playlist da aba à vista, de onde ela tinha parado.
- **Histórico de mudanças**: **Ajuda > Histórico de mudanças** mostra o que mudou em cada versão, da mais nova para a mais antiga.
  - O texto vem no idioma da interface, em português, inglês ou espanhol.

### Alterado

- **Trocar de aba não muda mais o que está tocando**: antes, passar para outra playlist parava a música ou carregava a faixa daquela aba. Agora ela continua enquanto você olha as outras abas ou cria uma com `Ctrl+T`.
  - Uma playlist assume a reprodução quando você toca algo nela. `Enter` na faixa em que ela tinha parado retoma daquele ponto.
  - `Espaço`, as setas, **Próxima**, **Anterior**, aleatório e repetição valem para o que está tocando, seja qual for a aba à vista.
  - O título da janela e o status (`S`) dizem o que está tocando.
- **Abrir um arquivo pelo Windows com o KeyTune fechado**: antes abria a janela principal e restaurava a sessão. Agora toca no player rápido.
  - Com o KeyTune já aberto nada muda: o arquivo vai para a playlist atual.
  - Para voltar ao comportamento antigo, desmarque **Usar o player rápido ao abrir arquivos pelo Windows** em `Ctrl+,` > **Geral**.
- **Equalizador para todas as abas**: antes cada aba tinha o seu, e repetir o ajuste pedia **Aplicar em todas as abas**. Agora o que você define em `Ctrl+Shift+E` vale para todas as abas, as novas e o player rápido.
  - Para um ajuste diferente numa playlist, marque **Usar um equalizador só para esta aba**.
  - Os equalizadores por aba de versões anteriores não são mantidos: defina o ajuste de novo, uma vez.
  - O botão **Aplicar em todas as abas** saiu.
- **`T` e `V` mais curtos**: falam só o valor, como "1:20 de 3:40. 36%." e "80%.", sem "Tempo atual:" e "Volume atual:".
- **Status (`S`) mais direto**: começa pela mídia e pelo tempo, por exemplo "Música.mp3, tocando. 1:20 de 3:40. 36%. Item 3 de 12. Volume 80%.".
  - Velocidade, tom, aleatório e repetição só são falados quando estão fora do padrão.
  - A aba só é falada quando não é a da mídia que toca.
- **Notas da atualização no seu idioma**: o diálogo de atualização mostra o que mudou na nova versão em português, inglês ou espanhol, conforme o idioma da interface.
