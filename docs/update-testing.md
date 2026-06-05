# Testando o sistema de atualização

Este documento descreve um fluxo prático para validar a atualização automática no Windows sem depender do repositório principal.

## Objetivo do teste

Validar que a aplicação empacotada:

1. verifica uma release remota mais nova ao iniciar;
2. mostra as notas da release antes do download;
3. baixa o arquivo `KeyTune-windows.zip` com barra de progresso;
4. fecha a aplicação principal;
5. aplica o pacote com `KeyTuneUpdater.exe`;
6. reinicia com a nova versão.

## Estratégia recomendada

Use um repositório de teste no GitHub, por exemplo `Ed-Fe/KeyTune-update-test`, para publicar releases sem interferir na release estável do projeto principal.

A build do app pode apontar para esse repositório por meio das variáveis de ambiente:

- `MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER`
- `MEDIA_PLAYER_UPDATE_REPOSITORY_NAME`

Se essas variáveis não estiverem definidas, o app continua usando `Ed-Fe/KeyTune`.

## Preparando uma build local

1. Confirme que `7-Zip` está disponível na máquina, porque o helper compartilhado do MPV descompacta o runtime.
2. Confirme que o ambiente virtual tem `PyInstaller` disponível.
3. Gere a release local com o script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1
```

Por padrão, o build script agora baixa e descompacta automaticamente o runtime do MPV por meio de `scripts/download_mpv_runtime.py`, e depois baixa o `yt-dlp.exe` oficial do canal estável e o embute ao lado do `KeyTune.exe`.

Se quiser fixar o runtime do MPV a uma pasta local ou a um arquivo `.7z`, passe `-MpvSource` ou `-MpvRuntimeArchive` para o build script. Para testar uma release local já com o canal nightly do yt-dlp, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1 -YtDlpChannel nightly
```

Ao final, você terá:

- `KeyTune-windows.zip`
- `KeyTune-windows.zip.sha256`

## Cenário recomendado de teste ponta a ponta

### Etapa A — preparar a versão antiga

1. Defina `APP_VERSION` para uma versão antiga, por exemplo `0.1.0`.
2. Gere a build local e extraia o conteúdo do ZIP em uma pasta limpa.
3. Essa será a instalação que vai procurar atualização.

### Etapa B — preparar a versão nova no repositório de teste

1. Faça bump de `APP_VERSION` para uma versão mais nova, por exemplo `0.2.0`.
2. Gere novamente a release local.
3. Crie uma release publicada no repositório de teste com tag `v0.2.0`.
4. Anexe os arquivos:
  - `KeyTune-windows.zip`
  - `KeyTune-windows.zip.sha256`
5. Escreva no corpo da release as notas/changelog que devem aparecer no diálogo antes do download.

### Etapa C — apontar a build antiga para o repositório de teste

Na máquina que vai executar a versão antiga, defina:

```powershell
  $env:MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER = "Ed-Fe"
  $env:MEDIA_PLAYER_UPDATE_REPOSITORY_NAME = "KeyTune-update-test"
```

Depois inicie `KeyTune.exe` a partir da pasta extraída da versão antiga.

## O que validar durante o teste

- Ao iniciar, a aplicação detecta a nova versão automaticamente.
- O diálogo mostra:
  - versão atual e nova versão;
  - nome do arquivo;
  - tamanho do download;
  - notas da release.
- Ao confirmar:
  - abre o diálogo de download;
  - a barra avança durante o download;
  - cancelar interrompe o processo sem corromper a instalação.
- Ao concluir:
  - o player fecha;
  - o updater aplica o ZIP;
  - o app reinicia;
  - a nova versão passa a ser a instalada.

## Verificações extras úteis

- Testar com release sem notas para validar a mensagem padrão.
- Testar checksum inválido para confirmar bloqueio da instalação.
- Testar pasta sem permissão de escrita para validar rollback/log de erro.
- Conferir o log do updater em `%TEMP%\KeyTuneUpdater\updater.log` caso algo falhe.
