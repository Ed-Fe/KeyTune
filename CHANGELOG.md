# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-08-03

### Adicionado
- **Busca na playlist ou pasta atual**: `Ctrl+F` abre a caixa **Localizar item**, que procura o texto em qualquer parte do nome, ignorando acentos e maiúsculas. `F3` vai para o próximo resultado e `Shift+F3` para o anterior, com a posição na busca e o aviso de volta ao início da lista na barra de status. Também disponível em **Exibir > Localizar item**.
- **Temporizador de desligamento**: `Ctrl+Shift+D` (ou **Reprodução > Temporizador de desligamento**) agenda a pausa automática da reprodução com durações prontas de 5 a 120 minutos, tempo personalizado ou ao fim da faixa atual. O menu traz ainda **Tempo restante** e **Cancelar temporizador**, há avisos falados faltando 5 minutos e 1 minuto, e o estado entra no anúncio de status (tecla `S`).
- **Conexão com o YouTube Music pelo navegador**: extração direta dos cookies de uma sessão já autenticada no Chrome, Edge, Firefox, Brave ou Opera, com alternância entre os modos navegador e manual na caixa de conexão.

### Corrigido
- **Plurais nas mensagens**: contagens de itens, faixas, playlists, mixes, resultados, dispositivos e minutos passam a usar formas reais de singular e plural (“216 itens”, “1 minuto”) no lugar das abreviações “item(ns)” e “minuto(s)”, em português, inglês e espanhol.
- **Resultados salvos no YouTube Music**: a mensagem de confirmação voltou a ser traduzível.

## [1.2.2] - 2026-07-30

### Corrigido
- **Reprodução do YouTube Music**: adiciona fallback de sessão para tentar perfis sem autenticação quando o YouTube recusa a reprodução autenticada.

## [1.2.1] - 2026-07-27

### Corrigido
- **Reprodução automática de playlists**: playlists preparadas pelo YouTube Music voltam a iniciar corretamente a primeira faixa.
- **Controles de mídia Bluetooth**: recupera a integração com os controles de mídia do Windows após reconexões.
- **YouTube Music e yt-dlp**: identifica runtimes JavaScript compatíveis e informa quando os instalados estão desatualizados ou incompatíveis.
- **Notas da versão**: preserva a codificação UTF-8 ao publicar no GitHub e mostra o conteúdo como texto puro no diálogo de atualização.

## [1.2.0] - 2026-07-05

### Adicionado
- **Sistema de tradução (localização)**: a interface agora pode ser traduzida para outros idiomas. O Português (Brasil) é o idioma-fonte e o Inglês e o Espanhol já vêm incluídos. Escolha o idioma em *Configurações > Preferências > Geral > Idioma* (ou deixe em Automático para seguir o sistema). O manual, os créditos e o instalador também são traduzíveis. Tradutores: veja `docs/translations.md`.
- **Fila de reprodução**: adiciona uma fila independente para organizar o que toca em seguida, com ações para adicionar, gerenciar, remover, reordenar e limpar itens.
- **Painel de letras**: busca e exibe letras automaticamente ao trocar de faixa, com alternância rápida, leitura por teclado e cópia do conteúdo.
- **Velocidade e tom da reprodução**: adiciona atalhos para aumentar, diminuir e restaurar a velocidade (`]`, `[`, `\`) e para alterar ou resetar o tom em semitons (`Shift+]`, `Shift+[`, `Shift+\`).

## [1.1.0] - 2026-06-29

### Adicionado
- **Instalador para Windows**: distribuição como `KeyTune-Setup.exe` com instalação por usuário ou para todos, atalhos no Menu Iniciar, registro em *Aplicativos padrão* e associação opcional de extensões.
- **Atualização automática**: baixa e instala sem intervenção, refletindo em *Aplicativos e recursos*.
- **Em alta por país (YouTube Music)**: paradas e destaques de mais de 50 países, organizados por continente.
- **Moods e gêneros (YouTube Music)**: categorias de climas e gêneros com playlists relacionadas.
- **Curtidas e Histórico (YouTube Music)**: faixas curtidas e histórico de reprodução, prontos para tocar ou adicionar a playlists.
- **Tela "Sobre"**: versão, licença (MIT), links para repositório e créditos de bibliotecas.
- **Tutorial de primeiros passos**: guia interativo apresentando recursos e configurações.

### Alterado
- **Instância única**: abrir novamente traz a janela para frente. Arquivos do Explorador tocam sem roubar o foco.
- **Reprodução mais fluida**: otimizações no crossfade, menos consumo de recursos e menos interrupções visuais.
- **Interface mais rápida**: otimizações de renderização e gestão de bindings.

### Corrigido
- **Conexão YouTube Music duradoura**: guia recomenda exportar cookies em modo privado.
- **Anúncios de acessibilidade**: correção de bugs com screen-readers e foco em diálogos.
- **Reconexão Bluetooth**: recuperação correta após reconexão.
- **Erros ao trocar faixas**: bug raro que causava travamentos.

## [1.0.0] - 2026-06-07

Primeira versão oficial estável (Release) do **KeyTune**. Consolida todos os recursos principais de reprodução de mídia acessível, playlists em abas, equalização, sistema de diagnóstico avançado e integração completa com YouTube Music.

### Resumo dos Recursos

- **Interface Acessível**: totalmente otimizado para leitores de tela, atalhos robustos, anúncios sonoros.
- **Playlists em Abas**: múltiplas playlists em abas, reordenação de faixas, salve e carregue `.m3u` e `.m3u8`.
- **Navegador de Pastas**: estilo Explorer com pré-visualização automática.
- **Restauração de Sessão**: retoma de onde parou — abas, faixa, posição, volume, configurações.
- **Equalizador por Aba**: som independente por playlist, 18 presets, customize ou aplique em todas as abas.
- **Integração com YouTube Music**: busque, acesse mixes e playlists. Importe cookies do navegador, resolução de áudio automática.
- **Associação de Arquivos**: registre/desregistre extensões para abrir com KeyTune.
- **Logs de Diagnóstico**: relatórios detalhados com controle de nível de detalhe.
- **Atualização Automática**: detecta versões, mostra novidades, instala automaticamente.

### Ajustes e Melhorias Recentes
- **Atalhos Consistentes**: `Ctrl+W` fecha aba, `Ctrl+Shift+W` encerra reprodução.
- **Seleção Múltipla**: `Ctrl+Seta` e `Ctrl+Espaço` nos resultados do YouTube Music.
- **Navegação Aprimorada**: correção de foco com Tab.
- **Estabilidade YouTube Music**: recuperação, autenticação e curtidas melhoradas.
