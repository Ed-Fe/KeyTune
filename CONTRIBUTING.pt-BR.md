# Como contribuir com o KeyTune

Valeu por querer ajudar. O KeyTune é usado todo dia por gente que depende de leitor de tela e de teclado, então toda mudança precisa continuar funcionando assim. Este guia diz o que você precisa saber antes de mandar uma.

[Read in English](CONTRIBUTING.md)

## Jeitos de ajudar

- **Relatar um bug** pelo [formulário de bug](https://github.com/Ed-Fe/KeyTune/issues/new/choose). Cole o relatório de **Ajuda > Diagnóstico > Copiar relatório** quando o problema for de reprodução, YouTube ou download.
- **Sugerir um recurso** pelo formulário de sugestão, ou abrir uma [discussão](https://github.com/Ed-Fe/KeyTune/discussions) se a ideia ainda estiver solta.
- **Traduzir** a interface, o manual ou o instalador. O [guia de tradução](docs/translations.md) explica os catálogos em `locale/`.
- **Escrever um plugin**. O [guia de plugins](docs/plugins.md) cobre a API, as permissões e o marketplace.
- **Mandar código**. As issues com a etiqueta [good first issue](https://github.com/Ed-Fe/KeyTune/labels/good%20first%20issue) são um bom começo.

## Preparar o ambiente

O KeyTune roda no Windows. Você precisa do [uv](https://docs.astral.sh/uv/) e do Git; o uv instala o Python 3.14 para você.

```powershell
git clone https://github.com/<seu-usuario>/KeyTune.git
cd KeyTune
uv sync
uv run python scripts/download_mpv_runtime.py
uv run keytune
```

- `uv sync` cria o `.venv` com as versões exatas do `uv.lock`, incluindo as dependências opcionais do YouTube e do AutoDJ. Para adicionar um pacote, use `uv add <pacote>`; para atualizar, `uv lock --upgrade`.
- O script do MPV precisa do 7-Zip. Se você já tem a libmpv, aponte `MPV_HOME` ou `MPV_DLL_DIR` para ela.

## Regras que toda mudança segue

- **Teclado primeiro.** Todo recurso precisa ser alcançável pelo teclado. Mantenha os atalhos que já existem e nunca crie um fluxo que precise do mouse.
- **Leitor de tela primeiro.** Todo campo, botão, lista e grupo precisa de um nome que o leitor de tela anuncie. O foco nunca pode cair na área nativa do vídeo. Os anúncios passam por `src/player/accessibility.py`.
- **Vai criar ou mudar uma tela?** Leia antes o [`.github/instructions/ui-screens.instructions.md`](.github/instructions/ui-screens.instructions.md), monte a tela com os auxiliares de `src/player/widgets.py` e `src/player/reading_dialog.py` e registre o diálogo ou painel novo na lista `SCREENS` do script de auditoria.
- **O português é o idioma de origem.** Todo texto que o usuário vê (rótulos, menus, status, anúncios) é escrito em português e envolvido em `_()`. Depois de mudar esses textos, rode `python scripts/i18n.py extract` e depois `python scripts/i18n.py compile`, e acrescente as traduções em inglês e espanhol.
- **Um módulo, uma função.** Interface, persistência, leitura de dados e serviços externos ficam em módulos separados, seguindo a organização de `src/player/`. O código só do Windows (`single_instance.py`, `file_associations.py`, `smtc/`) fica isolado e precisa falhar com elegância em outros sistemas.
- **Pequeno e focado.** Prefira uma mudança pontual a uma refatoração grande, e abra uma issue antes se for fazer uma grande.

A arquitetura está descrita em [`.github/instructions/player-architecture.instructions.md`](.github/instructions/player-architecture.instructions.md).

## Verificações antes da pull request

- `python -m compileall src`, para conferir a sintaxe rapidinho.
- `python -m unittest discover -s tests`, para mudanças de backend, leitura de dados e serviços.
- `uv run python scripts/audit_ui_accessibility.py` depois de qualquer mudança num diálogo, painel, aba ou página de preferências. Ele confere se todo controle tem nome acessível e se os grupos são grupos de verdade.
- Uma passada manual com leitor de tela (o NVDA é a referência) pelos fluxos de teclado que você mexeu.

## Histórico de mudanças e manual

- Mudanças que o usuário vai notar entram em `docs/changelog/unreleased.md` (português), `unreleased.en.md` e `unreleased.es.md`. Mantenha os três iguais.
- Quando um recurso ou atalho muda, atualize `docs/manual.md`, `docs/manual.en.md` e `docs/manual.es.md`.
- As regras de escrita dos dois estão em [`.github/instructions/writing.instructions.md`](.github/instructions/writing.instructions.md).

## Commits e pull requests

- Mensagens de commit e títulos de PR são em inglês e seguem o [Conventional Commits](https://www.conventionalcommits.org/): `tipo(escopo): resumo`, no imperativo e em minúsculas, por exemplo `fix(youtube): start playback at the chosen chapter`.
- Preencha o modelo da pull request: o que mudou, por quê, como você testou e o que afeta acessibilidade, reprodução, playlists ou a atualização.
- Um assunto por pull request.

## Licença

Ao contribuir, você concorda que a sua contribuição sai sob a [Licença MIT](LICENSE).
