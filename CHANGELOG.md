# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Não lançado]

### Adicionado
- **Em alta por país (YouTube Music)**: botão **Em alta...** na seção *Explorar* da aba do YouTube Music abre um menu com *Global* no topo e mais de 50 países agrupados em submenus por continente. Ao escolher um país, as paradas e os destaques em alta entram na lista de busca já existente, prontos para abrir como playlist ou salvar na biblioteca. Funciona sem conectar a conta (cliente público do `ytmusicapi`).
- **Moods e gêneros (YouTube Music)**: botão **Moods e gêneros...** abre um menu com as categorias de climas e gêneros do YouTube Music e carrega as playlists da categoria escolhida na lista de resultados. Funciona sem conta conectada. Inclui um analisador resiliente próprio para as páginas de *Gêneros*, que o `ytmusicapi` 1.12.0 não consegue interpretar sozinho.
- **Curtidas e Histórico (YouTube Music)**: botões **Curtidas** e **Histórico** trazem, respectivamente, as faixas curtidas da conta e o histórico de reprodução (da mais recente para a mais antiga) para a lista de resultados, prontos para abrir, tocar ou adicionar a uma playlist.

### Corrigido
- **Conexão do YouTube Music que expirava de um dia para o outro**: o diálogo de conexão e o manual agora explicam que o Google troca os cookies da sessão por segurança quando você continua navegando logado no YouTube, invalidando os cookies já exportados. A orientação recomenda exportar os cookies em uma janela anônima/privada e fechá-la sem reabrir o YouTube, para que a autenticação dure muito mais.

## [1.0.0] - 2026-06-07

Primeira versão oficial estável (Release) do **KeyTune**. Consolida todos os recursos principais de reprodução de mídia acessível, playlists em abas, equalização, sistema de diagnóstico avançado e integração completa com YouTube Music.

### Resumo dos Recursos

- **Interface Acessível e Foco em Teclado**: Totalmente otimizado para leitores de tela com atalhos de teclado robustos, mnemônicos e anúncios sonoros sob demanda para tempo, volume e status da mídia.
- **Playlists em Abas**: Gerenciamento de múltiplos contextos de playlist em abas individuais com reordenação de faixas, salvamento e carregamento assíncrono de playlists `.m3u` e `.m3u8`.
- **Navegador de Pastas Integrado**: Navegação rápida estilo Explorer por arquivos e subpastas de mídia, com pré-visualização instantânea e automática na seleção de arquivos.
- **Restauração de Sessão Inteligente**: Retoma automaticamente o estado anterior ao reiniciar o player (abas abertas, mídia ativa, posição exata da faixa, volume e configurações).
- **Equalizador Independente por Aba**: Ajuste fino de áudio individual por aba de playlist com 18 presets embutidos (Club, Rock, Bass, etc.), editor de presets personalizados e opção de replicar a equalização para todas as abas.
- **Integração com YouTube Music & YouTube**: Busca integrada no catálogo, suporte completo a mixes personalizadas e playlists da conta do usuário via importação de cookies do navegador, com resolução de áudio sob demanda via `yt-dlp`.
- **Associação de Arquivos no Windows**: Registro e desregistro simplificados de extensões de mídia para abrir arquivos diretamente com o KeyTune através do Explorador.
- **Sistema de Logs de Diagnóstico**: Diagnóstico detalhado com rotação automática de arquivos de logs e configuração ao vivo do nível de detalhes nas preferências.
- **Atualização Automática no Windows**: Detecção de novas versões, visualização de notas de release, download assíncrono com progresso visual e aplicação limpa via atualizador autônomo (`KeyTuneUpdater.exe`).

### Ajustes e Melhorias Recentes
- **Atalhos Aprimorados**: Inversão estratégica dos atalhos de fechamento (agora `Ctrl+W` fecha a aba ativa e `Ctrl+Shift+W` fecha ou descarrega a mídia atual) para maior fluidez e consistência com navegadores modernos.
- **Seleção Avançada na Busca**: Substituição do componente de resultados da busca do YouTube Music por uma lista virtualizada (`VirtualItemsListCtrl`), suportando seleção múltipla via teclado (`Ctrl+Arrow` e `Ctrl+Space`).
- **Arquitetura Modular**: Modularização completa do serviço de YouTube Music em subsistemas dedicados (cache, autenticação, gerenciador de biblioteca e feedbacks) para maior estabilidade.
- **Correções de Navegação e Foco**: Correção de travamento de foco com Tab/Shift+Tab nas abas de YouTube Music e Equalizador, além de validação aprimorada de curtidas/feedbacks.
- **Atualizações de Dependências**: Tratamento robusto para arquivos `.pyd` bloqueados no Windows durante a atualização em segundo plano do `yt-dlp` e pacotes auxiliares.


