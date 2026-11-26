# KeyTune

**Um player de música e vídeo para Windows feito para o teclado e para leitores de tela.**
Arquivos do computador, YouTube e YouTube Music, rádios online, downloads, letras e um AutoDJ, tudo numa janela que você usa inteira sem tocar no mouse.

[![Última versão](https://img.shields.io/github/v/release/Ed-Fe/KeyTune?label=%C3%BAltima%20vers%C3%A3o)](https://github.com/Ed-Fe/KeyTune/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Ed-Fe/KeyTune/total?label=downloads)](https://github.com/Ed-Fe/KeyTune/releases)
[![Licença: MIT](https://img.shields.io/github/license/Ed-Fe/KeyTune?label=licen%C3%A7a)](LICENSE)
![Plataforma: Windows](https://img.shields.io/badge/plataforma-Windows-0078D4)

**[Baixar o KeyTune para Windows](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** · [Manual do usuário](docs/manual.md) · [Novidades](docs/changelog/) · [Read in English](README.md)

<!-- Captura de tela: adicione docs/images/main-window.png (janela principal com uma playlist e o painel de tempo) e tire o comentário da linha abaixo.
![Janela principal do KeyTune com uma playlist aberta e o painel de tempo embaixo](docs/images/main-window.png)
-->

## Por que o KeyTune

- **Tudo funciona pelo teclado.** Reprodução, playlists, busca, YouTube, rádio, downloads e configurações têm atalho, e você pode mudar qualquer um deles.
- **Feito para leitores de tela.** Desenvolvido e testado com o NVDA. Cada campo, botão, lista e grupo tem nome, o foco nunca pula para a área do vídeo, e o KeyTune fala o que muda (faixa, volume, tempo, status) pelo seu leitor de tela. Você escolhe quais avisos falam.
- **Um player no lugar de cinco.** Sua pasta de músicas, o YouTube, o YouTube Music, rádios do mundo todo e podcasts ficam lado a lado, em abas.
- **Continua de onde você parou.** As abas, a faixa, a posição e o volume voltam na próxima vez que você abre.

## Recursos

### Reprodução e biblioteca

- Reprodução de áudio e vídeo com o [MPV](https://mpv.io/), com controle de velocidade e de tom e escolha da saída de áudio.
- Playlists em abas, suporte a `.m3u` e `.m3u8`, fila de reprodução e explorador de pastas ao lado das abas (`Ctrl+E`).
- Biblioteca inteligente: busca global nas músicas indexadas (`Ctrl+G`), favoritos, notas com estrelas, histórico de reprodução e playlists inteligentes montadas por regras.
- Retomada por arquivo para podcasts, audiolivros e vídeos longos, com a lista "continuar ouvindo".
- Painel de letras que procura sozinho a letra da faixa atual (`Ctrl+Alt+L`).
- Equalizador com predefinições prontas e suas, timer de desligamento e vídeo em tela cheia (`Alt+Enter`).
- Player rápido: `Enter` numa música no Explorador de Arquivos toca na hora, numa janela pequena.

### KeyTube: YouTube e YouTube Music

- YouTube e YouTube Music numa lista acessível só (`Ctrl+Shift+Y`): busca, suas playlists e mixes, curtidas, histórico, inscrições, canais e em alta.
- Comentários, chat ao vivo, notificações, capítulos e transcrição, tudo para ler e escrever pelo teclado.
- Transmissões ao vivo, Shorts, rádio a partir da faixa atual (`Ctrl+R`) e retomada sincronizada com o celular e a TV.
- Suporte ao [SponsorBlock](https://sponsor.ajay.app/), para pular patrocínios e as partes sem música dos clipes (vem desligado).

### Rádio, download e conversão

- Rádios online do diretório aberto [Radio Browser](https://www.radio-browser.info/), com favoritas e navegação por país, gênero e idioma (`Ctrl+Shift+N`).
- Download de músicas, vídeos e playlists inteiras do YouTube e do YouTube Music com o [yt-dlp](https://github.com/yt-dlp/yt-dlp), na qualidade original, em MP3 ou em FLAC (`Ctrl+Shift+B`).
- Conversão de áudio e vídeo entre formatos com o FFmpeg (`Ctrl+Shift+K`), de um arquivo ou de vários de uma vez.

### AutoDJ

- Um AutoDJ opcional que mixa a sua playlist como um DJ: analisa andamento, batidas, frases, tonalidade e volume, e encaixa cada transição na batida.

### Do seu jeito

- Personalização de todos os atalhos, com aviso de conflito (**Configurações > Personalizar teclado**).
- Atalhos globais que funcionam com o KeyTune minimizado, ícone na bandeja do sistema e controles de mídia do Windows.
- Sons de alerta para os eventos, que você pode desligar ou trocar pelos seus.
- Plugins com permissões explícitas, gerenciador de plugins e um marketplace da comunidade. Veja o [guia de plugins](docs/plugins.md).
- Interface em português, inglês e espanhol.

## Instalação

1. Baixe o **[KeyTune-Setup.exe](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** da [versão mais recente](https://github.com/Ed-Fe/KeyTune/releases/latest).
2. Execute. Dá para instalar só para o seu usuário, sem precisar de administrador, ou para todos os usuários do computador.
3. Na página de tarefas adicionais, você pode criar um atalho na área de trabalho e associar formatos de áudio, vídeo e playlist ao KeyTune. Tudo isso é opcional.

O KeyTune roda no Windows de 64 bits. O instalador já traz o MPV, então ele toca de cara. A integração com o YouTube e o AutoDJ são downloads opcionais: o KeyTune mostra o que vai instalar e pergunta antes de baixar qualquer coisa (**Configurações > Preferências > Recursos adicionais**).

O KeyTune se atualiza sozinho. Quando sai uma versão nova, ele mostra o que mudou, no seu idioma, e pergunta antes de baixar e instalar.

## Primeiros passos

- `Ctrl+O` abre arquivos, e `Ctrl+V` toca um arquivo, uma pasta ou um link que você copiou.
- `Espaço` toca ou pausa, `Ctrl+PageUp` e `Ctrl+PageDown` trocam de faixa, e as setas para cima e para baixo mudam o volume.
- `T`, `V` e `S` falam o tempo, o volume e o status.
- `F1` abre a ajuda rápida de atalhos a qualquer momento.
- `Ctrl+,` abre as preferências.

A lista completa está no [manual do usuário](docs/manual.md), que também abre dentro do KeyTune, pelo menu **Ajuda**. Se algo não tocar, **Ajuda > Diagnóstico** diz o que está errado e o que fazer.

## Rodar a partir do código

Você precisa do Windows, do [uv](https://docs.astral.sh/uv/) e do Git. O uv instala o Python 3.14 para você.

```powershell
git clone https://github.com/Ed-Fe/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

- `uv sync` cria o `.venv` com as versões exatas do `uv.lock`, incluindo as dependências opcionais do YouTube e do AutoDJ.
- `scripts/download_mpv_runtime.py` baixa a versão mais recente da libmpv para `./mpv/` e precisa do 7-Zip para descompactar. Se você já tem a libmpv, aponte `MPV_HOME` ou `MPV_DLL_DIR` para ela.
- `iniciar_player.bat` é um atalho que roda `uv run keytune` para você.

Os testes rodam com `python -m unittest discover -s tests`. A versão para Windows (app, MPV e instalador do Inno Setup) é gerada pelo `.github/workflows/release-windows.yml`, ou localmente com `scripts/build_windows_release.ps1`.

## Como contribuir

Relatos de bug, ideias, traduções e código são todos bem-vindos.

- Achou um bug? [Abra uma issue](https://github.com/Ed-Fe/KeyTune/issues/new/choose). O relatório de **Ajuda > Diagnóstico** ajuda muito.
- Tem uma ideia ou uma dúvida? Abra uma [discussão](https://github.com/Ed-Fe/KeyTune/discussions).
- Quer escrever código? Leia o [guia de contribuição](CONTRIBUTING.pt-BR.md) e procure as issues com a etiqueta [good first issue](https://github.com/Ed-Fe/KeyTune/labels/good%20first%20issue).
- Quer o KeyTune no seu idioma? Veja o [guia de tradução](docs/translations.md).

## Créditos

O KeyTune é criado e mantido por [Eduardo Ferreira](https://github.com/Ed-Fe), com contribuições de código de [reffehcsoibaf](https://github.com/reffehcsoibaf) e [paulosantesso1](https://github.com/paulosantesso1). Veja todo mundo na [página de contribuidores](https://github.com/Ed-Fe/KeyTune/graphs/contributors).

O KeyTune se apoia no [MPV](https://mpv.io/), [wxPython](https://wxpython.org/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [YouTube.js](https://github.com/LuanRT/YouTube.js), [FFmpeg](https://ffmpeg.org/), [librosa](https://librosa.org/), [accessible-output2](https://pypi.org/project/accessible-output2/), [Radio Browser](https://www.radio-browser.info/), [LRCLIB](https://lrclib.net/) e [SponsorBlock](https://sponsor.ajay.app/). A lista completa de bibliotecas está em [docs/credits.md](docs/credits.md).

O projeto é desenvolvido com a ajuda de assistentes de programação com IA, entre eles o GitHub Copilot, o OpenAI Codex e o Claude Code, da Anthropic.

## Licença

O KeyTune é software livre, sob a [Licença MIT](LICENSE).
