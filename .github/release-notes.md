# KeyTune 1.0.0

Primeira versão oficial estável (Release) do **KeyTune**. Este lançamento consolida os recursos principais desenvolvidos, trazendo um player de mídia acessível, moderno e focado em controle total via teclado.

## Recursos Principais

- **Acessibilidade Completa**: Otimizado para uso por teclado e leitores de tela (NVDA, JAWS, Narrador). Foco inteligente, mnemônicos e anúncios sonoros automáticos ou sob demanda (tempo de reprodução com `T`, volume com `V` e status com `S`).
- **Navegador Lateral e Visualização de Pastas**: Navegação rápida estilo Explorer por arquivos e subpastas de mídia. Inclui pré-visualização instantânea (toca o arquivo automaticamente ao focar com teclado).
- **Playlists em Abas**: Abra e organize múltiplas abas de playlist de forma assíncrona. Suporte completo para carregar, ordenar e salvar playlists locais nos formatos `.m3u` e `.m3u8`.
- **Restauração de Sessão**: Retome o player do ponto exato onde parou: abas abertas, faixa ativa, tempo de reprodução atual, volume e tamanho da janela.
- **Equalizador por Aba**: Ajuste de graves, médios e agudos independente para cada aba de playlist. Possui 18 presets integrados (Club, Rock, graves profundos, etc.), editor de presets customizados e sincronização rápida em todas as abas.
- **Integração com YouTube Music**: Aba dedicada (`Ctrl+Shift+Y`) com busca no catálogo, mixes e playlists da biblioteca integrados (via importação de cookies). Reprodução fluida por streaming e cache inteligente de URLs de áudio usando `yt-dlp`.
- **Associação de Arquivos no Windows**: Associe e desassocie o KeyTune nas preferências para abrir arquivos diretamente pelo menu do sistema Windows.
- **Logs de Diagnóstico**: Sistema para registro de logs com rotação automática para depuração, com controle de nível de detalhe nas preferências.
- **Atualização Automática no Windows**: Diálogos com notas de release, barra de progresso visual de download e aplicação de pacotes ZIP com atualizador autônomo.

## Ajustes Recentes e Estabilidade
- **Novos Atalhos**: Atalho `Ctrl+W` redefinido para fechar a aba ativa e `Ctrl+Shift+W` para descarregar a mídia ativa, alinhando com a convenção de navegadores.
- **Busca Melhorada**: Lista de resultados do YouTube Music agora virtualizada para permitir rolagem e seleção múltipla por teclado (`Ctrl+Arrow` e `Ctrl+Space`).
- **Mais Estabilidade**: Refatoração estrutural modular no serviço do YouTube Music e correções importantes para atualização automática de dependências em segundo plano.