## [0.4.1] - 2026-04-12

### Fixed
- O empacotamento Windows da release agora inclui os arquivos de localização do `ytmusicapi`, corrigindo a falha do YouTube Music ao listar playlists com a mensagem `No translation file found for domain: 'base'`.
- Arquivos de mídia enviados pelo Explorador para uma instância já aberta do player agora são adicionados à playlist existente, em vez de abrir automaticamente uma nova playlist.
- O recebimento de arquivos externos por instância única não força mais o foco da janela; se o app estiver minimizado, ele apenas restaura a janela e pede atenção ao usuário.

## [0.4.0] - 2026-04-12

### Added
- Novo diálogo **Abrir mídia, playlist ou pasta** para abrir arquivos de mídia, playlists `.m3u/.m3u8`, links de playlist e pastas a partir de um único fluxo.
- Suporte a abrir playlists remotas `.m3u/.m3u8` por URL, preservando entradas remotas e resolvendo caminhos relativos a partir da origem da playlist.
- Suporte inicial ao **YouTube Music** com autenticação por navegador, importação de `browser.json`/JSON de cookies/`cookies.txt`, abertura de playlists e mixes da conta e resolução de streams com `yt-dlp`.
- Configuração de **crossfade** nas Preferências, com suporte a sobrepor automaticamente faixas de áudio e opção `0` para desativar o recurso.
- Botão **Aplicar em todas as abas** no Equalizador para copiar o preset e o estado atual para todas as abas de mídia abertas.
- Preferência **Desativar saída de vídeo (tocar só o áudio)**, ativada por padrão, para evitar janelas externas do VLC quando o usuário quer reproduzir vídeos só com áudio.
- **Instância única**: ao abrir um arquivo com o player já rodando, o item é adicionado à playlist da instância existente em vez de abrir uma segunda janela.
- Suporte a receber arquivos pela **linha de comando** (`sys.argv`), permitindo abrir mídias diretamente pelo Explorador de Arquivos ou atalhos.
- Opção em **Preferências > Geral** para registrar e desregistrar o player como handler de arquivos de mídia e playlists no Windows (menu Abrir Com).

### Changed
- A barra de menu foi reorganizada para separar melhor ações de arquivo, reprodução, abas, exibição e ajuda, deixando atalhos e comandos relacionados mais fáceis de localizar.
- O menu **Arquivo** passou a concentrar a abertura geral em uma única ação, mantendo atalhos específicos para abrir arquivos locais e pastas no navegador.
- O atalho `Ctrl+O` agora aceita tanto arquivos de mídia quanto uma playlist local `.m3u/.m3u8`, usando o mesmo conjunto de tipos do seletor **Arquivo...** do diálogo unificado.
- Pastas locais agora podem ser abertas tanto no navegador quanto como playlists estáticas carregadas de forma assíncrona.
- A reprodução passou a usar players VLC dedicados por faixa no crossfade, com tratamento específico para o backend de áudio do Windows e melhor folga de inicialização entre músicas.
- A área do player agora mostra uma mensagem clara quando a saída de vídeo está desativada e a mídia está tocando em modo áudio apenas.
- O submenu **YouTube Music** passou a atualizar o estado da conexão, permitir desconectar a conta salva e carregar playlists/mixes sem bloquear a interface.
- Durante operações em segundo plano do **YouTube Music**, comandos sensíveis de troca de faixa, seleção direta, repetição, embaralhamento e fechamento da mídia atual ficam temporariamente bloqueados para evitar corridas de estado.
- Abas restauradas do YouTube Music agora tentam recuperar novamente os rótulos corretos das faixas após reconectar a conta.
- O código do player foi reorganizado por responsabilidades em pacotes como `frames/`, `library/`, `playlists/`, `preferences/`, `equalizer/`, `update/` e `youtube_music/`, com divisão adicional dos fluxos de biblioteca em mixins menores.

