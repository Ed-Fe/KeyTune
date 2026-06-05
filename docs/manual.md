# Manual do KeyTune

O KeyTune é um player de mídia feito para uso por teclado e com foco em acessibilidade. Ele foi pensado para funcionar bem com playlists, navegação por pastas e para manter o que você estava fazendo entre uma abertura e outra.

Este manual apresenta os recursos principais do aplicativo e as ações mais comuns para começar a usar o player com rapidez.

## O que o KeyTune oferece

- Reprodução de mídia com controle por teclado
- Playlists em abas
- Navegação por pastas com pré-visualização
- Equalizador por aba com predefinições e presets personalizados
- Aba dedicada do YouTube Music, aberta com `Ctrl+Shift+Y`
- Carregamento e gravação de playlists
- Restauração do que estava aberto na última sessão
- Lista de arquivos, pastas e playlists recentes
- Anúncios de acessibilidade quando leitores de tela estão disponíveis

## Primeiros passos

1. Extraia os arquivos do aplicativo para uma pasta local.
2. Execute o arquivo `KeyTune.exe`.
3. Se houver uma atualização disponível, o aplicativo mostra um diálogo com as novidades e pede confirmação antes de instalar.

O KeyTune depende do runtime do MPV para reproduzir mídia. O runtime precisa estar em uma pasta `mpv/` ao lado do executável, ou em um dos caminhos reconhecidos automaticamente (veja a seção **Solução de problemas**). Se o player abrir mas não reproduzir nada, esse é o primeiro ponto a verificar.

## Como abrir mídia

Você pode abrir arquivos de mídia, uma playlist local, uma pasta ou um caminho e link compatível usando os atalhos ou o menu **Arquivo**:

- `Ctrl+Alt+O` — diálogo unificado que aceita qualquer tipo: arquivo, pasta, playlist, link ou ID do YouTube Music.
- `Ctrl+O` — abre arquivos de mídia ou uma playlist `.m3u`/`.m3u8`.
- `Ctrl+Shift+O` — abre uma pasta diretamente no navegador de pastas.
- `Ctrl+V` — cola um caminho ou link da área de transferência na playlist atual.
- `Ctrl+Shift+V` — cola e abre em uma nova playlist.

Formatos de mídia suportados diretamente: `.mp3`, `.wav`, `.flac`, `.aac`, `.ogg` (áudio) e `.mp4`, `.mkv`, `.avi`, `.mov` (vídeo).

O menu **Arquivo > Recentes** guarda separadamente os últimos **Arquivos recentes**, **Pastas recentes** e **Playlists recentes**, facilitando reabrir o que você usou antes sem precisar navegar de novo.

## Playlist, pastas e abas

Cada playlist fica em uma aba separada. Isso ajuda a separar contextos, como uma lista de músicas para ouvir agora, uma pasta com arquivos locais ou uma coleção que você quer deixar organizada.

A aba ativa define o que está sendo reproduzido e o que aparece no navegador lateral. Você pode manter uma aba para uma playlist salva, outra para uma pasta inteira e outras para listas temporárias, sem misturar tudo no mesmo contexto. As abas podem ser abertas, alternadas e fechadas sem afetar as outras.

### Atalhos de arquivos e abas

- `Ctrl+T`: abrir uma nova aba de playlist
- `Ctrl+W`: fechar a mídia atual ou uma aba vazia
- `Ctrl+Shift+W`: fechar a aba ou playlist atual
- `Ctrl+Tab` / `Ctrl+Shift+Tab`: navegar para a próxima ou aba anterior
- `Ctrl+Shift+E`: abrir o equalizador da aba ativa
- `Ctrl+O`: abrir arquivos de mídia ou uma playlist local
- `Ctrl+Shift+O`: abrir uma pasta diretamente no navegador de pastas
- `Ctrl+Alt+O`: abrir mídia, playlist ou pasta no diálogo unificado
- `Ctrl+C`: copiar o caminho ou link do item selecionado
- `Ctrl+V`: colar um caminho ou link e, quando possível, adicioná-lo à playlist atual
- `Ctrl+Shift+V`: colar um caminho, playlist ou link e abrir em uma nova playlist
- `Ctrl+Shift+S`: salvar a playlist atual
- `Ctrl+B`: alternar foco entre o navegador de itens e o player

