# Manual do KeyTune

O KeyTune é um player de mídia feito para uso por teclado e com foco em acessibilidade. Ele foi pensado para funcionar bem com playlists, navegação por pastas e para manter o que você estava fazendo entre uma abertura e outra.

Este projeto foi desenvolvido com assistência de IA, incluindo GitHub Copilot, Codex da OpenAI e Claude Code da Anthropic.

Este manual apresenta os recursos principais do aplicativo e as ações mais comuns para começar a usar o player com rapidez.

## O que o KeyTune oferece

- Reprodução de mídia com controle por teclado
- Playlists em abas
- Fila de reprodução independente para organizar o que toca em seguida
- Busca dentro da playlist ou pasta atual, com navegação entre os resultados por teclado
- Temporizador com durações prontas ou pausa ao fim da faixa
- Navegação por pastas com pré-visualização
- Equalizador por aba com predefinições e presets personalizados
- Painel de letras com busca automática e cópia do texto
- Aba dedicada do YouTube Music, aberta com `Ctrl+Shift+Y`
- Carregamento e gravação de playlists
- Restauração do que estava aberto na última sessão
- Lista de arquivos, pastas e playlists recentes
- Anúncios de acessibilidade quando leitores de tela estão disponíveis

## Primeiros passos

1. Baixe o instalador `KeyTune-Setup.exe` mais recente na página de [releases](https://github.com/ed-fe/KeyTune/releases).
2. Execute o instalador e siga as etapas. Na página de tarefas adicionais você pode marcar a criação de um atalho na área de trabalho e escolher quais formatos de áudio, vídeo e playlist deseja associar ao KeyTune — tudo opcional e desmarcado por padrão. Associar um formato registra o KeyTune como opção no menu *Abrir com*; para que ele abra automaticamente esses arquivos, ainda é preciso confirmar como padrão nas configurações do Windows.
3. Ao final, o instalador oferece iniciar o KeyTune e abrir este manual.
4. Em execuções futuras, quando houver uma atualização disponível, o próprio aplicativo mostra um diálogo com as novidades e pede confirmação antes de baixar e instalar (veja [Atualizações](#atualizacoes)).

O KeyTune depende do runtime do MPV para reproduzir mídia. O instalador já inclui esse runtime; se o player abrir mas não reproduzir nada, veja a seção [Solução de problemas](#solucao-de-problemas).

## Interface

Ao abrir o KeyTune pela primeira vez, a janela principal mostra uma única aba de playlist vazia, sem nada para reproduzir ainda. A janela é dividida em quatro áreas:

- **Barra de menus**, no topo: **Arquivo** (abrir mídia/pasta/playlist, recentes, salvar), **Reprodução** (play/pause, faixa anterior/próxima, embaralhar, repetição, dispositivo de áudio, anúncios), **Exibir** (alternar foco, equalizador, YouTube Music), **Abas** (nova aba, navegação entre abas, fechar), **Configurações** (preferências) e **Ajuda** (manual, atalhos, verificar atualizações).
- **Área de abas**, ocupando a maior parte da janela: cada aba representa uma playlist ou uma pasta aberta (veja [Playlist, pastas e abas](#playlist-pastas-e-abas)). Dentro de cada aba, o espaço é dividido em duas partes lado a lado:
    - à **esquerda**, o navegador de itens — a lista da playlist ou o conteúdo da pasta atual;
    - à **direita**, a área do player. Quando a mídia atual é um vídeo, essa área mostra o quadro de vídeo; para áudio, ou quando nada está carregado,  ela mostra um texto de apoio com os atalhos mais usados para começar.
- **Painel de tempo**, abaixo da área de abas: mostra o tempo decorrido e a duração da mídia atual, uma barra de progresso visual e um resumo dos atalhos principais.
- **Barra de status**, na borda inferior da janela: exibe mensagens curtas e temporárias sobre a última ação realizada (por exemplo, ao abrir um arquivo ou salvar uma playlist).

Use `Tab` ou `Ctrl+B` para mover o foco entre o navegador de itens e o player dentro da aba ativa, e `F1` em qualquer momento para abrir a ajuda rápida de atalhos.

## Como abrir mídia

Você pode abrir arquivos de mídia, uma playlist local, uma pasta ou um caminho e link compatível usando os atalhos ou o menu **Arquivo**:

- `Ctrl+Alt+O` — diálogo unificado que aceita qualquer tipo: arquivo, pasta, playlist, link ou ID do YouTube Music.
- `Ctrl+O` — abre arquivos de mídia ou uma playlist `.m3u`/`.m3u8`.
- `Ctrl+Shift+O` — abre uma pasta diretamente no navegador de pastas.
- `Ctrl+V` — cola um caminho ou link da área de transferência na playlist atual.
- `Ctrl+Shift+V` — cola e abre em uma nova playlist.

Formatos de mídia suportados diretamente:

- Áudio: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg`, `.oga`, `.m4a`, `.opus`, `.wma`, `.aiff`, `.aif`, `.ac3`, `.mka`, `.wv`, `.ape`.
- Vídeo: `.mp4`, `.m4v`, `.mkv`, `.avi`, `.mov`, `.webm`, `.flv`, `.wmv`, `.mpg`, `.mpeg`, `.3gp`, `.ts`, `.m2ts`, `.mts`, `.ogv`.

O menu **Arquivo > Recentes** guarda separadamente os últimos **Arquivos recentes**, **Pastas recentes** e **Playlists recentes**, facilitando reabrir o que você usou antes sem precisar navegar de novo.

## Playlist, pastas e abas

Cada playlist fica em uma aba separada. Isso ajuda a separar contextos, como uma lista de músicas para ouvir agora, uma pasta com arquivos locais ou uma coleção que você quer deixar organizada.

A aba ativa define o que está sendo reproduzido e o que aparece no navegador lateral. Você pode manter uma aba para uma playlist salva, outra para uma pasta inteira e outras para listas temporárias, sem misturar tudo no mesmo contexto. As abas podem ser abertas, alternadas e fechadas sem afetar as outras.

### Atalhos de abas e itens

Os atalhos para abrir mídia, pastas, playlists e links estão na seção [Como abrir mídia](#como-abrir-midia), acima. Os atalhos abaixo são específicos de abas e da playlist atual:

- `Ctrl+T`: abrir uma nova aba de playlist
- `Ctrl+W`: fechar a aba ou playlist atual
- `Ctrl+Shift+W`: fechar a mídia atual
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: navegar para a próxima ou aba anterior
- `Ctrl+Shift+E`: abrir o equalizador da aba ativa
- `Ctrl+C`: copiar o caminho ou link do item selecionado
- `Ctrl+Shift+S`: salvar a playlist atual
- `Ctrl+B`: alternar foco entre o navegador de itens e o player
- `Ctrl+F`: localizar um item na playlist ou pasta atual
- `F3` / `Shift+F3`: próximo ou anterior resultado da busca

### Fila de reprodução

A fila de reprodução organiza o que deve tocar depois da faixa atual, sem depender da ordem da playlist que você está navegando. Ela sempre pertence à playlist que está tocando no momento.

Use `Ctrl+Shift+F` ou o menu **Reprodução > Adicionar à Fila de Reprodução** para adicionar ou remover itens da fila. Para ver, remover, reordenar ou limpar a fila inteira, use `Ctrl+Shift+Q` ou o menu **Reprodução > Gerenciar Fila de Reprodução**.

Se a fila estiver vazia, o gerenciador informa isso e pede para adicionar itens primeiro.

### Temporizador

O temporizador pausa a reprodução sozinho depois de um tempo combinado — útil para ouvir algo antes de dormir sem deixar o player tocando a noite toda. Ele **pausa** em vez de parar, então a posição da mídia é preservada e basta `Espaço` para continuar de onde parou.

Use `Ctrl+Shift+D` ou o menu **Reprodução > Temporizador** para configurá-lo. As opções são:

- **Durações prontas**: 5, 10, 15, 30, 45, 60, 90 ou 120 minutos, disponíveis direto no submenu.
- **Tempo personalizado**: qualquer valor de 1 a 720 minutos, na caixa de configuração.
- **Ao fim da faixa atual**: a reprodução termina quando a faixa acabar, sem avançar para a próxima, sem repetir e sem puxar conteúdo relacionado.
- **Não usar temporizador**: cancela o agendamento.

O submenu ainda traz **Tempo restante**, que anuncia quanto falta, e **Cancelar temporizador**, ativo apenas quando há um temporizador agendado.

Enquanto a contagem corre, o player avisa quando faltam 5 minutos e quando falta 1 minuto. O estado do temporizador também entra no anúncio de status da tecla `S`.

### Atalhos de reprodução

- `Espaço`: reproduzir ou pausar
- `Seta esquerda` / `Seta direita`: voltar ou avançar na mídia atual
- `Shift+Seta esquerda` / `Shift+Seta direita`: voltar ou avançar 1 minuto na mídia atual
- `Home` / `End`: ir para o início ou para o fim da mídia
- `Seta cima` / `Seta baixo`: aumentar ou diminuir o volume
- `Ctrl+.`: parar a reprodução
- `Ctrl+PageUp` / `Ctrl+PageDown`: faixa anterior ou próxima na playlist
- `Alt+Seta esquerda` / `Alt+Seta direita`: faixa anterior ou próxima na playlist (alternativa a `Ctrl+PageUp`/`Ctrl+PageDown`)
- `Alt+Seta cima` / `Alt+Seta baixo`: mover o item atual para cima ou para baixo na playlist
- `Alt+Home` / `Alt+End`: ir para o primeiro ou para o último item da playlist
- `E`: alternar modo aleatório
- `R`: alternar modo de repetição
- `A`: alternar a reprodução de conteúdo relacionado do YouTube Music (rádio automática ao fim da playlist)
- `]` / `[`: aumentar ou diminuir a velocidade de reprodução
- `Shift+]` / `Shift+[`: aumentar ou diminuir o tom da reprodução em semitons
- `Shift+\`: restaurar o tom original
- `Ctrl+Alt+L`: alternar o painel de letras
- `Ctrl+Shift+F`: adicionar o item selecionado à fila de reprodução
- `Ctrl+Shift+Q`: gerenciar a fila de reprodução
- `Ctrl+Shift+D`: configurar o temporizador
- `T`: anunciar o tempo atual da mídia
- `V`: anunciar o volume atual
- `S`: anunciar o status do player
- `Ctrl+L`: curtir a mídia atual no YouTube Music
- `Ctrl+Shift+L`: marcar a mídia atual como não gostei no YouTube Music (e pular para a próxima faixa)

O atalho `Ctrl+W` fecha a aba ativa diretamente; o atalho `Ctrl+Shift+W` fecha ou descarrega a mídia atual na aba ativa.

### Navegador de itens

O navegador fica à esquerda da janela e opera em dois modos distintos dependendo do que está na aba ativa: **modo playlist** e **modo pasta**. Use `Tab` ou `Ctrl+B` para alternar o foco entre o navegador e o player.

#### Modo playlist

Quando a aba contém uma playlist, o navegador mostra todos os itens da sequência. O item em reprodução fica marcado com `▶` no início da linha. Os atalhos disponíveis são:

- `Enter`: toca o item selecionado imediatamente.
- `Delete`: remove o item selecionado da playlist.
- `Shift+F10`: abre o menu contextual com ações adicionais sobre o item ou sobre toda a seleção (a lista aceita seleção múltipla). Além de copiar, colar e remover, o menu traz as ações do YouTube Music quando a seleção contém faixas dessa origem: **Curtir**/**Não gostei**, **Adicionar à playlist do YouTube Music...** e, quando a aba atual é uma playlist sua do YouTube Music, **Remover da playlist do YouTube Music**. Veja [Gerenciar playlists do YouTube Music](#gerenciar-playlists-do-youtube-music).
- `Tab` / `Esc`: volta o foco para o player.

#### Modo pasta

Quando a aba veio de uma pasta aberta com `Ctrl+Shift+O`, o navegador exibe o conteúdo do diretório atual: subpastas e arquivos de mídia. Conforme a reprodução avança, o item correspondente à mídia atual fica em destaque automaticamente. Ao mover a seleção para um arquivo de mídia, o player já inicia a reprodução desse arquivo. Os atalhos disponíveis são:

- `Enter`: entra na subpasta selecionada ou toca o arquivo de mídia.
- `Backspace`: volta para a pasta superior (equivale a selecionar `..`).
- `Shift+F10`: abre o menu contextual.
- `Tab` / `Esc`: volta o foco para o player.

#### Localização rápida por digitação

Nos dois modos, digitar letras ou números move a seleção para o primeiro item cujo nome começa com os caracteres digitados. A busca ignora acentos e diferenças entre maiúsculas e minúsculas. Após um segundo sem digitar, o acumulador de caracteres é resetado e a próxima letra inicia uma nova busca.

#### Busca na playlist ou pasta atual

Para procurar em listas grandes, use a busca completa em vez da digitação rápida. Ela encontra o texto em **qualquer parte** do nome do item, não apenas no início.

- `Ctrl+F`: abre a caixa **Localizar item**. Digite o texto e confirme com `Enter` ou com o botão **Localizar**.
- `F3`: vai para o próximo resultado.
- `Shift+F3`: volta para o resultado anterior.

Também é possível abrir a busca pelo menu **Exibir > Localizar item**, que traz igualmente **Próximo resultado** e **Resultado anterior**.

Detalhes úteis:

- A busca ignora acentos e diferenças entre maiúsculas e minúsculas, do mesmo jeito que a digitação rápida.
- Ela percorre os itens exibidos na aba ativa, então funciona tanto em playlists locais quanto em pastas e em listas vindas do YouTube Music.
- A primeira busca considera o item já selecionado; a partir daí, `F3` e `Shift+F3` avançam ou voltam.
- O leitor de tela lê o nome do item encontrado. A posição na busca aparece na barra de status, como em “Busca “rock”: resultado 2 de 7.”, junto com um aviso quando a busca dá a volta na lista.
- O texto procurado fica guardado durante a sessão: `F3` repete a última busca sem reabrir a caixa. Se ainda não houver um texto, `F3` abre a caixa de busca.
- Se nada corresponder, a seleção atual é mantida e o player informa que não há itens correspondentes.

Para tarefas de organização, vale pensar nas abas como espaços de trabalho independentes: uma aba para tocar algo agora, outra para revisar a biblioteca e outra para testes ou coleções temporárias.

## Configurações

As preferências ficam em `Ctrl+,` e são divididas em quatro abas: **Geral**, **Reprodução**, **Acessibilidade** e **Recursos adicionais**.

### Geral

A aba **Geral** reúne as opções que controlam como o KeyTune volta a funcionar na próxima abertura:

- **Restaurar sessão ao iniciar**: reabre as abas e tenta retomar o estado da execução anterior.
- **Lembrar tamanho da janela**: salva e restaura o tamanho da janela principal entre execuções.
- **Lembrar última pasta usada**: usa a última pasta aberta como diretório inicial nos diálogos de abrir e salvar.
- **Confirmar ao sair**: pede confirmação antes de fechar o player.

Nessa mesma aba fica a seção **Associação de arquivos** (Windows). O botão **Registrar como player padrão** adiciona o KeyTune ao menu *Abrir com* para formatos de áudio, vídeo e playlists. Depois de registrar, defina o app como padrão nas configurações do Windows se quiser que esses arquivos abram diretamente no KeyTune. O botão **Desregistrar associações** desfaz esse registro.

A aba **Geral** também inclui a seção **Registro de logs**:

- **Registrar logs de diagnóstico**: quando ligado, o player grava um arquivo de log rotativo em disco. Útil para depurar problemas e anexar ao relato de bugs. Os logs são gravados em inglês.
- **Nível de detalhe**: controla quanta informação é registrada. *Apenas erros* é o mais silencioso; *Depuração* é o mais detalhado e pode gerar arquivos grandes. Só fica disponível quando o registro está ativado.
- **Abrir pasta de logs**: abre no explorador de arquivos a pasta onde os arquivos de log são salvos.

Os logs são rotacionados automaticamente a cada 2 MB e até 3 arquivos anteriores são mantidos. Os arquivos de sessões anteriores ficam em `keytune.log.1`, `.2` e `.3` na mesma pasta.

### Reprodução

A aba **Reprodução** controla o comportamento de áudio e o estado inicial de novas playlists:

- **Volume padrão**: volume ao iniciar o player (0–100).
- **Passo de volume**: quanto cada pressão de `Seta cima`/`Seta baixo` aumenta ou diminui o volume (1–25).
- **Crossfade (segundos)**: sobreposição de áudio entre faixas na transição automática (0–12 s). Use 0 para desativar. O crossfade só é aplicado entre arquivos de áudio.
- **Passo de busca (segundos)**: quanto cada pressão de `Seta esquerda`/`Seta direita` avança ou retrocede na mídia (1–120 s).
- **Repetição padrão**: modo de repetição aplicado automaticamente a playlists novas. As opções são *Repetição desligada*, *Repetir faixa atual* e *Repetir playlist*.
- **Dispositivo de áudio**: saída de som usada na reprodução. *Padrão do sistema* segue o dispositivo principal do Windows.
- **Ativar embaralhamento em novas playlists**: ativa o modo aleatório automaticamente em playlists criadas depois de salvar.
- **Aplicar crossfade ao trocar de faixa manualmente**: quando ligado, o crossfade também é usado ao avançar ou voltar manualmente; por padrão só vale no fim natural de cada faixa.
- **Desativar saída de vídeo (tocar só o áudio)**: mantém a reprodução apenas em áudio, inclusive em arquivos de vídeo. Útil para evitar janelas externas de vídeo.

### Acessibilidade

A aba **Acessibilidade** tem uma única opção: **Ativar anúncios de acessibilidade**. Quando ligada, o player anuncia mudanças de tempo, volume, troca de abas e status ao leitor de tela. Quando desligada, esses anúncios são suprimidos. Os atalhos de anúncio sob demanda (`T`, `V`, `S`) continuam funcionando independentemente dessa configuração — veja [Recursos de acessibilidade](#recursos-de-acessibilidade) para detalhes.

### Recursos adicionais

A aba **Recursos adicionais** concentra as integrações opcionais. Hoje ela reúne os controles do YouTube Music e do YouTube em duas seções.

#### Integração com YouTube Music e YouTube

- **Ativar recursos adicionais para YouTube Music e YouTube (yt-dlp e ytmusicapi)**: baixa e mantém um executável `yt-dlp` e os pacotes Python necessários em uma pasta local. Sem isso, a aba do YouTube Music não funciona. Na primeira execução, o download pode levar alguns minutos e exige internet. Ao desativar, os arquivos já baixados não são removidos.
- **Atualizar automaticamente as dependências do YouTube Music**: verifica e aplica atualizações no intervalo definido abaixo. Só aparece quando a opção acima está ativada.
- **Usar versão nightly do yt-dlp (recomendado)**: baixa builds nightly do `yt-dlp`. Recomendado porque o YouTube e o YouTube Music mudam os mecanismos de extração com frequência e a nightly costuma receber correções antes do canal estável. Só aparece quando a integração está ativada.
- **Intervalo de atualização (horas)**: de quanto em quanto tempo o player tenta atualizar as dependências quando a aba YouTube Music é aberta (1–720 h). Só fica disponível quando a atualização automática está ativada.

#### Biblioteca do YouTube Music

Essa seção só aparece quando a integração está ativada.

- **Playlists carregadas por vez**: quantas playlists da biblioteca são trazidas em cada carregamento (5–200). Valores menores aceleram a abertura; ao chegar ao final da lista o player oferece carregar mais.
- **Mixes personalizadas para descobrir**: limite máximo de itens varridos na página inicial do YouTube Music para encontrar mixes personalizadas (5–200). Valores menores deixam a sincronização mais rápida.
- **Reproduzir conteúdo relacionado ao fim da playlist (rádio automática)**: quando a última faixa do YouTube Music termina naturalmente — ou quando você pede a próxima faixa estando na última —, o player busca faixas relacionadas (a rádio do YouTube Music) e continua tocando automaticamente. Para uma transição contínua, a busca começa pouco antes do fim da última faixa e o link da próxima já é resolvido com antecedência, evitando pausa enquanto o conteúdo é descoberto. Também pode ser ligado ou desligado com a tecla `A` durante a reprodução. Faixas que já estão na playlist não são adicionadas de novo, e quando a rádio devolve só repetidas o player busca a partir de uma faixa anterior antes de encerrar.
- **Salvar músicas escutadas no histórico do YouTube Music**: ligada por padrão. Ao escutar uma faixa do YouTube Music por tempo suficiente (cerca de 30% da duração, entre 15 e 30 segundos), o player marca essa faixa como assistida no histórico da sua conta do YouTube Music. Desative para tocar faixas do YouTube Music sem registrar nada no histórico.

## Equalizador

O equalizador é aberto por aba com `Ctrl+Shift+E`, então cada playlist pode ter um ajuste próprio.

Na prática, isso permite deixar uma playlist com graves reforçados e outra com um ajuste mais neutro sem precisar refazer tudo toda vez que trocar de contexto.

### Como usar

Ao abrir o equalizador, o campo **Aba alvo** mostra qual playlist receberá os ajustes. Use a caixa **Ativar equalizador nesta aba** para ligar ou desligar o efeito só naquela aba.

O campo **Preset** lista todos os presets disponíveis. Os embutidos aparecem com o sufixo *(embutido)*. Ao selecionar um, o campo **Descrição** mostra uma nota sobre o perfil sonoro e a seção **Resumo do preset** exibe os valores de pré-amplificação e de cada banda para conferir antes de aplicar.

#### Botões de gerenciamento de presets

- **Novo...**: cria um preset personalizado do zero. Abre o editor para você definir o nome, a pré-amplificação e o ganho de cada banda. Use este botão quando quiser uma curva que não existe entre os presets embutidos.
- **Editar...**: edita um preset personalizado já existente. Este botão só aparece assim quando o preset selecionado é personalizado.
- **Salvar cópia...**: quando o preset selecionado é embutido, o botão muda de nome para **Salvar cópia...** e cria uma versão editável baseada nele. Use este caminho para partir de um preset embutido e ajustá-lo.
- **Duplicar...**: cria uma cópia de um preset personalizado com um novo nome, mantendo o original intocado. Não disponível para presets embutidos.
- **Excluir**: remove o preset personalizado selecionado permanentemente. Não disponível para presets embutidos.
- **Aplicar em todas as abas**: copia o preset e o estado de ativação da aba atual para todas as abas de mídia abertas.

#### Editor de preset

O editor mostra o campo de nome, o controle de pré-amplificação e um controle por banda de frequência. Cada banda aceita valores de -12,0 dB a +12,0 dB. Valores positivos reforçam a frequência; valores negativos atenuam. A pré-amplificação ajusta o ganho geral antes de todas as bandas.

### Presets embutidos

O KeyTune inclui 18 presets prontos para uso:

| Preset | Perfil |
|---|---|
| Padrão | Curva neutra, mantém o som original |
| Clássico | Realça definição e brilho sem exagerar nos graves |
| Club | Graves e agudos mais animados |
| Dance | Mais impacto no grave e brilho no topo |
| Graves profundos | Prioriza subgraves e graves para dar peso à batida |
| Graves e agudos | Curva em V com graves fortes e agudos brilhantes |
| Agudos realçados | Destaca detalhes, vozes e brilho geral |
| Fones de ouvido | Equilíbrio pensado para fones com sensação de clareza |
| Sala ampla | Cria uma sensação mais aberta e ampla |
| Ao vivo | Presença de palco e ambiência |
| Festa | Curva para volumes casuais e músicas animadas |
| Pop | Voz, brilho e graves limpos |
| Reggae | Mais corpo nos graves com médios relaxados |
| Rock | Ataque de guitarras, caixa e presença geral |
| Ska | Baixo firme com médios e agudos vivos |
| Suave | Escuta suave, reduz agressividade |
| Rock suave | Equilíbrio com leve presença de voz e brilho |
| Techno | Batida, subgrave e brilho eletrônico |

### Dicas

- Reduza a pré-amplificação se o som começar a distorcer.
- Faça ajustes pequenos nas bandas para evitar exageros.
- Use **Salvar cópia...** sobre um preset embutido para partir de uma curva pronta e ajustar só o que precisar.
- Use **Duplicar...** em vez de editar diretamente quando quiser experimentar sem perder a versão anterior.

## YouTube Music

O KeyTune inclui uma aba dedicada ao YouTube Music. Use `Ctrl+Shift+Y` para abri-la. Ela funciona como uma aba separada, então você pode deixar a biblioteca local em uma aba e o YouTube Music em outra.

Para que a aba funcione, é necessário ativar a integração em `Ctrl+,` > **Recursos adicionais** e conectar uma conta.

A integração do YouTube Music depende da forma como o site muda e de como o `yt-dlp` interpreta essas páginas. Por isso, pode haver erros, falhas temporárias e até paradas sem explicação aparente; quando isso acontecer, normalmente é preciso atualizar as dependências ou tentar novamente mais tarde.

### Conta e biblioteca

A seção **Conta e biblioteca** mostra o status da conta conectada, o resumo da biblioteca carregada e a última mensagem de operação. Ela tem três botões:

- **Conectar conta...**: abre o diálogo para conectar uma conta do YouTube Music ou renovar a autenticação salva.
- **Desconectar conta**: remove a autenticação salva desta instalação.
- **Atualizar biblioteca**: busca novamente as playlists e mixes disponíveis na conta conectada.

Abaixo da seção de conta fica a lista **Playlists e mixes** com todas as playlists e mixes da biblioteca. Use o campo **Filtro** para localizar itens pelo nome. O contador acima da lista mostra quantos itens estão visíveis após o filtro. Abaixo da lista ficam as ações:

- **Abrir seleção**: abre a playlist ou mix selecionada em uma nova aba (`Enter` na lista faz o mesmo).
- **Nova playlist...**: cria uma playlist nova na sua conta. O player pede o nome e a privacidade (Privada, Não listada ou Pública). Veja [Gerenciar playlists do YouTube Music](#gerenciar-playlists-do-youtube-music).
- **Excluir playlist...**: exclui a playlist selecionada da sua conta, com confirmação. Só funciona em playlists que você criou — mixes, paradas e playlists de terceiros não podem ser excluídos.
- **Carregar mais playlists**: traz o próximo lote quando há mais playlists para carregar. Você também pode pressionar `Page Down` estando no fim da lista.

### Busca no catálogo e no YouTube

A seção **Busca no catálogo e no YouTube** fica recolhida por padrão. Expanda-a para pesquisar. Ela tem:

- **Campo de busca**: digite o que deseja procurar e pressione `Enter` ou clique em **Pesquisar**.
- **Escopo**: escolhe onde a busca será feita. As opções disponíveis são:
    - *YouTube Music — músicas*: faixas do catálogo do YouTube Music.
    - *YouTube Music — vídeos*: videoclipes e conteúdo em vídeo do YouTube Music.
    - *YouTube Music — playlists*: playlists do catálogo do YouTube Music.
    - *YouTube — vídeos*: vídeos do YouTube em geral, sem exigir conta.
- **Explorar**: quatro botões trazem mais conteúdo para a mesma lista de resultados:
    - **Em alta...**: abre um menu com *Global* no topo e os demais países agrupados em submenus por continente. Ao escolher um país, as paradas e os destaques em alta do YouTube Music aparecem na lista, como playlists que você pode abrir ou salvar na biblioteca. Não exige conta conectada.
    - **Moods e gêneros...**: abre um menu com as categorias de climas e gêneros do YouTube Music (por exemplo *Foco*, *Treino*, *Pop*, *Rock*). Ao escolher uma categoria, as playlists dela aparecem na lista. Não exige conta conectada.
    - **Curtidas**: carrega as faixas curtidas (a playlist *Curtidas/Liked Music* da sua conta). Exige conta conectada.
    - **Histórico**: carrega seu histórico de reprodução do YouTube Music, da faixa mais recente para a mais antiga. Exige conta conectada.
- **Lista de resultados**: mostra os itens encontrados (da busca, das paradas em alta, de moods e gêneros, das curtidas ou do histórico). A lista permite **seleção múltipla**: use `Ctrl+Setas` para mover o foco sem alterar a seleção, `Ctrl+Espaço` para marcar ou desmarcar o item em foco e `Shift+Setas` para selecionar um intervalo. `Enter` adiciona a seleção à playlist atual; `Ctrl+Enter` abre a seleção em nova playlist; `Shift+F10` ou o botão **Ações...** abre o menu contextual com opções adicionais.
- **Salvar no Music**: salva a seleção na biblioteca do YouTube Music quando o resultado for compatível (playlists ou faixas).

### Abrir playlist ou vídeo

A seção **Abrir playlist ou vídeo** também fica recolhida por padrão. Expanda-a para colar um link de playlist, mix ou vídeo do YouTube Music ou do YouTube. Clique em **Abrir link** ou pressione `Enter` no campo para abrir.

### Gerenciar playlists do YouTube Music

Além de abrir e salvar playlists, o KeyTune permite editar suas playlists diretamente na conta conectada. Todas essas ações exigem conta conectada e alteram a playlist **na sua conta do YouTube Music** — o que envolve excluir é confirmado antes e não pode ser desfeito pelo player.

**Adicionar faixas a uma playlist.** Selecione uma ou mais faixas do YouTube Music (na playlist atual ou na lista de resultados da busca) e use **Adicionar à playlist do YouTube Music...** no menu de contexto (`Shift+F10`), ou pressione `Ctrl+Shift+A` para adicionar a faixa que está tocando. Aparece uma lista das suas playlists editáveis; mixes e rádios personalizadas não entram nessa lista porque não aceitam edição. No topo da lista há a opção **Criar nova playlist...**, que cria uma playlist nova já com a seleção atual (mesmo comportamento do app do YouTube Music).

**Remover faixas de uma playlist.** Com uma playlist sua do YouTube Music aberta na aba atual, selecione as faixas e use **Remover da playlist do YouTube Music** no menu de contexto. O player pede confirmação e, ao concluir, remove as faixas também da aba aberta para que a lista continue espelhando a conta. A remoção só é oferecida em playlists que você criou ou onde é colaborador.

**Criar uma playlist.** Use **Nova playlist...** na seção *Playlists e mixes* para criar uma playlist vazia, ou **Criar nova playlist...** no diálogo de adicionar faixas para criar já com a seleção. Nos dois casos o player abre um diálogo onde você informa o **nome** e escolhe a **privacidade**: *Privada* (só você vê), *Não listada* (visível para quem tiver o link) ou *Pública* (aparece no seu perfil e pode surgir em buscas). O padrão é Privada. Depois de criar, a biblioteca é atualizada para a nova playlist aparecer na lista.

**Excluir uma playlist.** Selecione a playlist na lista *Playlists e mixes* e use **Excluir playlist...**. Só dá para excluir playlists que você criou; o player confirma antes e atualiza a biblioteca em seguida.

### Sessão do YouTube Music

Para utilizar os recursos da sua biblioteca (playlists salvas, histórico, curtidas e avaliações), é necessário conectar sua conta do YouTube Music. O KeyTune oferece dois modos de conexão no diálogo **Conectar conta**:

1. **Extrair do navegador instalado:** Selecione Firefox, Google Chrome, Microsoft Edge, Brave ou Opera na lista e clique em **Conectar**. O KeyTune extrai a sessão diretamente do perfil usando o `yt-dlp`. O Firefox é recomendado por oferecer maior compatibilidade no Windows.
2. **Importação de arquivo ou texto manual:** Para navegadores não listados ou configurações personalizadas, você pode importar um arquivo `cookies.txt` exportado ou colar os cabeçalhos HTTP da sessão.

No Windows, Chrome, Edge e Brave podem exigir que o navegador seja completamente fechado e, em algumas versões, a proteção do próprio navegador pode impedir a extração. Se isso acontecer, use o Firefox ou a importação manual.

#### O que são cookies

Cookies são pequenos arquivos de texto que navegadores armazenam para lembrar suas preferências e informações de login em sites. Quando você faz login no YouTube Music, o navegador salva cookies que contêm sua autenticação. Ao conectar sua conta no KeyTune, o aplicativo utiliza essa informação de sessão logada para acessar sua biblioteca sem pedir sua senha.

#### Como conectar via extração direta do navegador

1. Certifique-se de que está logado na sua conta no [YouTube Music](https://music.youtube.com/) em seu navegador (Chrome, Edge, Firefox, Brave ou Opera).
2. No KeyTune, abra a aba do YouTube Music (`Ctrl+Shift+Y`).
3. Na seção **Conta e biblioteca**, clique em **Conectar conta...**.
4. No diálogo que abre, selecione a opção **Extrair do navegador instalado**.
5. Escolha o seu navegador na lista e clique no botão **Conectar**.

#### Passo a passo alternativo: exportação manual de cookies.txt

Se você optar pelo modo manual ou usar um navegador não suportado diretamente:

**Pré-requisito:** instale a extensão [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc) em seu navegador.

**1. Ativar a extensão em abas anônimas**

Usar uma aba anônima/privada evita que o Google renove os cookies frequentemente durante o uso normal do navegador.

1. Pressione `Ctrl+L` para focar a barra de endereços.
2. Pressione `Escape` para sair da caixa de edição da barra de endereços.
3. Pressione `Alt+F` para abrir o menu do navegador.
4. Navegue com as setas até **Extensões**, expanda o submenu pressionando `Enter` e escolha **Gerenciar extensões**.
5. Localize **Get cookies.txt LOCALLY** e clique em **Detalhes** (ou "Saiba mais").
6. Na página de detalhes, localize a opção **Permitir em abas privadas** ou **Permitir em navegação anônima** e ative-a.
7. Feche a página e retorne ao seu navegador.

**2. Fazer login e exportar cookies**

1. Abra uma nova aba anônima/privada (`Ctrl+Shift+N` ou `Ctrl+Shift+P`).
2. Navegue para [music.youtube.com](https://music.youtube.com/).
3. Faça login com sua conta Google.
4. Abra a extensão **Get cookies.txt LOCALLY** e clique em **Exportar** ou **Download** para salvar o arquivo `cookies.txt`.
5. Feche a aba anônima sem navegar para outros sites.

**3. Importar no KeyTune**

1. No diálogo **Conectar conta...** do KeyTune, selecione **Importar arquivo ou texto manual**.
2. Selecione o arquivo `cookies.txt` baixado (ou cole o texto dos cabeçalhos) e clique em **Conectar**.

#### Informações de segurança

O arquivo `cookies.txt` exportado contém informações de autenticação da sua conta. Por segurança:

- Use o arquivo apenas no seu próprio computador.
- Não compartilhe o arquivo com outras pessoas.
- Exclua o arquivo após importá-lo no KeyTune se desejar. A cópia interna contém somente os cookies do YouTube necessários para a conexão.
- Se desconectar a conta no KeyTune, os cookies armazenados serão removidos.

### Atalhos

- `Ctrl+Shift+Y`: abrir a aba do YouTube Music
- `Ctrl+Shift+A`: adicionar a mídia atual a uma playlist do YouTube Music
- `Enter` no campo de busca: executar a pesquisa
- `Enter` na lista de resultados: adicionar o item à playlist atual
- `Ctrl+Enter` na lista de resultados: abrir o item em nova playlist
- `Ctrl+Espaço` na lista de resultados: marcar ou desmarcar o item em foco (seleção múltipla)
- `Ctrl+Setas` na lista de resultados: mover o foco sem alterar a seleção
- `Shift+Setas` na lista de resultados: selecionar um intervalo de itens
- `Shift+F10` na lista de resultados: abrir o menu de ações
- `Enter` na lista de playlists da biblioteca: abrir a seleção
- `Page Down` no fim da lista de playlists: carregar mais playlists
- `Esc`: fechar a aba quando ela estiver em foco

## Recursos de acessibilidade

O aplicativo foi projetado para leitores de tela e uso por teclado. Em geral:

- o foco evita saltos desnecessários para a área nativa de vídeo;
- anúncios de estado e de navegação são feitos quando o suporte de acessibilidade está disponível;
- campos, botões e listas têm nomes e descrições legíveis por leitores de tela.

Se você usa leitor de tela, os atalhos de anúncio sob demanda `T`, `V` e `S` (descritos em [Atalhos de reprodução](#atalhos-de-reproducao)) e a ajuda rápida `F1` ajudam a se localizar sem depender dos eventos automáticos.

Os anúncios automáticos — como troca de faixa, mudança de aba e alteração de volume — podem ser ligados ou desligados em `Ctrl+,` > **Acessibilidade**.

A busca de itens evita anúncios redundantes: como `Ctrl+F`, `F3` e `Shift+F3` movem a seleção para o item encontrado, quem lê a faixa é o próprio leitor de tela, e a posição na busca fica só na barra de status. O temporizador, por sua vez, avisa ao ser agendado, faltando 5 minutos, faltando 1 minuto e ao pausar a reprodução; seu estado também aparece no anúncio da tecla `S`.

O painel de letras também foi pensado para esse uso: `Ctrl+Alt+L` ou a caixa **Letras** na área de tempo mostram ou ocultam o painel, e o texto pode ser lido, navegado com as setas e copiado pelo botão **Copiar letra completa**. Ao trocar de faixa, o player tenta buscar a letra automaticamente primeiro no LRCLIB e depois no YouTube Music.

## Atualizações

Ao iniciar, o KeyTune pode verificar atualizações automaticamente. Para verificar manualmente a qualquer momento, use o menu **Ajuda > Verificar atualizações**.

Quando houver uma versão nova, o aplicativo mostra um diálogo com as notas da release, o nome do arquivo e o tamanho do download antes de pedir confirmação. Se você aceitar, o aplicativo baixa o pacote, mostra o andamento do download e pede permissão para instalar depois que o arquivo estiver pronto. Se você cancelar ou fechar o diálogo, nada é instalado e o player continua funcionando normalmente.

## Solução de problemas

Se o aplicativo não abrir corretamente, confira primeiro se a instalação foi concluída sem erros (reinstalar com o instalador mais recente resolve a maioria dos casos) e se o sistema tem permissão para acessar os arquivos ou pastas que você tentou abrir.

Se o player não encontrar o runtime do MPV, verifique se ele está em um destes caminhos: uma pasta `mpv/` ao lado do executável, `MPV_HOME`, `MPV_DLL_DIR`, o cache salvo da execução anterior ou uma instalação do Chocolatey compatível.

Se uma mídia não abrir, teste outro arquivo local para separar problema de caminho inválido, permissão ou tipo de arquivo incompatível.

Se a associação de arquivos não funcionar como esperado, há dois passos separados a confirmar: primeiro, que o KeyTune foi registrado como opção (durante a instalação ou depois em **Configurações > Geral > Registrar como player padrão**); segundo, que ele foi escolhido como aplicativo padrão para esses formatos nas configurações de apps padrão do Windows — o registro por si só não torna o KeyTune o padrão automaticamente.

Se a restauração de sessão falhar, abra o app uma vez sem depender da sessão anterior e verifique se a configuração de janela e pasta estão sendo salvas normalmente.

Se a aba do YouTube Music não carregar ou exibir erros de dependência, abra `Ctrl+,` > **Recursos adicionais** e confirme que a opção **Ativar recursos adicionais para YouTube Music e YouTube** está marcada. O download inicial pode levar alguns minutos e exige internet. Se as dependências já estiverem instaladas mas a busca ou o carregamento falharem, use a versão nightly do `yt-dlp` nas mesmas preferências — ela costuma receber correções antes do canal estável.

Se a sessão do YouTube Music expirar ou o player pedir autenticação novamente, exporte os cookies do navegador conforme descrito na seção [Sessão do YouTube Music](#sessao-do-youtube-music) e reconecte a conta.

Para investigar outros problemas, ative o registro de logs em `Ctrl+,` > **Geral** > **Registro de logs**. Com **Registrar logs de diagnóstico** ligado e o nível ajustado para *Depuração*, o player grava informações detalhadas em `keytune.log` na pasta de dados. Use **Abrir pasta de logs** para localizar o arquivo e, se precisar reportar um problema, anexe-o à issue.

## Para desenvolvedores

O KeyTune é um projeto de código aberto. O repositório, issues, pull requests e releases estão em [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). O fonte deste manual está em [docs/manual.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md).