### Fixed
- Transições de áudio com menos cortes e sem retorno repentino de volume no fim do crossfade ao avançar entre faixas compatíveis.
- Próxima/anterior e crossfade do YouTube Music ficaram mais estáveis com cache/prefetch de streams, espera maior pela próxima faixa quando o stream ainda está aquecendo e fallback automático para reprodução normal só depois desse tempo extra.
- Operações em segundo plano do YouTube Music agora têm timeout defensivo para evitar deixar o app preso em estado ocupado.
- Tentativas de usar próxima/anterior durante uma operação do YouTube Music agora também disparam o aviso sonoro característico do Windows como alerta extra.

### Notes
- Esta versão inclui uma refatoração estrutural grande. Apesar da validação rápida e das verificações feitas durante o desenvolvimento, ainda podem aparecer problemas ou regressões em fluxos menos exercitados.
- Se você encontrar qualquer comportamento estranho, travamento, atalho quebrado, regressão de acessibilidade ou falha ao abrir mídia/playlist/pasta, por favor reporte um bug com o máximo de detalhes possível.

## [0.3.0] - 2026-04-12

### Added
- Atalho `Ctrl+Shift+W` para fechar a aba ou playlist atual diretamente.
- Navegação por digitação de letras e números no navegador de itens para localizar arquivos e faixas mais rápido.
- Carregamento assíncrono de playlists e do explorador de pastas, com mensagens de carregamento enquanto a biblioteca é preparada.

### Changed
- O navegador de itens passou a usar uma lista virtual compartilhada por playlists e pastas para lidar melhor com bibliotecas grandes.
- A leitura inicial de pastas agora reaproveita uma única varredura para montar entradas do navegador e a lista de mídias da aba.
- O explorador de pastas não mostra mais um marcador visual de reprodução ao lado do arquivo em prévia.
- O aplicativo passou a se chamar **KeyTune** na interface e na documentação principal, sem o sufixo técnico.
- Inclusão de mnemônicos com `&` em botões e opções de Preferências, Equalizador, Ajuda rápida de atalhos e diálogos de atualização para melhorar a navegação por teclado.

### Fixed
- Redução das travadas ao abrir pastas muito grandes, transferindo a carga pesada para um worker e aliviando a primeira pintura do navegador.
- Redução do custo de atualização de playlists grandes com cache de índices, reaproveitamento de rótulos e refresh incremental da lista.
- Restauração do volume salvo ao abrir o app com sessão recuperada, aplicando corretamente o nível anterior já no início da reprodução.
- Preservação da posição atual do áudio ao entrar e sair da aba do equalizador, sem voltar para o tempo em que a aba foi aberta.
- Retorno ao modo de foco correto ao fechar o equalizador e eliminação do corte no áudio causado pelo recarregamento desnecessário da mesma mídia.

## [0.2.0] - 2026-04-11

### Added
- Verificação automática de atualizações ao iniciar a versão empacotada do Windows.
- Visualização das notas da release antes de confirmar o download da atualização.
- Diálogo de download com barra de progresso para baixar novas releases antes de instalar.
- Atualizador externo para aplicar o ZIP da release sem sobrescrever arquivos em uso.
 - Geração e publicação do arquivo `KeyTune-windows.zip.sha256` nas releases.
- Script local para gerar a release Windows e roteiro documentado para testar o atualizador ponta a ponta.

### Changed
 - Workflow de release do Windows para incluir `KeyTuneUpdater.exe` no pacote publicado.

## [0.1.0] - 2026-04-11

### Added
- Windows release workflow (`.github/workflows/release-windows.yml`) to build and publish a ZIP package.
- Bundled MPV runtime in release artifacts (`dist/KeyTune/mpv`) so users can run without MPV preinstalled.
- Runtime bootstrap (`src/player/mpv_runtime.py`) to detect a local MPV folder and configure DLL loading on Windows.

### Changed
- Startup flow in `src/main.py` to initialize the bundled MPV runtime before loading the app.
- `README.md` with release packaging instructions for GitHub Actions.
- `.gitignore` to ignore local packaging outputs (`build/`, `dist/`, `*.zip`).
