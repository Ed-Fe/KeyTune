# KeyTune

Player de música e vídeo para Windows, pensado para quem usa teclado e leitor de tela. Toca arquivos do computador, YouTube e YouTube Music, rádios online e podcasts, baixa e converte mídia, mostra letras e tem um AutoDJ.

[![Última versão](https://img.shields.io/github/v/release/Ed-Fe/KeyTune?label=%C3%BAltima%20vers%C3%A3o)](https://github.com/Ed-Fe/KeyTune/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Ed-Fe/KeyTune/total?label=downloads)](https://github.com/Ed-Fe/KeyTune/releases)
[![Licença: MIT](https://img.shields.io/github/license/Ed-Fe/KeyTune?label=licen%C3%A7a)](LICENSE)

**[Baixar o KeyTune](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe)** · [Manual](docs/manual.md) · [Novidades](docs/changelog/) · [English](README.md)

## O que ele faz

- Toca áudio e vídeo com controle de velocidade, tom e saída de áudio. Playlists ficam em abas, com fila, explorador de pastas e suporte a `.m3u`.
- Biblioteca com busca global (`Ctrl+G`), favoritos, notas, histórico e playlists inteligentes. Podcasts e audiolivros continuam de onde pararam.
- KeyTube (`Ctrl+Shift+Y`): YouTube e YouTube Music numa lista só, com busca, suas playlists, inscrições, comentários, chat ao vivo, notificações, capítulos e transcrição. Tem SponsorBlock, desligado por padrão.
- Rádios online do [Radio Browser](https://www.radio-browser.info/), por país, gênero e idioma (`Ctrl+Shift+N`).
- Download de músicas, vídeos e playlists com o [yt-dlp](https://github.com/yt-dlp/yt-dlp) (`Ctrl+Shift+B`) e conversão entre formatos com o FFmpeg (`Ctrl+Shift+K`).
- Letras da faixa atual (`Ctrl+Alt+L`), equalizador, timer de desligamento e um AutoDJ que faz as transições na batida.
- Todos os atalhos podem ser trocados. Há atalhos globais, ícone na bandeja e plugins (veja o [guia de plugins](docs/plugins.md)).
- Interface em português, inglês e espanhol.

Foi feito e testado com o NVDA. O KeyTune fala o que muda (faixa, volume, tempo) e você escolhe quais avisos quer ouvir. Ao fechar e abrir de novo, as abas, a faixa e a posição voltam como estavam.

## Instalação

Baixe o [KeyTune-Setup.exe](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Setup.exe) e execute. Funciona no Windows de 64 bits. Se preferir sem instalar, use o [KeyTune-Portable.zip](https://github.com/Ed-Fe/KeyTune/releases/latest/download/KeyTune-Portable.zip): extraia e abra o `KeyTune.exe` (detalhes na [versão portátil](docs/manual.md#versao-portatil)).

O YouTube e o AutoDJ são instalados à parte, em **Preferências > Recursos adicionais**.

## Primeiros passos

- `Ctrl+O` abre arquivos; `Ctrl+V` toca o que você copiou (arquivo, pasta ou link).
- `Espaço` toca e pausa, `Ctrl+PageUp` e `Ctrl+PageDown` trocam de faixa, setas para cima e para baixo mudam o volume.
- `T`, `V` e `S` falam o tempo, o volume e o status.
- `F1` mostra os atalhos e `Ctrl+,` abre as preferências.

O resto está no [manual](docs/manual.md), que também abre pelo menu **Ajuda**. Se algo não tocar, **Ajuda > Diagnóstico** mostra o problema.

## Rodar a partir do código

Precisa do Windows, do [uv](https://docs.astral.sh/uv/) e do Git.

```powershell
git clone https://github.com/Ed-Fe/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

O script do MPV usa o 7-Zip para descompactar. Testes: `python -m unittest discover -s tests`. O build do Windows sai de `scripts/build_windows_release.ps1`.

## Contribuir

- Bugs: [abra uma issue](https://github.com/Ed-Fe/KeyTune/issues/new/choose) e, se puder, anexe o relatório de **Ajuda > Diagnóstico**.
- Ideias e dúvidas: [discussões](https://github.com/Ed-Fe/KeyTune/discussions).
- Código: leia o [guia de contribuição](CONTRIBUTING.pt-BR.md).
- Traduções: veja o [guia de tradução](docs/translations.md).

## Créditos

Criado por [Eduardo Ferreira](https://github.com/Ed-Fe). [Vinicius Siqueira](https://github.com/viniciusSiqueira195) e [Paulo](https://github.com/paulosantesso1) foram quem mais contribuiu, junto com [reffehcsoibaf](https://github.com/reffehcsoibaf). A lista completa de contribuidores e bibliotecas está em [docs/credits.md](docs/credits.md).

Usa [MPV](https://mpv.io/), [wxPython](https://wxpython.org/), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [ytmusicapi](https://github.com/sigma67/ytmusicapi), [YouTube.js](https://github.com/LuanRT/YouTube.js), [FFmpeg](https://ffmpeg.org/), [librosa](https://librosa.org/), [Radio Browser](https://www.radio-browser.info/), [LRCLIB](https://lrclib.net/) e [SponsorBlock](https://sponsor.ajay.app/).

Parte do código foi escrita com ajuda de assistentes de IA (GitHub Copilot, OpenAI Codex e Claude Code).

## Licença

[MIT](LICENSE).