### Atalhos de reprodução

- `Espaço`: reproduzir ou pausar
- `Seta esquerda` / `Seta direita`: voltar ou avançar na mídia atual
- `Home` / `End`: ir para o início ou para o fim da mídia
- `Seta cima` / `Seta baixo`: aumentar ou diminuir o volume
- `Ctrl+.`: parar a reprodução
- `Ctrl+PageUp` / `Ctrl+PageDown`: faixa anterior ou próxima na playlist
- `E`: alternar modo aleatório
- `R`: alternar modo de repetição
- `T`: anunciar o tempo atual da mídia
- `V`: anunciar o volume atual
- `S`: anunciar o status do player
- `Ctrl+L`: curtir a mídia atual no YouTube Music
- `Ctrl+Shift+L`: marcar a mídia atual como não gostei no YouTube Music

Quando uma aba está vazia, `Ctrl+W` fecha essa aba; quando há mídia carregada, o mesmo atalho remove só o item atual ou encerra a reprodução da aba ativa.

### Navegador de itens

O navegador fica à esquerda da janela e opera em dois modos distintos dependendo do que está na aba ativa: **modo playlist** e **modo pasta**. Use `Tab` ou `Ctrl+B` para alternar o foco entre o navegador e o player.

#### Modo playlist

Quando a aba contém uma playlist, o navegador mostra todos os itens da sequência. O item em reprodução fica marcado com `▶` no início da linha. Os atalhos disponíveis são:

- `Enter`: toca o item selecionado imediatamente.
- `Delete`: remove o item selecionado da playlist.
- `Shift+F10`: abre o menu contextual com ações adicionais sobre o item.
- `Tab` / `Esc`: volta o foco para o player.

#### Modo pasta

Quando a aba veio de uma pasta aberta com `Ctrl+Shift+O`, o navegador exibe o conteúdo do diretório atual: subpastas e arquivos de mídia. Conforme a reprodução avança, o item correspondente à mídia atual fica em destaque automaticamente. Ao mover a seleção para um arquivo de mídia, o player já inicia a reprodução desse arquivo. Os atalhos disponíveis são:

- `Enter`: entra na subpasta selecionada ou toca o arquivo de mídia.
- `Backspace`: volta para a pasta superior (equivale a selecionar `..`).
- `Shift+F10`: abre o menu contextual.
- `Tab` / `Esc`: volta o foco para o player.

#### Localização rápida por digitação

Nos dois modos, digitar letras ou números move a seleção para o primeiro item cujo nome começa com os caracteres digitados. A busca ignora acentos e diferenças entre maiúsculas e minúsculas. Após um segundo sem digitar, o acumulador de caracteres é resetado e a próxima letra inicia uma nova busca.

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

### Reprodução

A aba **Reprodução** controla o comportamento de áudio e o estado inicial de novas playlists:

- **Volume padrão**: volume ao iniciar o player (0–100).
- **Passo de volume**: quanto cada pressão de `Seta cima`/`Seta baixo` aumenta ou diminui o volume (1–25).
- **Passo de busca (segundos)**: quanto cada pressão de `Seta esquerda`/`Seta direita` avança ou retrocede na mídia (1–120 s).
- **Crossfade (segundos)**: sobreposição de áudio entre faixas na transição automática (0–12 s). Use 0 para desativar. O crossfade só é aplicado entre arquivos de áudio.
- **Aplicar crossfade ao trocar de faixa manualmente**: quando ligado, o crossfade também é usado ao avançar ou voltar manualmente; por padrão só vale no fim natural de cada faixa.
- **Repetição padrão**: modo de repetição aplicado automaticamente a playlists novas. As opções são *Repetição desligada*, *Repetir faixa atual* e *Repetir playlist*.
- **Dispositivo de áudio**: saída de som usada na reprodução. *Padrão do sistema* segue o dispositivo principal do Windows.
- **Ativar embaralhamento em novas playlists**: ativa o modo aleatório automaticamente em playlists criadas depois de salvar.
- **Desativar saída de vídeo (tocar só o áudio)**: mantém a reprodução apenas em áudio, inclusive em arquivos de vídeo. Útil para evitar janelas externas de vídeo.

