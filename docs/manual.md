# Manual do KeyTune

O KeyTune é um player de mídia feito para ser usado pelo teclado, com a acessibilidade em primeiro lugar. Ele trabalha bem com playlists, com a navegação por pastas e com a volta ao ponto em que você parou na última vez.

Este projeto foi desenvolvido com assistência de IA, incluindo GitHub Copilot, Codex da OpenAI e Claude Code da Anthropic.

Aqui você encontra os recursos do aplicativo e o passo a passo das tarefas mais comuns. Se você só quer começar a ouvir, leia [Primeiros passos](#primeiros-passos) e [Como abrir mídia](#como-abrir-midia). O resto serve de consulta.

## O que o KeyTune oferece

- Reprodução de áudio e vídeo controlada pelo teclado
- Playlists em abas, com uma fila de reprodução independente
- Explorador de pastas ao lado das abas
- Busca na playlist ou na pasta atual, com navegação entre os resultados
- Biblioteca inteligente: busca global, favoritos, avaliações, histórico e retomada por arquivo
- Temporizador com durações prontas ou pausa ao fim da faixa
- Equalizador para todas as abas ou só para uma, com predefinições e presets próprios
- Painel de letras com busca automática
- Aba KeyTube, com o YouTube Music e o YouTube (`Ctrl+Shift+Y`)
- Transmissões ao vivo do YouTube, com áudio e vídeo opcional
- Rádios online de todo o mundo (`Ctrl+Shift+N`)
- Download de músicas e vídeos do YouTube (`Ctrl+Shift+B`)
- Conversão de áudio e vídeo entre formatos (`Ctrl+Shift+K`)
- AutoDJ, que mistura as faixas da playlist
- Plugins e marketplace
- Restauração do que estava aberto na última sessão
- Anúncios para leitores de tela

## Primeiros passos

1. Baixe o `KeyTune-Setup.exe` mais recente na página de [releases](https://github.com/ed-fe/KeyTune/releases).
2. Execute o instalador e siga as etapas. Na página de tarefas adicionais você pode criar um atalho na área de trabalho e escolher quais formatos de áudio, vídeo e playlist associar ao KeyTune. Tudo isso é opcional e vem desmarcado. Associar um formato põe o KeyTune no menu *Abrir com*; para que ele abra esses arquivos sozinho, ainda é preciso defini-lo como padrão nas configurações do Windows.
3. Nas próximas vezes, se houver uma versão nova, o KeyTune mostra as novidades e pede confirmação antes de baixar e instalar (veja [Atualizações](#atualizacoes)).

O KeyTune toca mídia pelo runtime do MPV, e o instalador já o inclui. Se o player abrir mas não tocar nada, veja [Solução de problemas](#solucao-de-problemas).

## Interface

Na primeira abertura, a janela mostra uma aba de playlist vazia. Ela tem estas áreas:

- **Barra de menus**, no topo: **Arquivo**, **Reprodução**, **Exibir**, **Biblioteca**, **Abas**, **Configurações** e **Ajuda**.
- **Área de abas**, que ocupa quase toda a janela. Cada aba é uma playlist (veja [Playlist, pastas e abas](#playlist-pastas-e-abas)) e se divide em duas partes lado a lado: à esquerda, o navegador de itens, que é a lista da playlist; à direita, a área do player. Para um vídeo, a área do player mostra o quadro de vídeo. Para áudio, ou sem nada carregado, mostra um texto de apoio com os atalhos mais usados.
- **Explorador de pastas**, à esquerda das abas quando aberto com `Ctrl+E`. Mostra as pastas e os arquivos de mídia do computador (veja [Explorador de pastas](#explorador-de-pastas)).
- **Painel de tempo**, abaixo das abas: tempo decorrido, duração, barra de progresso e um resumo dos atalhos principais.
- **Barra de status**, na borda de baixo: o resultado da última ação.

`Tab` ou `Ctrl+B` alternam o foco entre o navegador de itens e o player (com o explorador aberto, `Tab` passa por ele também). `F1`, em qualquer momento, abre a ajuda rápida de atalhos.

## Como abrir mídia

Há três jeitos de pôr mídia no KeyTune: abrir, colar e usar o explorador de pastas. Os três funcionam igual: o que entra vai para a **playlist atual** e começa a tocar. Com `Shift`, entra **sem tocar**, no fim da lista, e o que estava tocando continua.

| Para | Tocando | Sem tocar |
| --- | --- | --- |
| Escolher arquivos | `Ctrl+O` (**Arquivo > Abrir...**) | `Ctrl+Shift+O` (**Arquivo > Abrir sem tocar...**) |
| Colar da área de transferência | `Ctrl+V` | `Ctrl+Shift+V` |
| Usar o explorador de pastas | `Enter` | `Shift+Enter` |

- Um arquivo `.m3u` ou `.m3u8` aberto com `Ctrl+O` vira uma playlist.
- `Ctrl+V` aceita links, caminhos em texto e arquivos ou pastas copiados no Explorador de Arquivos do Windows. De uma pasta entram todas as mídias, inclusive as das subpastas. Links de playlist do YouTube Music são reconhecidos pelo `list=` e abertos como a playlist completa.

Para começar uma lista separada, crie uma playlist nova com `Ctrl+T` e abra ou cole nela. Para abrir um link, copie-o e use `Ctrl+V`.

Formatos de mídia suportados diretamente:

- Áudio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Vídeo: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

**Arquivo > Recentes** guarda, em listas separadas, os últimos arquivos, pastas e playlists que você usou.

### Ouvir um arquivo direto do Explorador de Arquivos do Windows

Com o KeyTune definido como player padrão, `Enter` num arquivo de áudio no Explorador de Arquivos abre o **player rápido**: uma janela pequena que toca o arquivo na hora, sem carregar abas, playlists nem a sessão anterior.

1. No Explorador de Arquivos, selecione o arquivo e pressione `Enter`.
2. Ouça. O leitor de tela anuncia o nome do arquivo no título da janela.
3. Pressione `Esc` ou `Alt+F4` para fechar.

`Enter` em outro arquivo, com o player rápido aberto, troca o que está tocando pelo arquivo novo, na mesma janela. O foco continua no Explorador de Arquivos, e o KeyTune não anuncia nada: você ouve o arquivo novo começar.

| Ação | Atalho |
| --- | --- |
| Reproduzir ou pausar | `Espaço` |
| Voltar ou avançar | `Seta para a esquerda` / `Seta para a direita` |
| Voltar ou avançar 1 minuto | `Shift+Seta para a esquerda` / `Shift+Seta para a direita` |
| Volume | `Seta para cima` / `Seta para baixo` |
| Ir ao início ou ao fim | `Home` / `End` |
| Velocidade | `]` aumenta, `[` diminui, `\` volta ao normal |
| Ouvir o tempo, o volume ou o status | `T` / `V` / `S` |
| Continuar no KeyTune completo | `Ctrl+Enter` (ou o botão **Continuar no KeyTune completo**) |
| Fechar | `Esc` ou `Alt+F4` |

As teclas e os anúncios são os mesmos do player da janela principal: mudar o volume ou avançar não fala nada, e `V` e `T` dizem o volume e o tempo quando você quiser.

`Ctrl+Enter` abre a janela principal e leva a mídia para uma playlist nova. O som não é interrompido: a mídia segue tocando do ponto em que estava, com o mesmo volume e a mesma velocidade, enquanto as abas da última sessão voltam. Abrir o KeyTune pelo menu Iniciar com o player rápido aberto faz o mesmo.

O player rápido não grava nada: o arquivo não entra nos recentes, no histórico nem na sessão, e o volume mudado nele vale só até fechar ou até você continuar no KeyTune completo, que o mantém. Ele começa com o volume da última sessão, ou com o volume padrão se a sessão não é restaurada.

Abrem direto na janela principal, como antes: playlists `.m3u` e `.m3u8`, vídeos quando a saída de vídeo está ligada, e qualquer arquivo quando o KeyTune completo já está aberto (ele vai para a playlist atual). Para usar sempre a janela principal, desmarque **Usar o player rápido ao abrir arquivos pelo Windows** em `Ctrl+,` > **Geral**.

## Reproduzir

### Atalhos de reprodução

| Tecla | O que faz |
| --- | --- |
| `Espaço` | Reproduzir ou pausar |
| `Enter` | Com o foco no player, tocar a playlist da aba à vista, de onde ela parou |
| `Seta esquerda` / `Seta direita` | Voltar ou avançar na mídia (o passo está em **Preferências > Reprodução**) |
| `Shift+Seta esquerda` / `Shift+Seta direita` | Voltar ou avançar 1 minuto |
| `Home` / `End` | Ir ao início ou ao fim da mídia |
| `Seta cima` / `Seta baixo` | Aumentar ou diminuir o volume |
| `Ctrl+.` | Parar |
| `Ctrl+PageUp` / `Ctrl+PageDown` | Faixa anterior ou próxima |
| `Alt+Seta esquerda` / `Alt+Seta direita` | O mesmo, como alternativa |
| `Alt+Seta cima` / `Alt+Seta baixo` | Mover o item atual para cima ou para baixo na playlist |
| `Alt+Home` / `Alt+End` | Ir ao primeiro ou ao último item da playlist |
| `E` | Alternar o modo aleatório |
| `R` | Alternar o modo de repetição |
| `]` / `[` | Aumentar ou diminuir a velocidade |
| `\` | Voltar à velocidade normal |
| `Shift+]` / `Shift+[` | Aumentar ou diminuir o tom, em semitons |
| `Shift+\` | Voltar ao tom original |
| `Alt+D` | Escolher a saída de áudio |
| `Ctrl+Alt+L` | Mostrar ou ocultar o painel de letras |
| `Ctrl+Alt+V` | Alternar o vídeo das transmissões ao vivo |
| `Ctrl+Shift+F` | Pôr o item selecionado na fila |
| `Ctrl+Shift+Q` | Gerenciar a fila |
| `Ctrl+Shift+D` | Configurar o temporizador |
| `T`, `V`, `S` | Anunciar o tempo, o volume e o status |

Os atalhos do YouTube Music, de baixar e de converter estão em [KeyTube](#keytube-youtube-e-youtube-music), [Baixar da internet](#baixar-da-internet) e [Converter mídia](#converter-midia).

`Ctrl+W` fecha a aba ativa. `Ctrl+Shift+W` fecha, ou descarrega, só a mídia atual.

### Fila de reprodução

A fila define o que toca depois da faixa atual, sem depender da ordem da playlist que você está vendo. Ela pertence sempre à playlist que está tocando.

`Ctrl+Shift+F` (ou **Reprodução > Adicionar à Fila de Reprodução**) põe um item na fila ou o tira dela. `Ctrl+Shift+Q` (ou **Reprodução > Gerenciar Fila de Reprodução**) mostra a fila e deixa remover, reordenar ou limpar.

### Temporizador

O temporizador pausa a reprodução depois de um tempo combinado, bom para ouvir algo antes de dormir. Ele **pausa** em vez de parar: a posição fica guardada e `Espaço` continua de onde parou.

Abra com `Ctrl+Shift+D` ou **Reprodução > Temporizador**. As opções:

- **Durações prontas**: 5, 10, 15, 30, 45, 60, 90 ou 120 minutos, direto no submenu.
- **Tempo personalizado**: de 1 a 720 minutos, na caixa de configuração.
- **Ao fim da faixa atual**: a reprodução termina quando a faixa acabar, sem avançar, sem repetir e sem puxar conteúdo relacionado. Não vale para transmissões ao vivo.
- **Não usar temporizador**: cancela o agendamento.

O submenu também tem **Tempo restante** e **Cancelar temporizador**. O player avisa quando faltam 5 minutos e quando falta 1.

### Letras

`Ctrl+Alt+L`, ou a caixa **Letras** no painel de tempo, mostra ou oculta o painel de letras. Ao trocar de faixa, o KeyTune procura a letra sozinho, primeiro no LRCLIB e depois no YouTube Music. O botão **Copiar letra completa** leva o texto para a área de transferência.

## Playlist, pastas e abas

Cada playlist fica numa aba, o que ajuda a separar contextos: uma lista para ouvir agora, uma coleção organizada, uma de testes. A aba à vista decide o que aparece no navegador de itens.

Trocar de aba não mexe no que está tocando: dá para passear pelas playlists, ou criar uma nova com `Ctrl+T`, sem interromper a música. Uma playlist só assume a reprodução quando você toca algo nela.

- `Enter` num item toca esse item, e a playlist dele passa a ser a que toca.
- Cada playlist guarda a faixa e a posição em que parou. `Enter` nessa faixa, numa playlist que não é a que toca, retoma daquele ponto em vez de recomeçar.
- `Espaço`, as setas de avanço e de volume, **Próxima** e **Anterior** valem sempre para o que está tocando, seja qual for a aba à vista. Se nada está carregado, `Espaço` retoma a playlist à vista.
- `Enter`, com o foco no player, passa a reprodução para a playlist à vista: ela volta a tocar de onde tinha parado, e a que tocava guarda a posição dela.
- Aleatório e repetição também valem para a playlist que está tocando. Se nada está carregado, valem para a playlist à vista.
- O título da janela e o status (`S`) dizem o que está tocando. O `S` também diz a aba à vista quando ela é outra.

### Atalhos de abas e itens

- `Ctrl+T`: nova aba de playlist
- `Ctrl+W`: fechar a aba atual
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: próxima aba ou aba anterior
- `Ctrl+Shift+E`: equalizador
- `Ctrl+C`: copiar a seleção como texto e, no caso de arquivos do computador, também como arquivos. Dá para colar em outra playlist, num campo de texto ou no Explorador do Windows
- `Ctrl+Shift+C`: copiar o link ou o caminho da mídia atual (no explorador de pastas, o caminho da seleção)
- `Ctrl+Shift+S`: salvar a playlist atual
- `Ctrl+B`: alternar o foco entre o navegador de itens e o player
- `Ctrl+F`: localizar um item na playlist ou na pasta atual
- `Ctrl+G`: buscar na biblioteca inteira
- `Ctrl+D`: favoritar ou desfavoritar a seleção
- `Ctrl+0` a `Ctrl+5`: avaliar a seleção de zero a cinco estrelas
- `Ctrl+Shift+H`: histórico de reprodução
- `Ctrl+Shift+R`: continuar ouvindo o que ficou pela metade
- `F3` / `Shift+F3`: próximo ou anterior resultado da busca

### Navegador de itens

O navegador fica à esquerda de cada aba e lista os itens da playlist. O que está tocando leva `▶` no começo da linha.

- `Enter`: toca o item selecionado.
- `Delete`: tira o item da playlist.
- `Shift+F10`: abre o menu de contexto do item ou da seleção. Além de copiar, colar (tocando ou não) e remover, o menu traz as ações do YouTube quando a seleção tem itens dessa origem: **Curtir**, **Não gostei**, **Ver detalhes**, **Ver comentários** e **Adicionar à playlist do YouTube Music...**. Quando a aba é uma playlist sua do YouTube Music, também aparece **Remover da playlist do YouTube Music**. Veja [Gerenciar playlists do YouTube Music](#gerenciar-playlists-do-youtube-music).
- `Tab` ou `Esc`: devolve o foco ao player.

### Como as listas funcionam

O explorador de pastas, o KeyTube e as rádios online navegam do mesmo jeito: você entra nos itens, vê o que há dentro e volta. As teclas são as mesmas nos três.

- `Enter`: entra no item quando ele guarda outros itens (uma pasta, um canal, um artista, um país) e **toca** quando ele toca (um arquivo, uma faixa, um vídeo, uma rádio). Álbuns e playlists entram inteiros na playlist atual.
- `Shift+Enter`: adiciona à playlist atual **sem tocar**.
- `Seta para a direita`: mostra o que há dentro do item, na mesma lista, mesmo quando `Enter` tocaria.
- `Backspace`: volta à lista anterior, com a seleção no item que você tinha aberto. No KeyTube e nas rádios, `Seta para a esquerda` e `Alt+Seta para a esquerda` também voltam.
- `Seta para baixo` ou `Page Down` no último item: carrega mais, no KeyTube e nas rádios.
- Letras: pulam para o item que começa com elas.
- `Shift+F10`, a tecla Aplicativos ou o botão direito do mouse: abrem o menu de ações do item.
- Seleção múltipla: `Shift+Setas` selecionam um intervalo e `Ctrl+Setas` movem o foco sem mudar a seleção. `Ctrl+Espaço` marca ou desmarca o item em foco (no explorador, `Ctrl+Espaço` abre a classificação).

### Explorador de pastas

`Ctrl+E` (ou **Arquivo > Explorador de Pastas**) abre, à esquerda das abas, a lista de pastas e de arquivos de mídia do computador. Ele não ocupa uma aba: fica ao lado de qualquer playlist e serve para montá-la aos poucos, sem interromper o que toca. Com o foco nele, `Ctrl+E` fecha a lista; com o foco em outro lugar, leva o foco até ela.

Ele começa em **Este computador**, com as pastas Músicas, Vídeos, Downloads, Área de trabalho e Documentos e as unidades de disco. A pasta em que você parou e a classificação escolhida ficam guardadas para a próxima abertura, e as pastas de **Arquivo > Recentes > Pastas recentes** também abrem aqui.

Além das teclas de [Como as listas funcionam](#como-as-listas-funcionam):

- `Enter` entra na pasta ou toca o arquivo, adicionando-o à playlist atual. Com `Shift+Enter`, de uma pasta entram todas as mídias, inclusive as das subpastas.
- `Ctrl+Shift+F` adiciona a seleção à fila, e `Ctrl+Shift+K` converte os arquivos selecionados (veja [Converter mídia](#converter-midia)).
- `Backspace` sobe para a pasta de cima.
- `Ctrl+C` copia os arquivos ou pastas selecionados, para colar numa playlist ou no Explorador do Windows. `Ctrl+Shift+C` copia os caminhos como texto.
- `Ctrl+Espaço` abre o menu de classificação: por nome, data de modificação, data de criação, tipo ou tamanho, em ordem crescente ou decrescente.
- `F5` atualiza a pasta.
- `Shift+F10` abre o menu com todas as ações: **Tocar agora**, **Adicionar à playlist sem tocar**, **Adicionar à fila de reprodução**, **Abrir em nova playlist**, **Adicionar a pasta atual inteira à playlist**, **Converter...**, **Indexar pasta na biblioteca**, **Copiar**, **Copiar caminho**, **Mostrar no Explorador de Arquivos do Windows**, a classificação, **Atualizar** e **Fechar explorador**.
- `Esc` devolve o foco para onde estava antes de você abrir o explorador.

### Localizar itens

**Digitação rápida.** Na playlist e no explorador, digitar letras ou números leva a seleção ao primeiro item cujo nome começa com o que você digitou. A busca ignora acentos e maiúsculas. Depois de um segundo sem digitar, a próxima letra começa uma busca nova.

**Busca completa.** Para listas grandes, use `Ctrl+F` (ou **Exibir > Localizar item**), que encontra o texto em **qualquer parte** do nome, e não só no começo.

- `Ctrl+F` abre a caixa **Localizar item**. Digite o texto e confirme com `Enter` ou com o botão **Localizar**.
- `F3` vai para o próximo resultado e `Shift+F3`, para o anterior. O menu **Exibir** tem os mesmos comandos.
- A busca percorre os itens da aba ativa: playlists, pastas e listas do KeyTube.
- `F3` repete a última busca sem abrir a caixa. Se ainda não houve busca, abre a caixa.

## Baixar e converter

### Baixar da internet

`Ctrl+Shift+B` baixa músicas e vídeos do YouTube, do YouTube Music e de outros sites que o KeyTune toca. Ele segue a mesma regra do `Ctrl+Shift+K` (converter): com o foco numa lista (a playlist ou os resultados do KeyTube), baixa a **seleção**; com o foco no player, baixa a **mídia atual**. Os mesmos comandos estão em **Arquivo > Baixar da internet**: **Baixar mídia atual**, **Baixar seleção** e **Baixar playlist inteira**. O download usa o `yt-dlp`, o mesmo que já toca essas mídias, e acontece em segundo plano: a reprodução continua normalmente.

1. Selecione o que quer baixar, ou deixe o foco no player para baixar a mídia atual.
2. Pressione `Ctrl+Shift+B`.
3. No diálogo, escolha **Áudio** ou **Vídeo**, a qualidade, a taxa de amostragem (só para áudio convertido) e a pasta. A última escolha vira o padrão das Preferências.
4. Confirme.

Detalhes que vale saber:

- **Sem diálogo.** Desmarque **Sempre mostrar este diálogo ao baixar** para que os próximos downloads comecem direto, com as opções da aba **Download** das Preferências.
- **Qualidade indisponível.** Se a qualidade escolhida não existir para aquela mídia, o KeyTune baixa na original e avisa.
- **Nome do arquivo.** O arquivo leva o mesmo nome que o KeyTune mostra para a faixa (`Artista — Título.mp3`). Um download nunca substitui um arquivo que já está na pasta: se o nome existir, o novo ganha " (2)", " (3)" e assim por diante.
- **Andamento.** Pressione `Ctrl+Shift+B` de novo durante um download para ouvir o andamento ou cancelar.
- **FFmpeg.** Converter o áudio (MP3, FLAC ou outra taxa de amostragem) e baixar vídeo em alta resolução exigem o FFmpeg. Se ele não for encontrado, o KeyTune pergunta se pode baixá-lo (cerca de 90 MB). Se você recusar, o download segue na qualidade original, sem conversão. Um FFmpeg já instalado no sistema também é usado.

**Vários itens de uma vez.** **Baixar seleção** baixa os itens selecionados, e **Baixar playlist inteira** baixa todos os da aba numa subpasta com o nome da playlist. Os dois estão em **Arquivo > Baixar da internet** e no menu de contexto da lista. O KeyTune pede confirmação antes de começar.

Os itens são baixados três de cada vez, com as mesmas opções, e a barra de status mostra a posição na fila. No fim, o player resume quantos deram certo e quantos falharam, e `Ctrl+Shift+B` informa a posição e permite cancelar. Um item que falha não interrompe os outros, e o KeyTune oferece uma lista com cada falha e o motivo, com o botão **Copiar lista**.

**Outros sites.** Um endereço de outro site que o KeyTune toca também pode ser baixado, assim como o link direto de um arquivo de áudio ou vídeo. Rádios e transmissões ao vivo ficam de fora, porque não terminam. Se o endereço for de uma lista, só o primeiro item é baixado. A conta do YouTube não é usada em outros sites.

### Converter mídia

O KeyTune converte arquivos de áudio e de vídeo do computador sem sair do player. `Ctrl+Shift+K` segue a mesma regra do `Ctrl+Shift+B`: com o foco numa lista (a playlist ou o explorador de pastas), converte a **seleção**; com o foco no player, converte a **mídia atual**. Os mesmos comandos estão em **Arquivo > Converter** (**Converter mídia atual** e **Converter seleção**) e no menu de contexto das listas.

O KeyTune pergunta o que fazer e mostra só as opções que servem ao tipo do arquivo:

- **Áudio para vídeo**: gera um vídeo a partir do áudio, com uma imagem parada. Escolha MP4, MKV ou WebM e a resolução (480p, 720p ou 1080p). Se o áudio tiver capa de álbum embutida, ela vira a imagem; sem capa, o fundo é preto.
- **Vídeo para áudio**: extrai o som do vídeo para MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC ou WAV.
- **Áudio para outro formato de áudio**: converte entre MP3, M4A (AAC), OGG (Vorbis), Opus, FLAC e WAV. A capa e as informações da faixa acompanham a conversão para MP3, M4A e FLAC.
- **Vídeo para outro formato de vídeo**: troca só o formato (MP4, MKV, WebM, AVI ou MOV). As faixas compatíveis com o novo formato são copiadas sem recodificar, o que é rápido e não perde qualidade; as incompatíveis são recodificadas. Legendas só são mantidas em MKV.

No diálogo, além do formato, você define:

- a qualidade dos formatos com perdas (128, 192, 256 ou 320 kbps);
- a taxa de amostragem (original, 44100 ou 48000 Hz; o Opus sempre usa 48000 Hz);
- onde salvar: **Mesma pasta do arquivo original** (o padrão) ou **Outra pasta**, que habilita o campo da pasta e o botão **Escolher pasta**.

O diálogo lembra as últimas escolhas. O arquivo original nunca é alterado nem sobrescrito: se já existir um arquivo com o mesmo nome, o novo ganha " (1)", " (2)" e assim por diante.

**Vários arquivos.** Selecione-os na playlist ou no explorador e pressione `Ctrl+Shift+K`. O KeyTune pergunta o modo e mostra quantos arquivos cada um atende. Só os do tipo certo são convertidos. As opções valem para todos. Com **Mesma pasta do arquivo original**, cada arquivo vai para a pasta do próprio original; com **Outra pasta**, todos vão para a pasta escolhida. Os arquivos são convertidos um por vez, com um resumo no fim. Um erro num arquivo não interrompe os demais, e a lista das falhas pode ser aberta e copiada, como nos downloads.

A conversão roda em segundo plano, e a reprodução continua. Pressione `Ctrl+Shift+K` durante uma conversão para ouvir o andamento ou cancelar; um arquivo incompleto nunca fica para trás.

A conversão usa o FFmpeg, o mesmo do download. Se ele não for encontrado, o KeyTune pergunta se pode baixá-lo, como descrito em [Baixar da internet](#baixar-da-internet). Só arquivos do computador são convertidos; para mídias da internet, use `Ctrl+Shift+B`.

## Biblioteca inteligente

Enquanto o `Ctrl+F` procura na lista que está aberta, a **biblioteca inteligente** lembra o que você já abriu e ouviu e deixa tudo pesquisável de uma vez. Ela guarda também favoritos, avaliações, o histórico de reprodução e o ponto em que cada mídia longa parou.

Tudo fica num banco local (`smart_library.db`), na mesma pasta de dados das preferências. Nada sai do seu computador, e o recurso inteiro pode ser desligado em `Ctrl+,` > **Biblioteca**. O menu **Biblioteca** reúne os comandos.

### O que entra no índice

- As mídias de qualquer playlist ou pasta que você abre entram no índice, em segundo plano.
- **Biblioteca > Indexar pasta na biblioteca...** varre uma pasta e as subpastas.
- **Biblioteca > Atualizar pastas indexadas** varre de novo as pastas já indexadas e descarta os arquivos que não existem mais.
- **Biblioteca > Resumo da biblioteca** anuncia quantas mídias, pastas, favoritos e reproduções estão guardados.
- **Biblioteca > Limpar biblioteca...** apaga tudo (índice, favoritos, avaliações, histórico e retomada), com confirmação.

Se você prefere que só as pastas escolhidas por você entrem no índice, desligue **Indexar automaticamente as pastas abertas no navegador** nas preferências. Navegar pelo explorador não indexa nada sozinho: entram no índice as pastas abertas pelos recentes e as que você indexar pelo menu de contexto do explorador.

### Busca global

`Ctrl+G` abre a caixa **Buscar na biblioteca**. Digite o texto e confirme com `Enter` ou com o botão **Procurar**.

- A busca ignora acentos e maiúsculas, e cada palavra digitada precisa aparecer em algum lugar do nome do item ou da pasta.
- O campo **Filtrar** limita a busca a **Tudo na biblioteca**, **Somente favoritos**, **Somente avaliados** ou **Somente já reproduzidos**. Os três últimos funcionam mesmo com o texto vazio.
- Os resultados vêm numa lista com colunas de item, avaliação e pasta.
- A busca é instantânea mesmo com dezenas de milhares de arquivos. Ela casa o começo de cada palavra ("estrad" encontra "Estrada") e, se nada aparece, procura também no meio da palavra ("onita" encontra "Bonita").
- `Enter` (ou o botão **Reproduzir**) abre **todos** os resultados numa nova playlist e começa pela faixa selecionada, de modo que uma busca vira uma lista utilizável.
- **Adicionar à fila** enfileira só o item selecionado, na playlist que está tocando.

### Favoritos e avaliações

Os comandos agem sobre o que estiver selecionado na lista; sem seleção, agem sobre a mídia que está tocando.

- `Ctrl+D`: favorita ou desfavorita.
- `Ctrl+0` a `Ctrl+5`: dá de zero a cinco estrelas.
- **Biblioteca > Anunciar marcadores da seleção**: lê favorito, avaliação e número de reproduções do item.
- **Biblioteca > Abrir favoritos em nova playlist**: monta uma playlist com tudo que você favoritou.

Os mesmos comandos estão no menu de contexto da lista (`Shift+F10`).

Favorito e avaliação aparecem ao lado do nome, na própria lista, por exemplo `Estrada — favorito, 5 estrelas`, tanto nas playlists quanto no explorador de pastas. Assim o leitor de tela fala o marcador junto com o item.

### Histórico de reprodução

`Ctrl+Shift+H` abre o **Histórico de reprodução**. O campo **Ver** escolhe entre três visões, e as colunas mudam junto:

- **Todas as reproduções**: uma linha por vez que a mídia tocou, com quando tocou, onde parou e a origem (playlist local, pasta, mídia remota ou YouTube Music).
- **Agrupado por mídia**: uma linha por mídia, com quantas vezes tocou, a última vez e os marcadores.
- **Mais tocadas**: o mesmo agrupamento, da mais tocada para a menos tocada.

**Filtrar por texto** reduz a lista. `Enter` (ou **Reproduzir**) toca de novo, e **Adicionar à fila** enfileira. **Remover entrada** tira uma reprodução da lista sem apagar a mídia do índice; nas visões agrupadas o botão vira **Remover do histórico** e apaga todas as reproduções daquela mídia. **Limpar histórico** apaga tudo, com confirmação.

Uma faixa só entra no histórico depois de tocar o bastante para contar como ouvida, e as entradas mais antigas saem quando o histórico passa do limite das preferências.

Este histórico é local e não tem relação com **Salvar o que ouvi no histórico do YouTube Music**, que registra na sua conta do YouTube Music.

### Retomar de onde parou

Podcasts, audiolivros e vídeos longos voltam a tocar do ponto em que pararam. A regra é conservadora de propósito:

- vale só para arquivos locais, porque streams não têm uma linha do tempo estável entre sessões;
- vale só para mídias acima da **duração mínima** configurada (10 minutos, por padrão);
- parar dentro da **margem** configurada (30 segundos, por padrão) do começo ou do fim não cria ponto de retomada;
- chegar ao fim da faixa apaga a marca, e na próxima vez ela recomeça do início.

**Biblioteca > Continuar ouvindo** (`Ctrl+Shift+R`) abre uma playlist com tudo que ficou pela metade, do mais recente para o mais antigo, e cada item mostra onde parou. **Biblioteca > Apagar posições de retomada** limpa todas de uma vez.

### Playlists inteligentes

Uma playlist inteligente é uma regra salva, não uma lista fixa. Ela é montada toda vez que você a abre, então acompanha as mudanças de avaliação e de histórico: "cinco estrelas que não toco há 30 dias" continua certa um mês depois, sozinha.

**Biblioteca > Playlists inteligentes** lista as regras salvas, para abrir com um comando só, e **Gerenciar playlists inteligentes...** cria, edita e remove. No editor, tudo é campo de teclado, sem construtor visual:

- **Somente favoritos** e **Avaliação mínima** filtram pelos seus marcadores.
- **Sem tocar há pelo menos (dias)** acha o que anda esquecido, e **Incluir mídias nunca tocadas** decide se o que nunca tocou entra junto.
- **Reproduções mínimas** vai pelo outro lado: só o que você já ouviu bastante.
- **Limitar à pasta** restringe a uma pasta e a tudo que está abaixo dela.
- **Incluir mídias remotas** traz também links do YouTube Music e rádios, que por padrão ficam de fora.
- **Ordenar por** e **Número máximo de itens** definem o que sai e em que ordem.

Cada mudança atualiza o **Resumo da regra**, no fim da caixa, numa frase: a forma mais rápida de conferir o que a regra vai reunir antes de salvar.

## KeyTube: YouTube e YouTube Music

O KeyTube é a central do KeyTune para o YouTube Music e o YouTube comum. Nas versões até a 2.0.6 ela se chamava YouTube Music e cuidava só da música; hoje reúne também vídeos, canais, inscrições e comentários do YouTube. Abra com `Ctrl+Shift+Y` (ou **Exibir > KeyTube por aba**). Ela é uma aba separada, então você pode deixar a biblioteca local numa e o KeyTube em outra.

Para a aba funcionar, ative a integração em `Ctrl+,` > **Recursos adicionais** e conecte uma conta do YouTube. A mesma conta serve ao YouTube e ao YouTube Music.

A integração depende de como o site muda e de como o `yt-dlp` lê essas páginas. Por isso podem acontecer erros, falhas temporárias e paradas sem explicação aparente. Quando isso acontece, geralmente basta atualizar as dependências ou tentar mais tarde.

### Conta e biblioteca

A aba tem duas partes. Em cima, a seção **Conta e biblioteca**; embaixo, o campo de busca e **uma lista só**, por onde passa todo o resto: sua biblioteca, a busca e o que há dentro de cada item.

**Conta e biblioteca** mostra a conta conectada, o resumo da biblioteca carregada e a última mensagem de operação. Os botões:

- **Conectar conta...**: abre o diálogo para conectar uma conta ou renovar a autenticação salva.
- **Desconectar conta**: remove a autenticação salva nesta instalação.
- **Atualizar biblioteca**: busca de novo as playlists e mixes da conta e atualiza as avaliações de músicas visíveis na conta.
- **Nova playlist...**: cria uma playlist na sua conta. O player pede o nome e a privacidade (veja [Gerenciar playlists do YouTube Music](#gerenciar-playlists-do-youtube-music)).

**Curtir** e **Não gostei** são enviados à conta conectada, então aparecem também no YouTube Music do celular e de outros aparelhos. O KeyTune tira as faixas marcadas como não gostei das playlists e rádios da conta. Uma avaliação feita fora do KeyTune só é percebida quando a faixa volta a aparecer; **Atualizar biblioteca** força a verificação.

### A lista

A lista funciona como o explorador de pastas (veja [Como as listas funcionam](#como-as-listas-funcionam)) e começa no **Início**, com sete itens:

- **Suas playlists e mixes**: as da conta conectada. `Enter` abre a playlist numa aba própria, de onde dá para editá-la na conta; `Seta para a direita` mostra as faixas na própria lista. Exige conta conectada.
- **Curtidas**: as faixas curtidas (a playlist *Curtidas* da sua conta). Exige conta conectada.
- **Histórico**: seu histórico de reprodução do YouTube Music. Exige conta conectada.
- **Vídeos das inscrições**: os vídeos novos dos canais em que você está inscrito, com duração, visualizações e data. Exige conta conectada e o YouTube.js ativado.
- **Canais inscritos**: os canais em que você está inscrito. Cada um abre como qualquer canal, para você escolher entre vídeos, Shorts, transmissões ao vivo e playlists. Exige conta conectada e o YouTube.js ativado. As duas listas de inscrições são só para leitura: inscrever-se e cancelar a inscrição continuam sendo feitos no YouTube.
- **Em alta**: *Global* e os continentes. Entre num continente, escolha o país, e as paradas e destaques em alta aparecem como playlists que você pode tocar, abrir ou salvar na biblioteca. Não exige conta.
- **Moods e gêneros**: as categorias de climas e gêneros do YouTube Music (*Foco*, *Treino*, *Pop*, *Rock*...). Entre numa categoria para ver as playlists dela. Não exige conta.

No KeyTube, vale ainda:

- `Backspace` volta um nível por vez, até o **Início**. Dá para encadear: de um artista para um álbum, de um canal para uma playlist dele.
- Cada lista traz uma parte dos itens por vez (25, ou o que estiver em **Itens carregados por vez**, nas preferências). Ao chegar ao fim, descer mais traz a parte seguinte. **Carregar a lista inteira**, no menu **Ações...**, traz de uma vez o que falta; numa busca ou num canal, que não têm fim conhecido, para em 1000 itens por vez.
- O botão **Ações...** abre o menu do item: **Tocar**, **Adicionar sem tocar**, **Ver conteúdo**, **Voltar à lista anterior**, **Carregar a lista inteira**, **Ver comentários**, **Ver detalhes**, **Ir para o canal** (ou **Ir para o artista**, seguido do nome), **Adicionar seleção...** (numa nova playlist ou numa aberta), **Baixar seleção...** e **Salvar no YouTube Music** (playlists ou faixas compatíveis). Numa das suas playlists, o menu também traz **Excluir playlist do YouTube Music...**, que a exclui da conta, com confirmação, e só vale para playlists que você criou. Num comentário, traz **Ler o comentário inteiro**.
- `Shift+Enter` numa das suas playlists adiciona as faixas à playlist atual sem tocar.
- `Ctrl+Shift+B` (ou **Baixar seleção...**) baixa o que está selecionado. Com uma **playlist ou um álbum**, o KeyTune busca todas as faixas de dentro e baixa tudo. Você escolhe a pasta de destino; cada playlist ou álbum vira uma **subpasta com o nome dele**, e as faixas e vídeos avulsos ficam na própria pasta, inclusive numa seleção mista. Duas listas com o mesmo nome ganham pastas separadas (*Mix* e *Mix (2)*), e uma faixa que está em duas playlists é baixada nas duas, para cada pasta ficar completa.

Logo acima da lista, uma linha diz onde você está e quantos itens há (por exemplo, *Em alta — Europa: 24 itens*).

### Buscar e abrir links

- **Buscar ou colar link**: digite o que procura e pressione `Enter`. Os resultados entram por cima do **Início**, e `Backspace` volta para ele.
- **Colar um link**: um link de playlist, mix ou vídeo do YouTube Music ou do YouTube colado nesse campo é aberto com `Enter`, em vez de ser pesquisado.
- **Em** e **Tipo**: duas caixas ao lado do campo. **Em** escolhe onde buscar (*YouTube Music* ou *YouTube*) e **Tipo**, o que buscar ali. Nas duas, a primeira letra pula para a opção.
    - No *YouTube Music*: *Músicas* (faixas do catálogo), *Vídeos* (videoclipes e vídeos do YouTube Music), *Álbuns* (álbuns, singles e EPs), *Artistas* e *Playlists* (do catálogo do YouTube Music).
    - No *YouTube*: *Vídeos* (em geral, sem exigir conta), *Canais* e *Playlists*.
- **Dentro de um canal ou artista**: ao entrar, a lista mostra primeiro o que há para ver. Num canal do YouTube: *Vídeos*, *Shorts*, *Ao vivo* e *Playlists*. Num artista do YouTube Music: *Músicas*, *Álbuns*, *Singles e EPs*, *Vídeos* e *Artistas parecidos*. Entre no que quiser; `Backspace` volta para escolher outro.

### Detalhes de vídeos e músicas

**Ver detalhes**, no menu **Ações...** (ou no menu de contexto da playlist, para um item do YouTube), abre uma caixa de leitura com título, canal e inscritos, duração, visualizações, curtidas, data de publicação e a descrição inteira. Para a mídia que está tocando, use `Ctrl+Shift+I` (**Reprodução > Ver detalhes da mídia atual**). O botão **Ir para o canal**, ou **Ir para o artista** numa faixa do YouTube Music, abre o canal ou o artista no KeyTube; o mesmo comando está no menu **Ações...**.

### Comentários

**Ver comentários**, no menu **Ações...** de um vídeo ou de uma música, abre os comentários na própria lista, por cima do que você via; `Backspace` volta. Para a mídia que está tocando, use `Ctrl+Shift+M` (**Reprodução > Ver comentários da mídia atual**), que abre a aba já nos comentários.

- Cada linha traz o autor, o texto, a data, as curtidas e quantas respostas há. O comentário fixado pelo canal vem marcado como *fixado*.
- `Enter` abre o comentário inteiro numa caixa de leitura; `Esc` fecha.
- `Seta para a direita`, num comentário com respostas, abre as respostas.

Com o YouTube.js ativado (**Preferências > Recursos adicionais**), os comentários chegam em menos de um segundo, no idioma do conteúdo, com paginação e respostas. Sem ele, o KeyTune usa o yt-dlp, que é mais lento, traz só os 20 primeiros comentários, sem respostas, e com datas em inglês.

### Idioma do áudio

**Reprodução > Idioma do áudio da mídia atual...** lista as faixas de áudio do vídeo do YouTube que está tocando (a original e as dublagens) e passa a tocar a escolhida a partir do mesmo ponto. A escolha vale para aquela mídia até você fechar o KeyTune. Para valer para todas, use **Áudio dos vídeos dublados** nas preferências.

### Transmissões ao vivo

Cole o link de uma transmissão ao vivo do YouTube no campo **Buscar ou colar link** (ou use `Ctrl+V`, como em qualquer link). O KeyTune reconhece a transmissão sozinho.

- Ela toca no momento atual, sem retomar de uma posição salva. A barra de tempo mostra um rótulo fixo no lugar da duração, e `T` informa há quanto tempo você está assistindo.
- Com **Mostrar o vídeo das transmissões ao vivo** ligado (o padrão), a imagem aparece na área do player mesmo com **Desativar saída de vídeo** marcado. O vídeo é limitado a 720p. Desligado, a transmissão toca só o áudio, na variante mais leve. `Ctrl+Alt+V` alterna a opção e reinicia a transmissão no novo modo.
- Não dá para avançar, voltar nem ir ao início ou ao fim. Pausar e retomar continua de onde parou.
- Se a conexão cair, o player tenta reconectar até três vezes e avisa. Se a transmissão já tiver terminado, o player avisa em vez de tocar a gravação desde o começo.
- Uma transmissão agendada que ainda não começou avisa; tente de novo quando ela iniciar.
- Transmissões ao vivo ficam fora do AutoDJ e do crossfade, não têm letra e não geram ponto de retomada.

### Rádio a partir da faixa atual

Com uma música do YouTube Music tocando, pressione `Ctrl+R` (ou use **Reprodução > Iniciar rádio desta faixa**). O KeyTune abre uma aba nova, mantém a posição da reprodução e põe a faixa atual como item 1, sem continuar a fila da rádio anterior.

O KeyTune evita repetir faixas da playlist de origem e das últimas rádios que você abriu. Como quem escolhe os candidatos é o YouTube Music, não há garantia de músicas diferentes; se não houver novidades, a aba nova fica só com a faixa inicial.

Não confunda com as [rádios online](#radios-online), que são estações de rádio de verdade.

### Gerenciar playlists do YouTube Music

Além de abrir e salvar playlists, o KeyTune edita suas playlists direto na conta conectada. Tudo isto exige conta conectada e muda a playlist **na sua conta do YouTube Music**. Excluir não tem volta pelo player.

**Adicionar faixas.** Selecione uma ou mais faixas do YouTube Music (na playlist atual ou nos resultados da busca) e use **Adicionar à playlist do YouTube Music...** no menu de contexto (`Shift+F10`). Para adicionar a faixa que está tocando, pressione `Ctrl+Shift+A`. Aparece a lista das suas playlists editáveis; mixes e rádios personalizadas não entram porque não aceitam edição. No topo há **Criar nova playlist...**, que cria uma playlist já com a seleção.

**Remover faixas.** Com uma playlist sua aberta na aba atual, selecione as faixas e use **Remover da playlist do YouTube Music** no menu de contexto. O player pede confirmação. A remoção só é oferecida em playlists que você criou ou em que é colaborador.

**Criar uma playlist.** Use **Nova playlist...** (na seção *Playlists e mixes*) para criar uma vazia, ou **Criar nova playlist...** no diálogo de adicionar faixas para criar já com a seleção. Nos dois casos o player pede o **nome** e a **privacidade**: *Privada* (só você vê), *Não listada* (visível para quem tiver o link) ou *Pública* (aparece no seu perfil e pode surgir em buscas). O padrão é Privada.

**Excluir uma playlist.** Selecione a playlist em *Playlists e mixes* e use **Excluir playlist...**. Só dá para excluir playlists que você criou.

### Conectar a conta

Para usar a sua biblioteca (playlists salvas, histórico, curtidas e avaliações), conecte uma conta. O KeyTune não pede a sua senha: ele usa os cookies do navegador em que você entrou no YouTube.

Abra o KeyTube (`Ctrl+Shift+Y`) e, na seção **Conta e biblioteca**, ative **Conectar conta...**. O diálogo **Conectar ao YouTube** tem dois modos:

1. **Informar manualmente (arquivo ou texto)**: o modo padrão e o que dura. Você exporta um `cookies.txt` de uma janela anônima e escolhe o arquivo.
2. **Exportar do navegador instalado**: mais rápido, mas a conexão cai quando você volta a usar o YouTube nesse navegador.

O botão **Como exportar os cookies...** abre um resumo destas instruções numa caixa de leitura.

#### O que são cookies

Cookies são pequenos arquivos de texto que os navegadores guardam para lembrar preferências e logins. Quando você entra no YouTube Music, o navegador salva cookies com a sua autenticação. Ao conectar a conta no KeyTune, o aplicativo usa essa sessão para acessar a sua biblioteca.

#### Por que a conexão cai: a troca de cookies

Por segurança, o YouTube troca os cookies da conta com frequência enquanto você usa o site. Quando o navegador recebe os cookies novos, os que o KeyTune guardou deixam de valer, e a conta aparece como desconectada, mesmo que ontem estivesse funcionando. Não é defeito do KeyTune nem da sua conta.

A troca só acontece numa sessão que continua sendo usada. Por isso o caminho que dura é exportar os cookies de uma sessão que o navegador nunca mais vai abrir: uma janela anônima, fechada logo depois da exportação.

Quando os cookies deixam de valer, o KeyTune avisa que o YouTube não os aceita mais. Conecte de novo com um arquivo novo; o antigo não volta a funcionar.

#### Conectar com um cookies.txt (recomendado)

**Antes de começar**, instale no navegador a extensão [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).

**1. Ativar a extensão em janelas anônimas.**

1. Pressione `Ctrl+L` para focar a barra de endereços.
2. Pressione `Escape` para sair da caixa de edição da barra de endereços.
3. Pressione `Alt+F` para abrir o menu do navegador.
4. Com as setas, vá até **Extensões**, abra o submenu com `Enter` e escolha **Gerenciar extensões**.
5. Ache **Get cookies.txt LOCALLY** e clique em **Detalhes** (ou "Saiba mais").
6. Na página de detalhes, ative **Permitir em abas privadas** (ou **Permitir em navegação anônima**).
7. Feche a página e volte ao navegador.

**2. Entrar e exportar os cookies.**

1. Abra uma janela anônima (`Ctrl+Shift+N` ou `Ctrl+Shift+P`). Ela deve ser a única janela anônima aberta.
2. Vá para [music.youtube.com](https://music.youtube.com/) e entre com a sua conta Google.
3. Abra a extensão **Get cookies.txt LOCALLY** e clique em **Exportar** (ou **Download**) para salvar o `cookies.txt`.
4. Feche a janela anônima sem abrir mais nada nela.

Isso costuma bastar. Se a conta cair mesmo assim, repita a exportação com um passo a mais, recomendado pelo `yt-dlp`: depois de entrar na conta e antes de exportar, pressione `Ctrl+L`, digite `youtube.com/robots.txt` e pressione `Enter`. Abre uma página só de texto; não precisa fazer nada nela. Exporte os cookies com essa página aberta e feche a janela.

**3. Importar no KeyTune.**

1. No diálogo **Conectar ao YouTube**, deixe **Informar manualmente (arquivo ou texto)** escolhido.
2. Em **Arquivo de conexão**, escolha o `cookies.txt` baixado e ative **Conectar**.

No lugar do arquivo, você também pode colar em **Dados copiados do navegador** o conteúdo do `cookies.txt`, os cabeçalhos HTTP de um pedido do YouTube Music ou só o valor do cabeçalho `Cookie`.

#### Conectar pelo navegador instalado

Use este modo se não quiser instalar a extensão. Ele copia a sessão normal do navegador pelo `yt-dlp`, então vale o que está em [Por que a conexão cai](#por-que-a-conexao-cai-a-troca-de-cookies): a conexão dura enquanto você não usar o YouTube nesse navegador. Funciona melhor com um navegador em que você não assiste YouTube.

1. Entre na sua conta no [YouTube Music](https://music.youtube.com/) nesse navegador e feche-o por completo.
2. No diálogo **Conectar ao YouTube**, escolha **Exportar do navegador instalado**.
3. Escolha o navegador na lista e ative **Conectar**.

O Firefox é o que funciona melhor. No Windows, Chrome, Edge e Brave protegem os cookies de um jeito que o `yt-dlp` não consegue abrir, e a exportação costuma falhar; nesse caso use o Firefox ou o modo manual.

#### Mais de uma conta Google

Se a sessão tiver mais de uma conta Google, o KeyTune pergunta qual usar logo depois de conectar. A biblioteca e as inscrições passam a ser dessa conta. Para trocar depois, ative **Atualizar acesso...** e conecte de novo.

#### Segurança

O `cookies.txt` guarda a autenticação da sua conta. Por isso:

- use o arquivo só no seu computador;
- não o compartilhe com ninguém;
- apague-o depois de importar, se quiser: a cópia interna do KeyTune tem só os cookies do YouTube necessários para a conexão;
- ao desconectar a conta no KeyTune, os cookies guardados são removidos.

### Atalhos do KeyTube

- `Ctrl+Shift+Y`: abrir o KeyTube
- `Ctrl+R`: iniciar uma rádio a partir da faixa atual
- `Ctrl+Shift+A`: adicionar a mídia atual a uma playlist do YouTube Music
- `Ctrl+Shift+I`: ver os detalhes da mídia atual
- `Ctrl+Shift+M`: ver os comentários da mídia atual
- `Ctrl+L`: curtir a mídia atual
- `Ctrl+Shift+L`: marcar a mídia atual como não gostei (e pular para a próxima faixa)
- `A`: ligar ou desligar o conteúdo relacionado ao fim da playlist
- `Enter` no campo de busca: pesquisar; com resultados, o foco vai para a lista
- `Esc`: fechar a aba, quando ela estiver em foco

## Rádios online

`Ctrl+Shift+N` (ou **Exibir > Rádios online por aba**) abre uma aba para ouvir rádios de todo o mundo. As estações vêm do [Radio Browser](https://www.radio-browser.info/), um diretório aberto mantido pela comunidade. Não é preciso conta nem ativar nada em **Recursos adicionais**: as rádios tocam direto, sem passar pelo `yt-dlp`.

A aba tem um campo de busca e, embaixo, uma lista só, que funciona como o explorador de pastas e como a lista do KeyTube: você entra nos itens e volta.

### O início

A lista começa no **Início**, com estes itens:

- **Rádios favoritas**: as que você marcou com `Ctrl+D`.
- **Ouvidas recentemente**: as últimas rádios que você tocou.
- **Rádios do seu país**: as do país que o KeyTune usa como o seu. Por padrão é o do Windows; você pode escolher outro em **Preferências > Rádios online**, em **Meu país**, ou no menu de ações do país, dentro da aba (**Definir ... como o meu país**).
- **Mais ouvidas no mundo**.
- **Países**: escolha um país e veja as **Mais ouvidas**, **Todas, em ordem alfabética** ou **Por estado ou região**.
- **Gêneros**: escolha um gênero para ver as rádios dele.
- **Idiomas**: escolha um idioma para ver as rádios dele.

### Teclas e ações

Além das teclas de [Como as listas funcionam](#como-as-listas-funcionam):

- `Ctrl+D`: adiciona a rádio às favoritas ou a tira delas. É o mesmo favorito das playlists, e a lista marca a rádio como "favorita".
- `Ctrl+C`: copia o endereço do stream da rádio selecionada.
- O botão **Ações...** abre o menu com **Tocar**, **Adicionar sem tocar**, **Ver conteúdo**, **Voltar à lista anterior**, **Adicionar rádio manualmente...**, **Adicionar às favoritas** (ou **Remover das favoritas**), **Ver detalhes da rádio**, **Abrir o site da rádio no navegador**, **Copiar o endereço do stream** e **Votar nesta rádio no diretório**. Com uma rádio tocando, o menu também deixa favoritá-la mesmo que ela não esteja selecionada.

**Ver detalhes da rádio** abre uma caixa de leitura com nome, país, estado ou região, idioma, gêneros, qualidade (codec e taxa de bits), votos, ouvintes nas últimas 24 horas, site e endereço do stream, com um botão para abrir o site. **Votar nesta rádio no diretório** registra o seu voto no Radio Browser.

### Buscar e colar endereços

Digite o nome de uma rádio no campo de busca e pressione `Enter`. A caixa **Em** escolhe onde procurar: **Todo o mundo** ou só o seu país. Se você colar no campo o endereço de um stream, ele toca direto, sem busca, mas sem ir para as favoritas.

### Adicionar rádio manualmente

Quando uma rádio não estiver no diretório do Radio Browser, o botão **Adicionar rádio manualmente...** (alcançável com `Tab`, logo após o campo de busca, ou pelo menu **Ações...**) abre uma caixa com dois campos: o **nome** da rádio e o **endereço do stream ou de um arquivo M3U**. Ao confirmar com **OK**, a rádio é cadastrada e vai direto para as **Rádios favoritas**, e o KeyTune avisa com um anúncio de status.

### Como a rádio toca

A rádio entra na playlist atual com o nome da estação. Ela toca como uma transmissão ao vivo só de áudio: não dá para avançar nem voltar, e ela fica fora do AutoDJ e do crossfade.

A música que a estação anuncia aparece na barra de status, no formato *Estação: título*, e entra no anúncio de status (`S`). As recentes saem do histórico de reprodução.

## Equalizador

`Ctrl+Shift+E` (ou **Exibir > Equalizador**) abre o equalizador. O ajuste vale para tudo o que o KeyTune toca: todas as abas, as que você abrir depois e o player rápido.

### Como usar

A caixa **Ativar equalizador** liga ou desliga o efeito.

O campo **Preset** lista todos os presets. Os embutidos levam o sufixo *(embutido)*. Ao escolher um, **Descrição** mostra uma nota sobre o perfil sonoro e **Resumo do preset** traz a pré-amplificação e o valor de cada banda, para você conferir antes de aplicar.

#### Botões de gerenciamento

- **Novo...**: cria um preset personalizado do zero. O editor pede o nome, a pré-amplificação e o ganho de cada banda. Use quando quiser uma curva que não existe entre os embutidos.
- **Editar...**: edita um preset personalizado. Só aparece assim quando o selecionado é personalizado.
- **Salvar cópia...**: quando o selecionado é embutido, é este o botão que aparece. Cria uma versão editável baseada nele, o caminho certo para partir de um preset pronto e ajustar.
- **Duplicar...**: copia um preset personalizado com outro nome, sem mexer no original. Não vale para os embutidos.
- **Excluir**: remove de vez o preset personalizado selecionado. Não vale para os embutidos.

#### Equalizador só para uma aba

Uma playlist pode soar diferente das outras: audiolivros com a voz realçada, por exemplo. Com ela tocando, abra o equalizador e marque **Usar um equalizador só para esta aba**. O campo **Aba alvo** mostra de qual playlist se trata.

- Marcada, a aba começa com o ajuste que já estava valendo, e o que você mudar fica só nela.
- Desmarcada, a aba volta a seguir o equalizador de todas as abas.

#### Editor de preset

O editor tem o campo do nome, a pré-amplificação e um controle por banda de frequência. Cada banda vai de -12,0 dB a +12,0 dB: valores positivos reforçam a frequência e negativos atenuam. A pré-amplificação ajusta o ganho geral antes de todas as bandas.

### Presets embutidos

O KeyTune traz 18 presets:

| Preset | Perfil |
|---|---|
| Padrão | Curva neutra, mantém o som original |
| Clássico | Realça definição e brilho sem exagerar nos graves |
| Club | Graves e agudos mais animados |
| Dance | Mais impacto no grave e brilho no topo |
| Graves profundos | Prioriza subgraves e graves, para dar peso à batida |
| Graves e agudos | Curva em V, com graves fortes e agudos brilhantes |
| Agudos realçados | Destaca detalhes, vozes e brilho geral |
| Fones de ouvido | Equilíbrio pensado para fones, com sensação de clareza |
| Sala ampla | Cria uma sensação mais aberta e ampla |
| Ao vivo | Presença de palco e ambiência |
| Festa | Curva para volumes casuais e músicas animadas |
| Pop | Voz, brilho e graves limpos |
| Reggae | Mais corpo nos graves, com médios relaxados |
| Rock | Ataque de guitarras, caixa e presença geral |
| Ska | Baixo firme, com médios e agudos vivos |
| Suave | Escuta tranquila, reduz a agressividade |
| Rock suave | Equilíbrio com leve presença de voz e brilho |
| Techno | Batida, subgrave e brilho eletrônico |

### Dicas

- Reduza a pré-amplificação se o som começar a distorcer.
- Para ajustar uma curva pronta, use **Salvar cópia...** sobre o preset embutido. Para experimentar sem perder a versão atual, use **Duplicar...**.

## AutoDJ

O AutoDJ mistura as faixas da playlist como um DJ faria, em vez de cortar de uma para outra. Ele não faz parte do instalador: o KeyTune baixa as bibliotecas de análise (`librosa`, NumPy, SciPy, Numba e PyAV) depois que você confirma, em **Preferências > Recursos adicionais**. Depois de instalado, **Reprodução > Ativar AutoDJ** liga e desliga.

Ele analisa a faixa atual e as próximas opções em segundo plano e escolhe a seguinte pela energia, pela tonalidade, pelo volume e pelo andamento, evitando repetir artistas recentes. Quando o ritmo é confiável, alinha as batidas das duas faixas durante a sobreposição. A fila manual sempre tem prioridade. Se a análise atrasar, falhar ou não tiver confiança, o player usa o crossfade comum ou segue para a próxima faixa normalmente.

**Reproduzir playlist com AutoDJ** cria uma aba separada, sem mexer na playlist original. A faixa atual começa na hora, e o KeyTune mantém até cinco músicas preparadas à frente. A aba tem um campo de leitura com a origem, quantas faixas estão preparadas, a atividade da análise e a próxima transição: BPM, ajuste de andamento e, quando é preciso uma transição comum, o motivo. Cada item aparece como tocado, tocando, próximo ou preparado.

Os controles da sessão trocam a próxima faixa, recalculam a sequência, adicionam arquivos, pausam ou retomam a preparação e encerram a sessão mantendo o trecho já preparado. As mesmas ações estão em `Shift+F10`, sobre a lista. A sessão é restaurada junto com o player.

As opções do AutoDJ estão em **Preferências > Reprodução** e **Recursos adicionais**; veja [Configurações](#configuracoes).

## Personalizar o teclado

**Configurações > Personalizar teclado** lista cada ação do player com o atalho em vigor. A tela tem duas abas: **Atalhos do player**, que valem com a janela do KeyTune em foco, e **Atalhos globais**, que valem de qualquer lugar do Windows.

Em cada aba:

- **Filtrar ações** procura pelo nome da ação, pela categoria ou pelo próprio atalho. Digitar "volume" ou "Ctrl+Shift" já reduz a lista.
- `Enter` na lista (ou **Alterar atalho**) abre um campo que captura a combinação que você pressionar. `Tab` sai do campo, `Enter` confirma e `Esc` cancela.
- `Delete` na lista (ou **Remover atalho**) deixa a ação sem atalho.
- **Restaurar padrão** devolve o atalho original da ação; **Restaurar todos** faz isso com a aba inteira.
- Nada muda até você escolher **Salvar**.

Se o atalho escolhido já pertence a outra ação, o KeyTune diz qual e pergunta se pode passá-lo para a nova; a antiga fica sem atalho. Assim nunca há duas ações no mesmo atalho.

Algumas teclas não podem ser usadas, porque servem para navegar e editar: `Tab`, `Shift+Tab`, `Ctrl+Tab`, `Esc`, `Enter`, `Alt+F4`, `Shift+F10`, `Ctrl+A`, `Ctrl+C`, `Ctrl+V`, `Ctrl+X` e `Ctrl+Z`.

Um atalho sem `Ctrl` nem `Alt` (como `Espaço`, `P` ou `Shift+Seta direita`) se comporta como os padrão: só age com o foco no player. Na lista de itens e nos campos de texto a tecla continua sendo do controle. Atalhos com `Ctrl` ou `Alt` agem em qualquer ponto da janela, menos dentro de um campo de texto.

Os menus passam a mostrar o atalho novo, e `F1` lista no fim da ajuda o que você mudou.

### Atalhos globais

Funcionam com o KeyTune minimizado, na bandeja do sistema ou com outro programa em primeiro plano. Ficam desligados até você marcar **Ativar atalhos globais**, na aba **Atalhos globais**. Disponível só no Windows.

| Atalho padrão | Ação |
| --- | --- |
| `Ctrl+Alt+Shift+P` | Reproduzir ou pausar |
| `Ctrl+Alt+Shift+Seta direita` / `Seta esquerda` | Próxima faixa / faixa anterior |
| `Ctrl+Alt+Shift+X` | Parar |
| `Ctrl+Alt+Shift+Seta acima` / `Seta abaixo` | Aumentar / diminuir o volume (o volume novo é falado) |
| `Ctrl+Alt+Shift+I` | Anunciar status |
| `Ctrl+Alt+Shift+T` | Anunciar tempo |
| `Ctrl+Alt+Shift+K` | Mostrar ou ocultar o KeyTune na bandeja do sistema |
| `Ctrl+Alt+Shift+M` | Minimizar ou restaurar a janela |

Avançar, voltar, embaralhar, modo de repetição, anunciar volume e trazer o KeyTune para a frente vêm sem atalho; dá para definir um na mesma tela. Atalhos globais precisam de `Ctrl`, `Alt` ou da tecla `Windows`, senão a tecla deixaria de funcionar nos outros programas. Se outro programa já usa a combinação, o KeyTune avisa ao salvar e aquele atalho fica sem efeito até você escolher outro.

### Bandeja do sistema

**Arquivo > Ocultar na bandeja do sistema** (ou `Ctrl+Alt+Shift+K`, com os atalhos globais ligados) esconde a janela e deixa um ícone perto do relógio, e a música continua. Para chegar ao ícone pelo teclado, use `Windows+B` e as setas. `Enter` no ícone mostra a janela de novo; o menu de contexto (`Shift+F10` ou a tecla de aplicativos) tem **Mostrar KeyTune**, **Reproduzir ou pausar**, **Faixa anterior**, **Próxima faixa**, **Parar**, **Anunciar status** e **Sair do KeyTune**. Ao voltar, o foco fica onde estava.

Em **Preferências > Geral > Bandeja do sistema**, **Ao minimizar, ocultar na bandeja do sistema** faz o mesmo ao minimizar, e **Ao fechar, ocultar na bandeja do sistema** faz fechar a janela só escondê-la. Com essa opção ligada, para sair use **Arquivo > Sair** ou **Sair do KeyTune** no menu do ícone.

## Configurações

As preferências abrem com `Ctrl+,` e se dividem em oito abas: **Geral**, **Reprodução**, **Acessibilidade**, **Biblioteca**, **Download**, **KeyTube**, **Rádios online** e **Recursos adicionais**.

### Geral

**Restaurar sessão ao iniciar**, **Lembrar tamanho da janela**, **Lembrar última pasta usada** e **Confirmar ao sair** fazem o que o nome diz. **Usar o player rápido ao abrir arquivos pelo Windows** vem marcado e decide se um arquivo de áudio aberto pelo Explorador de Arquivos toca na janela pequena ou na janela principal (veja [Ouvir um arquivo direto do Explorador de Arquivos do Windows](#ouvir-um-arquivo-direto-do-explorador-de-arquivos-do-windows)).

A seção **Bandeja do sistema** tem **Ao minimizar, ocultar na bandeja do sistema** e **Ao fechar, ocultar na bandeja do sistema**; veja [Bandeja do sistema](#bandeja-do-sistema).

A seção **Associação de arquivos** (Windows) tem o botão **Registrar como player padrão**, que põe o KeyTune no menu *Abrir com* para formatos de áudio, vídeo e playlists. Depois de registrar, defina o app como padrão nas configurações do Windows, se quiser que esses arquivos abram direto nele. **Desregistrar associações** desfaz o registro.

A seção **Registro de logs** ajuda a investigar problemas. **Registrar logs de diagnóstico** grava um arquivo de log, em inglês, na pasta de dados, útil para anexar a um relato de bug. **Nível de detalhe** vai de *Apenas erros*, o mais silencioso, a *Depuração*, que gera arquivos grandes. **Abrir pasta de logs** leva até eles.

### Reprodução

- **Crossfade (segundos)**: a sobreposição de áudio entre faixas na troca automática (0 a 12 s). Use 0 para desligar. Só vale entre arquivos de áudio.
- **Aplicar crossfade ao trocar de faixa manualmente**: com a opção ligada, o crossfade vale também ao avançar ou voltar com os controles; por padrão, só no fim natural da faixa. Quando há uma transição do AutoDJ pronta, avançar usa esse plano mesmo com a opção desligada.
- **Dispositivo de áudio**: a saída de som. *Padrão do sistema* segue o dispositivo principal do Windows.
- **Desativar saída de vídeo (tocar só o áudio)**: toca só o áudio, inclusive de arquivos de vídeo. Evita janelas externas de vídeo.
- **Mostrar o vídeo das transmissões ao vivo**: mostra a imagem das transmissões do YouTube na área do player mesmo com a saída de vídeo desativada para o resto do app. Desmarcado, a transmissão toca só o áudio. `Ctrl+Alt+V` alterna durante uma transmissão.

O **volume padrão**, os passos de **volume** e de **busca** (o quanto cada seta muda), a **repetição padrão** e o **embaralhamento** das playlists novas completam a aba e também fazem o que o nome diz.

Com o AutoDJ instalado, há duas opções a mais: **Perfil do AutoDJ** (*Suave* faz uma mistura longa e equilibrada; *Festa* concentra a troca de graves no centro e eleva a energia aos poucos; *Eletrônica* usa cortes mais fortes e uma troca mais rápida, pensada para batidas marcadas) e **Duração da transição do AutoDJ** (8, 16 ou 32 batidas, independente do crossfade comum).

### Acessibilidade

Tem uma opção só: **Ativar anúncios de acessibilidade**. Ligada, o player anuncia ao leitor de tela mudanças de tempo, volume, troca de abas e status. Desligada, esses anúncios param. Os atalhos de anúncio sob demanda (`T`, `V` e `S`) funcionam em qualquer caso. Veja [Acessibilidade](#recursos-de-acessibilidade).

### Biblioteca

Controla a [biblioteca inteligente](#biblioteca-inteligente). Desligar **Ativar a biblioteca inteligente** desativa o recurso inteiro e desabilita as outras opções.

- **Indexar automaticamente as pastas abertas no navegador**: ao abrir uma pasta, as mídias dela entram no índice em segundo plano.
- **Guardar um histórico local de reprodução** e **Reproduções guardadas no histórico** (50 a 20000): passando do limite, as mais antigas saem.
- **Lembrar a posição de mídias longas**, **Duração mínima para lembrar a posição** (1 a 240 minutos) e **Margem ignorada no início e no fim** (5 a 300 segundos): veja [Retomar de onde parou](#retomar-de-onde-parou).
- **Entradas guardadas no cache** (100 a 100000): quantos metadados e análises de áudio ficam guardados.

### Download

Define os padrões do `Ctrl+Shift+B`:

- **Tipo de download padrão**: **Áudio** ou **Vídeo**.
- **Qualidade do áudio**: **Original (sem conversão)** mantém o áudio como o YouTube entrega; **MP3** (128, 192, 256 ou 320 kbps) e **FLAC (sem perdas)** convertem o áudio e exigem o FFmpeg.
- **Taxa de amostragem do áudio**: **Original**, 44100 Hz ou 48000 Hz. Só vale quando o áudio é convertido. O YouTube entrega 44,1 ou 48 kHz, então taxas maiores não trariam ganho de qualidade.
- **Qualidade do vídeo**: **Melhor disponível** ou uma altura máxima de 2160p a 144p. Se a altura escolhida não existir, o vídeo é baixado na melhor qualidade disponível.
- **Pasta de download**: onde os arquivos são salvos. O padrão é **Downloads\KeyTune**, na pasta do seu usuário.
- **Sempre mostrar o diálogo ao baixar**: ligado (o padrão), cada download abre o diálogo de confirmação; desligado, o download começa direto com as opções desta aba.

### KeyTube

Reúne as opções do YouTube e do YouTube Music. Elas só têm efeito com a integração ativada em **Recursos adicionais**.

**Biblioteca**

- **Itens carregados por vez**: quantos itens cada lista da aba traz a cada carregamento (5 a 200). Vale para as playlists da biblioteca, os resultados de busca, as faixas de uma playlist e os comentários. Valores menores abrem mais rápido; ao chegar ao fim da lista, o player carrega mais.
- **Mixes personalizadas para descobrir**: o máximo de itens varridos no início do YouTube Music para achar mixes personalizadas (5 a 200). Valores menores deixam a sincronização mais rápida.

**Reprodução**

- **Tocar faixas relacionadas ao fim da playlist**: quando a última faixa do YouTube Music acaba, ou quando você pede a próxima estando na última, o player busca faixas relacionadas (a rádio do YouTube Music) e segue tocando, sem pausa entre uma e outra. A tecla `A` liga e desliga durante a reprodução. Faixas que já estão na playlist não entram de novo.
- **Salvar o que ouvi no histórico do YouTube Music**: ligada por padrão. Ao ouvir uma faixa por tempo suficiente (cerca de 30% da duração, entre 15 e 30 segundos), o player a marca como assistida no histórico da sua conta. Desligue para tocar sem registrar nada.

**Idioma e região**

- **Idioma do conteúdo**: o idioma pedido ao YouTube nas buscas e nos textos que ele devolve (contagens, datas). O padrão é **O mesmo do KeyTune**. Vale para as buscas do YouTube com o YouTube.js ativado; as buscas do YouTube Music usam só a região.
- **Região do conteúdo**: o país usado nas buscas do YouTube e do YouTube Music. Em **Automática**, o YouTube decide pela sua conexão.
- **Áudio dos vídeos dublados**: alguns vídeos trazem o áudio original e dublagens. Aqui você escolhe o que toca: **A que o YouTube entregar** (o padrão), **Original do vídeo** ou a dublagem num idioma. Vídeos sem a faixa pedida tocam normalmente. Uma faixa que não é a padrão passa pelo yt-dlp e leva alguns segundos a mais para começar.

### Rádios online

- **Meu país**: o país que abre o início da aba **Rádios online** e que aparece como opção de busca. Em **Automático (seguir o sistema)**, vale o país configurado no Windows. Um país que não está na lista pode ser definido na própria aba, no menu de ações do país.

### Recursos adicionais

Reúne as integrações e as bibliotecas opcionais do YouTube e do AutoDJ. Antes do primeiro download, o KeyTune mostra um diálogo com todos os componentes que serão instalados.

**Componentes do YouTube**

- **Ativar a integração com YouTube e YouTube Music**: baixa e mantém o executável `yt-dlp`, os pacotes Python necessários e, se não houver um compatível, um Node.js portátil para o resolvedor EJS. Sem isso, o KeyTube não funciona. Na primeira vez o download pode levar alguns minutos e exige internet. Ao desativar, os arquivos já baixados ficam no lugar.
- **Atualizar os componentes automaticamente**: verifica e aplica atualizações no intervalo definido abaixo. Só fica disponível com a integração ativada.
- **Usar versão nightly do yt-dlp (recomendado)**: baixa as builds nightly do `yt-dlp`. O YouTube muda seus mecanismos de extração com frequência, e a nightly costuma receber as correções antes do canal estável.
- **Usar YouTube.js (recomendado)**: melhora a resolução e a reprodução. Instala o YouTube.js e usa o mesmo Node.js 24 ou superior preparado para o `yt-dlp`, que continua como alternativa. O pacote entra na verificação periódica de atualizações.
- **Intervalo de atualização (horas)**: de quanto em quanto tempo o player tenta atualizar as dependências quando o KeyTube é aberto (1 a 720 h). Só fica disponível com a atualização automática ligada.

**AutoDJ**

- **Baixar recursos e ativar AutoDJ**: baixa à parte `librosa`, NumPy, SciPy, Numba e PyAV, que não vêm no instalador. Ao desativar, os arquivos baixados ficam no lugar.
- **Tocar efeitos de DJ**, **Perfil do AutoDJ** e **Duração da transição** ficam disponíveis com o AutoDJ ativado.

## Recursos de acessibilidade

O KeyTune foi pensado para leitores de tela e para uso só pelo teclado:

- o foco evita saltos desnecessários para a área nativa de vídeo;
- estados e navegação são anunciados quando o suporte de acessibilidade está disponível;
- campos, botões, listas e grupos têm nomes e descrições legíveis por leitores de tela.

Se você usa leitor de tela, `T`, `V` e `S` (veja [Atalhos de reprodução](#atalhos-de-reproducao)) e a ajuda rápida `F1` ajudam a se localizar sem depender dos anúncios automáticos. Esses anúncios, como troca de faixa, mudança de aba e mudança de volume, podem ser ligados ou desligados em `Ctrl+,` > **Acessibilidade**.

Favoritos e avaliações são falados junto com o item, e detalhes, comentários e permissões de plugins aparecem em campos de leitura com rótulo. O leitor de tela também anuncia o nome do grupo quando o foco entra nele.

## Atualizações

Ao iniciar, o KeyTune pode verificar atualizações sozinho. Para verificar a qualquer hora, use **Ajuda > Verificar atualizações**.

Quando há versão nova, o aplicativo mostra as notas da release, o nome do arquivo e o tamanho do download antes de pedir confirmação. Se você aceitar, ele baixa o pacote, mostra o andamento e pede permissão para instalar quando o arquivo estiver pronto. As notas vêm no idioma da interface.

Para ler o que mudou em cada versão, inclusive nas anteriores, use **Ajuda > Histórico de mudanças**: escolha a versão na lista e leia o texto logo abaixo.

## Solução de problemas

**Comece pelo diagnóstico.** **Ajuda > Diagnóstico** testa o que o KeyTune precisa para tocar: a biblioteca do MPV e as dependências dela no Windows, o início do player, os dispositivos de áudio, o `yt-dlp`, o Node.js, o YouTube.js, o FFmpeg, a conta do YouTube e, resolvendo um vídeo público de verdade, se o YouTube responde ao YouTube.js e ao `yt-dlp`. O relatório abre numa caixa de leitura, com os problemas primeiro e, em cada um, o que fazer. **Copiar relatório** leva o texto para a área de transferência, para anexar a um relato de bug. O diagnóstico só lê e testa; ele não instala nem altera nada.

Se o player não conseguir iniciar ao abrir o KeyTune, o mesmo diagnóstico roda sozinho, mostra o motivo e o aplicativo fecha em seguida.

**O aplicativo não abre direito.** Veja se a instalação terminou sem erros (reinstalar com o instalador mais recente resolve a maioria dos casos) e se o sistema tem permissão para acessar os arquivos ou pastas que você tentou abrir.

**O player não acha o runtime do MPV.** Confira se ele está num destes lugares: uma pasta `mpv/` ao lado do executável, `MPV_HOME`, `MPV_DLL_DIR`, o cache salvo da execução anterior ou uma instalação compatível do Chocolatey.

**A associação de arquivos não funciona como esperado.** São dois passos separados. Primeiro, o KeyTune precisa estar registrado como opção (na instalação, ou depois em **Configurações > Preferências > Geral > Registrar como player padrão**). Segundo, ele precisa estar escolhido como aplicativo padrão para esses formatos nas configurações de apps padrão do Windows. Só registrar não o torna o padrão.

**O KeyTube não carrega ou mostra erros de dependência.** Abra `Ctrl+,` > **Recursos adicionais** e confirme que **Ativar a integração com YouTube e YouTube Music** está marcada. O download inicial pode levar alguns minutos e exige internet. Se as dependências já estão instaladas mas a busca ou o carregamento falham, use a versão nightly do `yt-dlp`, nas mesmas preferências: ela costuma receber correções antes do canal estável.

**Uma conversão falhou.** Confirme que o arquivo abre normalmente no player e que a pasta de destino aceita gravação. A mensagem do FFmpeg é mostrada e anunciada; arquivos corrompidos ou em formatos incomuns podem não ser convertidos.

**Um download ou uma transmissão ao vivo não funciona.** Confirme que os **Recursos adicionais** estão ativados e atualizados (o `yt-dlp` muda com frequência para acompanhar o YouTube). Num download, confirme também que a pasta existe e aceita gravação. O erro 429 indica um bloqueio temporário do YouTube por excesso de pedidos: espere alguns minutos e tente de novo.

**Uma rádio online não toca ou a lista não abre.** O diretório do Radio Browser e as próprias estações às vezes ficam fora do ar. Tente outra rádio da lista, ou volte à lista e abra-a de novo.

**A conta do YouTube aparece desconectada, ou o player pede para conectar de novo.** O navegador trocou os cookies que o KeyTune tinha guardado; veja [Por que a conexão cai](#por-que-a-conexao-cai-a-troca-de-cookies). Exporte um `cookies.txt` novo de uma janela anônima, como em [Conectar com um cookies.txt](#conectar-com-um-cookies-txt-recomendado), e conecte de novo. Se a biblioteca vier vazia ou de outra pessoa, a sessão tem mais de uma conta Google: conecte de novo e escolha a conta certa.

**Outros problemas.** Ative o registro de logs em `Ctrl+,` > **Geral** > **Registro de logs**. Com **Registrar logs de diagnóstico** ligado e o nível em *Depuração*, o player grava informações detalhadas em `keytune.log`, na pasta de dados. **Abrir pasta de logs** leva até o arquivo. Se for relatar o problema, anexe o log à issue.

## Plugins e marketplace

Abra **Configurações > Gerenciar plugins** para instalar um arquivo `.ktplugin` ou escolher **Abrir marketplace**. Selecione um plugin, confira autor, versão, origem, permissões e isolamento e confirme com **Instalar e ativar**. O gerenciador também ativa, desativa e desinstala plugins.

As ações que os plugins adicionam ficam em **Configurações > Ações de plugins**. Plugins também podem oferecer abas e telas. Instale só código de autores em quem você confia: rodar em processo separado não é uma sandbox de segurança. O selo de verificação indica revisão de procedência, não garantia de segurança.

O [guia de desenvolvimento e API 2.0](plugins.md) traz manifesto, permissões, métodos, eventos e publicação. Ele acompanha o player e pode ser lido offline; links externos exigem internet.

## Para desenvolvedores

O KeyTune é um projeto de código aberto. O repositório, as issues, os pull requests e as releases estão em [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). O fonte deste manual está em [docs/manual.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md).

Para rodar o projeto a partir do código, instale as dependências com `uv sync` e abra o player com `uv run keytune`. As regras de escrita de manual, changelog e commits estão em `.github/instructions/writing.instructions.md`.
