# Testando o sistema de atualização

Este documento descreve um fluxo prático para validar a atualização automática no Windows sem depender do repositório principal.

## Objetivo do teste

Na preparação de uma release, confirme a versão e a data de publicação no changelog. O workflow usa essa seção como corpo da release.

Antes de distribuir o instalador, confirme em `dist/KeyTune/docs` a presença de `plugins.html`, `plugins.en.html` e `plugins.es.html`, além dos manuais. Abra cada manual e siga o link para a API sem conexão; confira também os links entre idiomas e o destino do rodapé. O instalador deve preservar esses arquivos na pasta `docs` da instalação.

Validar que a aplicação empacotada:

1. verifica uma release remota mais nova ao iniciar;
2. mostra as notas da release antes do download;
3. baixa o arquivo `KeyTune-Setup.exe` com barra de progresso;
4. executa o instalador em modo silencioso (`/VERYSILENT`), que fecha a aplicação, troca os arquivos e reinicia com a nova versão.

> Instalações per-machine (Arquivos de Programas) exigem elevação: o app dispara o instalador via UAC nesse caso. Instalações per-user atualizam sem prompt.

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

Por padrão, o build script baixa e descompacta o runtime do MPV, baixa o `yt-dlp.exe` oficial e gera separadamente os pacotes opcionais de Node.js, dependências Python do YouTube, YouTube.js e AutoDJ. Esses quatro pacotes não entram no instalador principal; a release os publica com checksums para download sob demanda. O build falha se NumPy, librosa, SciPy, Numba, llvmlite ou PyAV aparecerem em `dist/KeyTune/_internal`.

O build também exige Node.js com npm no PATH. Os manifestos dos pacotes devem usar a mesma versão de `APP_VERSION` em `src/player/constants.py` e da tag publicada.

Antes de publicar, valide em uma pasta de dados limpa: ativação e confirmação pelo teclado em Recursos adicionais, download dos quatro pacotes com seus checksums, reprodução pelo YouTube.js e análise de uma faixa pelo processo isolado do AutoDJ, que reutiliza o runtime Python do KeyTune. Repita a atualização de dependências: pacotes válidos com a mesma `resource_revision` não devem ser baixados novamente após atualizar somente o player; em especial, preserve o Node.js gerenciado já instalado. O yt-dlp continua consultando o canal selecionado. Confira também os anúncios de progresso com leitor de tela.

Se quiser fixar o runtime do MPV a uma pasta local ou a um arquivo `.7z`, passe `-MpvSource` ou `-MpvRuntimeArchive` para o build script. Para testar uma release local já com o canal nightly do yt-dlp, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1 -YtDlpChannel nightly
```

Ao final, você terá (o instalador exige `ISCC.exe` do Inno Setup 6 no PATH padrão; instale com `choco install innosetup`):

- `dist\KeyTune-Setup.exe`
- `dist\KeyTune-Setup.exe.sha256`
- `dist\optional-resources\KeyTune-NodeJS-win-x64.zip` + `.sha256`
- `dist\optional-resources\KeyTune-YouTubePython-win-x64.zip` + `.sha256`
- `dist\optional-resources\KeyTune-YouTubeJS-win-x64.zip` + `.sha256`
- `dist\optional-resources\KeyTune-AutoDJ-win-x64.zip` + `.sha256`
- `KeyTune-windows.zip` + `.sha256` (build em pasta, usado para gerar o instalador)

Para fixar a versão exibida no instalador e em "Aplicativos e recursos", passe `-AppVersion`:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows_release.ps1 -AppVersion 0.2.0
```

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
  - `KeyTune-Setup.exe`
  - `KeyTune-Setup.exe.sha256`
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
  - o instalador silencioso fecha o player, troca os arquivos e reinicia;
  - a nova versão passa a ser a instalada;
  - a versão em "Aplicativos e recursos" reflete a nova release.

## Verificações extras úteis

- Testar com release sem notas para validar a mensagem padrão.
- Testar checksum inválido para confirmar bloqueio da instalação.
- Testar uma instalação per-machine para confirmar o prompt de UAC durante a atualização.
- Validar o registro de "Apps padrão": após instalar, abrir Configurações > Aplicativos > Aplicativos padrão e confirmar que o KeyTune aparece e pode ser associado às extensões.
- Conferir o log do Inno Setup (caminho mostrado quando `SetupLogging=yes`, normalmente em `%TEMP%`) caso a atualização falhe.
