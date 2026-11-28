# Testando o sistema de atualização

Este documento descreve um fluxo prático para validar a atualização automática no Windows sem depender do repositório principal.

## Objetivo do teste

Na preparação de uma release, confirme a versão e a data de publicação em `docs/changelog/<versão>.md` e em suas traduções `.en.md` e `.es.md`. O workflow usa o arquivo em português como corpo da release e publica as traduções como `release-notes.en.md` e `release-notes.es.md`.

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

1. Confirme que Python 3.14 e `7-Zip` estão disponíveis na máquina, porque o build usa o Python 3.14 e o helper compartilhado do MPV descompacta o runtime.
2. Confirme que o ambiente virtual tem `PyInstaller` disponível e que Node.js 24 com npm está no `PATH`.
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

Ao final, você terá (o instalador exige `ISCC.exe` do Inno Setup 6; instale por usuário com `winget install --id JRSoftware.InnoSetup --exact --scope user` ou por máquina com `choco install innosetup`):

- `dist\KeyTune-Setup.exe`
- `dist\KeyTune-Setup.exe.sha256`
- `dist\KeyTune-Portable.zip`
- `dist\KeyTune-Portable.zip.sha256`
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
  - `KeyTune-Portable.zip`
  - `KeyTune-Portable.zip.sha256`
  - `release-notes.en.md` e `release-notes.es.md` (opcionais; sem eles o diálogo mostra o corpo da release, em português)
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

A versão portátil publica `KeyTune-Portable.zip` e `KeyTune-Portable.zip.sha256` junto do instalador. O zip traz o `KeyTuneUpdater.exe`. O instalador não leva esse executável.

Para testar a atualização portátil, use o mesmo repositório de teste e as mesmas variáveis:

```powershell
$env:MEDIA_PLAYER_UPDATE_REPOSITORY_OWNER = "Ed-Fe"
$env:MEDIA_PLAYER_UPDATE_REPOSITORY_NAME = "KeyTune-update-test"
```

Extraia o `KeyTune-Portable.zip` da versão antiga (ele já vem com `portable.ini`) numa pasta vazia. Não use o setup. Coloque uma frase em `portable.ini` e um arquivo em `data`, para reconhecer os dois depois. Abra o `KeyTune.exe` dessa pasta e confirme em **Ajuda > Verificar atualizações**.

O que conferir:

- o download é o `KeyTune-Portable.zip`, e o `KeyTune-Setup.exe` não abre;
- a janela do atualizador aparece durante a troca e o leitor de tela anuncia o resultado;
- `portable.ini` e a pasta `data` continuam com o que você tinha colocado;
- o KeyTune abre de novo já na versão nova;
- `data/portable-update.log` descreve a troca.

Use uma cópia de teste para simular falhas.

- Publique um ZIP sem `KeyTune.exe`, com `Data` na raiz ou com nomes que só diferem nas maiúsculas. Gere o checksum de cada ZIP. O KeyTune deve rejeitar cada pacote com o player ainda aberto.
- Simule uma falha na extração depois que o player fecha. O atualizador deve tentar reabrir a versão antiga e registrar o erro em `data/portable-update.log`.
- Simule uma falha na troca seguida de um arquivo bloqueado durante a restauração. Confira se o atualizador ainda restaura os demais arquivos e se o erro e o log informam o caminho do backup em `data/portable-update-backup-*`. Use `Tab` para chegar a **Fechar** ou `Esc` para sair depois do erro.
- Abra a cópia portátil com a versão instalada em execução. Envie um arquivo com `--enqueue` para cada executável e confira se a mídia entra na instância correspondente. Repita com a pasta `data` sem permissão de escrita. Na abertura da cópia portátil, confira o aviso e o uso de `%APPDATA%\KeyTune`.
- Com outro player como padrão, confira **Adicionar à playlist do KeyTune** no menu de contexto de cada formato de áudio ou vídeo escolhido na instalação. Os registros por extensão se limitam aos formatos selecionados. Repita o teste após registrar e desregistrar pela seção **Associação de arquivos** nas Preferências da cópia portátil. O desregistro da cópia portátil deve preservar as associações da versão instalada.

## Verificações extras úteis

- Testar com release sem notas para validar a mensagem padrão.
- Testar checksum inválido para confirmar bloqueio da instalação.
- Testar uma instalação per-machine para confirmar o prompt de UAC durante a atualização.
- Validar o registro de "Apps padrão": após instalar, abrir Configurações > Aplicativos > Aplicativos padrão e confirmar que o KeyTune aparece e pode ser associado às extensões.
- Conferir o log do Inno Setup (caminho mostrado quando `SetupLogging=yes`, normalmente em `%TEMP%`) caso a atualização falhe.