### Acessibilidade

A aba **Acessibilidade** tem uma única opção: **Ativar anúncios de acessibilidade**. Quando ligada, o player anuncia mudanças de tempo, volume, troca de abas e status ao leitor de tela. Quando desligada, esses anúncios são suprimidos. Os atalhos de anúncio sob demanda (`T`, `V`, `S`) continuam funcionando independentemente dessa configuração — veja a seção **Acessibilidade** para detalhes.

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

### Conta e biblioteca

A seção **Conta e biblioteca** mostra o status da conta conectada, o resumo da biblioteca carregada e a última mensagem de operação. Ela tem três botões:

- **Conectar conta...**: abre o diálogo para conectar uma conta do YouTube Music ou renovar a autenticação salva.
- **Desconectar conta**: remove a autenticação salva desta instalação.
- **Atualizar biblioteca**: busca novamente as playlists e mixes disponíveis na conta conectada.

Abaixo da seção de conta fica a lista **Playlists e mixes** com todas as playlists e mixes da biblioteca. Use o campo **Filtro** para localizar itens pelo nome. O contador acima da lista mostra quantos itens estão visíveis após o filtro. Quando há mais playlists para carregar, o botão **Carregar mais playlists** fica disponível; você também pode pressionar `Page Down` estando no fim da lista para carregar o próximo lote.

### Busca no catálogo e no YouTube

A seção **Busca no catálogo e no YouTube** fica recolhida por padrão. Expanda-a para pesquisar. Ela tem:

- **Campo de busca**: digite o que deseja procurar e pressione `Enter` ou clique em **Pesquisar**.
- **Escopo**: escolhe onde a busca será feita. As opções disponíveis são:
    - *YouTube Music — músicas*: faixas do catálogo do YouTube Music.
    - *YouTube Music — vídeos*: videoclipes e conteúdo em vídeo do YouTube Music.
    - *YouTube Music — playlists*: playlists do catálogo do YouTube Music.
    - *YouTube — vídeos*: vídeos do YouTube em geral, sem exigir conta.
- **Lista de resultados**: mostra os itens encontrados. `Enter` adiciona a seleção à playlist atual; duplo clique abre em nova playlist; `Shift+F10` ou o botão **Ações...** abre o menu contextual com opções adicionais.
- **Salvar no Music**: salva a seleção na biblioteca do YouTube Music quando o resultado for compatível (playlists ou faixas).

### Abrir playlist específica

A seção **Abrir playlist específica** também fica recolhida por padrão. Expanda-a para colar um link completo do YouTube Music ou do YouTube, ou informar diretamente o ID de uma playlist ou mix. Clique em **Abrir pelo link ou ID** ou pressione `Enter` no campo para abrir.

### Sessão do YouTube Music

Na maioria das vezes o KeyTune vai pedir essa sessão para funcionar corretamente com o YouTube Music, especialmente na primeira vez ou quando a autenticação expirar. Se isso acontecer, exporte os cookies da conta que já está logada no navegador.

