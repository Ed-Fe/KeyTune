# Manual do KeyTune

Este documento é o manual inicial do KeyTune. Ele foi pensado para viver no repositório em Markdown e, na hora de gerar uma release, virar uma versão HTML navegável dentro do pacote distribuído.

## Como ler este manual

Você pode abrir este manual de três formas:

1. No repositório, diretamente em `docs/manual.md`.
2. No VS Code, usando a pré-visualização de Markdown.
3. Na release empacotada, abrindo `docs/manual.html` no navegador ou em qualquer visualizador de HTML.

## O que é o KeyTune

O KeyTune é um player de mídia focado em teclado e acessibilidade. Ele foi desenhado para funcionar bem com playlists, navegação por pastas, restauração de sessão, preferências persistentes e integração com MPV.

## Primeiros passos

Ao abrir o aplicativo pela primeira vez, vale seguir esta ordem:

1. Confirmar que a reprodução de áudio e vídeo está funcionando.
2. Abrir alguns arquivos de mídia ou uma playlist `.m3u` / `.m3u8`.
3. Testar a navegação por abas e os atalhos principais.
4. Verificar se as preferências estão sendo salvas corretamente.

## Fluxo básico de uso

### Abrir conteúdo

O KeyTune aceita arquivos locais, playlists e pastas. O fluxo mais simples é usar o diálogo de abertura ou os atalhos do teclado para inserir mídia diretamente na playlist atual.

### Navegar com o teclado

O aplicativo foi desenhado para ser usado sem depender do mouse. A lista principal, as abas e os diálogos devem manter uma navegação previsível por teclado.

### Usar playlists

As playlists podem ser abertas, salvas e reorganizadas. Quando houver várias abas, cada uma preserva seu próprio estado de reprodução.

## Reprodução e biblioteca

O player usa MPV como base de reprodução. A biblioteca local permite navegar por arquivos e pastas, e a sessão pode restaurar a aba ativa, a posição da mídia e o volume anterior.

## Equalizador

O equalizador é separado por aba e pode usar presets internos ou ajustes personalizados. A ideia é permitir mudança rápida sem perder o contexto da playlist atual.

## YouTube Music

Existe uma aba dedicada ao YouTube Music para autenticação, busca e carregamento de playlists e mixes. Esse fluxo pode ser tratado como um complemento à biblioteca local, não como substituto dela.

## Atualizações

Na release do Windows, o aplicativo pode baixar e aplicar atualizações automaticamente. O pacote distribuído inclui o updater externo e o arquivo de checksum do ZIP.

## Acessibilidade

Mensagens, rótulos e anúncios continuam priorizando uso com leitor de tela e navegação por teclado. Se um comportamento novo quebrar esse fluxo, o manual deve ser atualizado junto com a alteração no código.

## Próximos capítulos

Este manual ainda está sendo escrito. As próximas revisões devem detalhar:

1. instalação e primeira execução;
2. atalhos de teclado por área do app;
3. uso do navegador de biblioteca;
4. equalizador e presets;
5. YouTube Music;
6. atualização e empacotamento da release.