1. Instale a extensão [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc).
2. Abra o [YouTube Music](https://music.youtube.com/) no mesmo navegador e faça login na sua conta.
3. Clique na extensão e exporte os cookies no formato `cookies.txt`.
4. No KeyTune, use a opção de importar ou carregar a sessão do YouTube Music quando ela for exibida.

O arquivo exportado contém informações de acesso da sua conta. Use apenas no seu computador e só com a conta que você quer conectar ao aplicativo.

### Atalhos

- `Ctrl+Shift+Y`: abrir a aba do YouTube Music
- `Enter` no campo de busca: executar a pesquisa
- `Enter` na lista de resultados: adicionar o item à playlist atual
- duplo clique na lista de resultados: abrir o item em nova playlist
- `Shift+F10` na lista de resultados: abrir o menu de ações
- `Enter` na lista de playlists da biblioteca: abrir a seleção
- `Page Down` no fim da lista de playlists: carregar mais playlists
- `Esc`: fechar a aba quando ela estiver em foco

## Acessibilidade

O aplicativo foi projetado para leitores de tela e uso por teclado. Em geral:

- o foco evita saltos desnecessários para a área nativa de vídeo;
- anúncios de estado e de navegação são feitos quando o suporte de acessibilidade está disponível;
- campos, botões e listas têm nomes e descrições legíveis por leitores de tela.

Se você usa leitor de tela, use os atalhos de anúncio sob demanda para se localizar sem depender dos eventos automáticos:

- `T`: anuncia o tempo atual da mídia em reprodução.
- `V`: anuncia o volume atual.
- `S`: anuncia o status geral do player (reproduzindo, pausado, parado).
- `F1`: abre a ajuda rápida de atalhos.

Os anúncios automáticos — como troca de faixa, mudança de aba e alteração de volume — podem ser ligados ou desligados em `Ctrl+,` > **Acessibilidade**.

## Atualizações

Ao iniciar, o KeyTune pode verificar atualizações automaticamente. Para verificar manualmente a qualquer momento, use o menu **Ajuda > Verificar atualizações**.

Quando houver uma versão nova, o aplicativo mostra um diálogo com as notas da release, o nome do arquivo e o tamanho do download antes de pedir confirmação. Se você aceitar, o aplicativo baixa o pacote, mostra o andamento do download e pede permissão para instalar depois que o arquivo estiver pronto. Se você cancelar ou fechar o diálogo, nada é instalado e o player continua funcionando normalmente.

## Solução de problemas

Se o aplicativo não abrir corretamente, confira primeiro se os arquivos foram extraídos para uma pasta local e se o sistema tem permissão para acessar os arquivos ou pastas que você tentou abrir.

Se o player não encontrar o runtime do MPV, verifique se ele está em um destes caminhos: uma pasta `mpv/` ao lado do executável, `MPV_HOME`, `MPV_DLL_DIR`, o cache salvo da execução anterior ou uma instalação do Chocolatey compatível.

Se uma mídia não abrir, teste outro arquivo local para separar problema de caminho inválido, permissão ou tipo de arquivo incompatível.

Se a associação de arquivos não funcionar como esperado, registre a opção nas preferências do Windows e confirme também o app como padrão para os formatos compatíveis.

Se a restauração de sessão falhar, abra o app uma vez sem depender da sessão anterior e verifique se a configuração de janela e pasta estão sendo salvas normalmente.

Se a aba do YouTube Music não carregar ou exibir erros de dependência, abra `Ctrl+,` > **Recursos adicionais** e confirme que a opção **Ativar recursos adicionais para YouTube Music e YouTube** está marcada. O download inicial pode levar alguns minutos e exige internet. Se as dependências já estiverem instaladas mas a busca ou o carregamento falharem, use a versão nightly do `yt-dlp` nas mesmas preferências — ela costuma receber correções antes do canal estável.

Se a sessão do YouTube Music expirar ou o player pedir autenticação novamente, exporte os cookies do navegador conforme descrito na seção **Sessão do YouTube Music** e reconecte a conta.

## Para desenvolvedores

O KeyTune é um projeto de código aberto. O repositório, issues, pull requests e releases estão em [github.com/ed-fe/KeyTune](https://github.com/ed-fe/KeyTune). O fonte deste manual está em [docs/manual.md](https://github.com/ed-fe/KeyTune/blob/main/docs/manual.md).
